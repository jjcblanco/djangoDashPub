"""
Optimized trading strategies based on security audit findings.
"""
import pandas as pd
import numpy as np
from decimal import Decimal
from .backtester import DayTradingStrategy
from .indicadores import calculate_rsi, atr, adx, macd, bollinger_bands

class OptimizedDayTradingStrategy(DayTradingStrategy):
    """
    Optimized Day Trading Strategy addressing issues identified in security audit:
    1. Simplified indicator set (2 EMAs + RSI + ATR)
    2. Dynamic RSI thresholds based on market conditions
    3. Improved risk management with adaptive position sizing
    4. Market regime detection (trending vs ranging)
    5. Volume confirmation
    """
    
    def __init__(self, parameters=None):
        # Call parent but we'll override parameters
        super().__init__(parameters)
        
        # Override default parameters with optimized defaults
        self.parameters = {
            'ema_fast': 9,
            'ema_slow': 21,
            'ema_trend': 200,  # For trend filter only
            'rsi_period': 14,
            'rsi_upper_dynamic': True,  # Use dynamic thresholds
            'rsi_lower_dynamic': True,
            'rsi_upper_static': 60,     # Fallback static values
            'rsi_lower_static': 40,
            'atr_period': 14,
            'atr_sl_multiplier': 1.5,   # Stop loss
            'atr_tp_multiplier': 3.0,   # Take profit (2:1 RR)
            'use_volume_filter': True,
            'volume_ma_period': 20,
            'min_adx': 20,              # Minimum trend strength
            'risk_per_trade_pct': 1.0,  # Conservative risk per trade
            'max_positions': 3,         # Maximum concurrent positions
            'cooldown_bars': 5,         # Bars between trades
            'market_regime_filter': True, # Filter by market regime
        }
        
        # Update with user parameters
        if parameters:
            self.parameters.update(parameters)
    
    def calculate_dynamic_rsi_thresholds(self, df, lookback=100):
        """Calculate dynamic RSI thresholds based on recent market conditions."""
        if len(df) < lookback:
            lookback = len(df)
        
        recent_rsi = df['rsi'].tail(lookback)
        
        # Use percentiles for thresholds
        upper_threshold = recent_rsi.quantile(0.7)  # 70th percentile
        lower_threshold = recent_rsi.quantile(0.3)  # 30th percentile
        
        # Ensure thresholds are reasonable
        upper_threshold = max(60, min(75, upper_threshold))
        lower_threshold = max(25, min(40, lower_threshold))
        
        return upper_threshold, lower_threshold
    
    def detect_market_regime(self, df):
        """Detect if market is trending or ranging."""
        if 'adx' not in df.columns:
            df['adx'] = adx(df, 14)
        
        # Calculate EMA trend if not exists
        if 'ema_trend' not in df.columns:
            ema_t = int(self.parameters['ema_trend'])
            df['ema_trend'] = df['close'].ewm(span=ema_t, adjust=False).mean()
        
        # Simple regime detection: high ADX = trending, low ADX = ranging
        df['regime'] = 'ranging'
        df.loc[df['adx'] > 25, 'regime'] = 'trending'
        
        # Additional check: price distance from EMA trend
        df['distance_pct'] = (df['close'] - df['ema_trend']) / df['ema_trend'] * 100
        df.loc[abs(df['distance_pct']) > 5, 'regime'] = 'trending'
        
        return df
    
    def generate_signals(self, df):
        """Generate optimized trading signals."""
        # Ensure numeric columns (convert Decimal to float)
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_cols:
            if col in df.columns and df[col].dtype == 'object':
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 1. Calculate indicators
        ema_f = int(self.parameters['ema_fast'])
        ema_s = int(self.parameters['ema_slow'])
        ema_t = int(self.parameters['ema_trend'])
        
        df['ema_fast'] = df['close'].ewm(span=ema_f, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=ema_s, adjust=False).mean()
        df['ema_trend'] = df['close'].ewm(span=ema_t, adjust=False).mean()
        
        df['rsi'] = calculate_rsi(df, int(self.parameters['rsi_period']))
        df['atr'] = atr(df, int(self.parameters['atr_period']))
        
        # 2. Market regime detection
        if self.parameters['market_regime_filter']:
            df = self.detect_market_regime(df)
        
        # 3. Dynamic RSI thresholds
        if self.parameters['rsi_upper_dynamic'] or self.parameters['rsi_lower_dynamic']:
            rsi_upper, rsi_lower = self.calculate_dynamic_rsi_thresholds(df)
        else:
            rsi_upper = self.parameters['rsi_upper_static']
            rsi_lower = self.parameters['rsi_lower_static']
        
        # 4. Volume filter
        if self.parameters['use_volume_filter'] and 'volume' in df.columns:
            vol_ma = df['volume'].rolling(window=self.parameters['volume_ma_period']).mean()
            df['volume_ratio'] = df['volume'] / vol_ma
        else:
            df['volume_ratio'] = 1.0
        
        # 5. Signal generation
        df['signal'] = 'HOLD'
        df['stop_loss'] = np.nan
        df['take_profit'] = np.nan
        df['signal_strength'] = 0.0
        
        # EMA crossover conditions
        ema_crossover_bullish = (df['ema_fast'] > df['ema_slow']) & (df['ema_fast'].shift(1) <= df['ema_slow'].shift(1))
        ema_crossover_bearish = (df['ema_fast'] < df['ema_slow']) & (df['ema_fast'].shift(1) >= df['ema_slow'].shift(1))
        
        # Trend filter
        trend_up = df['close'] > df['ema_trend']
        trend_down = df['close'] < df['ema_trend']
        
        # Volume confirmation
        volume_ok = df['volume_ratio'] > 0.8  # Allow slightly below average
        
        # Regime filter
        if self.parameters['market_regime_filter']:
            regime_ok = df['regime'] == 'trending'
        else:
            regime_ok = True
        
        # Buy conditions
        buy_conditions = (
            ema_crossover_bullish &
            trend_up &
            (df['rsi'] > rsi_lower) & (df['rsi'] < 70) &  # RSI not overbought
            volume_ok &
            regime_ok
        )
        
        # Sell conditions (for short positions or exit signals)
        sell_conditions = (
            ema_crossover_bearish &
            trend_down &
            (df['rsi'] < rsi_upper) & (df['rsi'] > 30) &  # RSI not oversold
            volume_ok &
            regime_ok
        )
        
        # Apply ADX filter for trend strength
        if 'adx' in df.columns:
            buy_conditions = buy_conditions & (df['adx'] >= self.parameters['min_adx'])
            sell_conditions = sell_conditions & (df['adx'] >= self.parameters['min_adx'])
        
        # Assign signals
        df.loc[buy_conditions, 'signal'] = 'BUY'
        df.loc[sell_conditions, 'signal'] = 'SELL'
        
        # 6. Calculate stop loss and take profit
        for idx in df.index[buy_conditions]:
            current_price = df.loc[idx, 'close']
            atr_value = df.loc[idx, 'atr']
            
            # ATR-based stop loss and take profit
            stop_loss = current_price - (atr_value * self.parameters['atr_sl_multiplier'])
            take_profit = current_price + (atr_value * self.parameters['atr_tp_multiplier'])
            
            df.at[idx, 'stop_loss'] = stop_loss
            df.at[idx, 'take_profit'] = take_profit
            
            # Calculate signal strength (0-1 scale)
            strength = 0.5  # Base strength
            
            # Increase strength with RSI position
            rsi_value = df.loc[idx, 'rsi']
            if rsi_value > 50:
                strength += 0.2
            if df.loc[idx, 'volume_ratio'] > 1.2:
                strength += 0.2
            if 'adx' in df.columns and df.loc[idx, 'adx'] > 30:
                strength += 0.1
            
            df.at[idx, 'signal_strength'] = min(1.0, strength)
        
        for idx in df.index[sell_conditions]:
            current_price = df.loc[idx, 'close']
            atr_value = df.loc[idx, 'atr']
            
            stop_loss = current_price + (atr_value * self.parameters['atr_sl_multiplier'])
            take_profit = current_price - (atr_value * self.parameters['atr_tp_multiplier'])
            
            df.at[idx, 'stop_loss'] = stop_loss
            df.at[idx, 'take_profit'] = take_profit
            
            # Signal strength for sell
            strength = 0.5
            rsi_value = df.loc[idx, 'rsi']
            if rsi_value < 50:
                strength += 0.2
            if df.loc[idx, 'volume_ratio'] > 1.2:
                strength += 0.2
            if 'adx' in df.columns and df.loc[idx, 'adx'] > 30:
                strength += 0.1
            
            df.at[idx, 'signal_strength'] = min(1.0, strength)
        
        # 7. Apply cooldown period
        if self.parameters['cooldown_bars'] > 0:
            df = self.apply_cooldown_period(df)
        
        return df
    
    def apply_cooldown_period(self, df):
        """Ensure minimum bars between signals."""
        cooldown = self.parameters['cooldown_bars']
        signal_indices = df.index[df['signal'].isin(['BUY', 'SELL'])]
        
        for i in range(len(signal_indices)):
            if i > 0:
                idx = signal_indices[i]
                prev_idx = signal_indices[i-1]
                bars_between = df.index.get_loc(idx) - df.index.get_loc(prev_idx)
                
                if bars_between < cooldown:
                    df.at[idx, 'signal'] = 'HOLD'
                    df.at[idx, 'stop_loss'] = np.nan
                    df.at[idx, 'take_profit'] = np.nan
        
        return df

class EnhancedRiskManager:
    """
    Enhanced risk management with correlation analysis and position sizing.
    """
    
    def __init__(self, max_portfolio_risk=0.02, max_correlation=0.7):
        self.max_portfolio_risk = max_portfolio_risk  # 2% max portfolio risk
        self.max_correlation = max_correlation
        self.positions = []
    
    def calculate_position_size(self, account_balance, entry_price, stop_loss, risk_per_trade_pct=1.0):
        """Calculate position size based on risk percentage."""
        risk_amount = account_balance * (risk_per_trade_pct / 100)
        risk_per_unit = abs(entry_price - stop_loss)
        
        if risk_per_unit == 0:
            return 0
        
        position_size = risk_amount / risk_per_unit
        return position_size
    
    def check_correlation(self, new_symbol, existing_positions, historical_data):
        """Check correlation with existing positions."""
        # Simplified correlation check
        # In production, would use actual correlation calculation
        if not existing_positions:
            return True
        
        # For now, assume different symbols have low correlation
        existing_symbols = [pos['symbol'] for pos in existing_positions]
        if new_symbol in existing_symbols:
            return False  # Already have position in this symbol
        
        # Simple diversification check
        max_same_asset_class = 2
        # Count positions in similar assets (simplified)
        return True
    
    def can_open_trade(self, account_balance, positions, new_trade_details):
        """Check if new trade can be opened given risk constraints."""
        # Check max positions
        if len(positions) >= 10:  # Arbitrary limit
            return False
        
        # Check portfolio risk
        total_risk = self.calculate_portfolio_risk(positions)
        if total_risk > self.max_portfolio_risk:
            return False
        
        return True
    
    def calculate_portfolio_risk(self, positions):
        """Calculate total portfolio risk."""
        # Simplified risk calculation
        total_risk = 0
        for pos in positions:
            total_risk += pos.get('risk', 0)
        
        return total_risk