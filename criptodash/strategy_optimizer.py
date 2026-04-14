#!/usr/bin/env python
"""
Strategy Optimizer - Analyze and improve trading bot performance
"""
import os
import sys
import django
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from decimal import Decimal
import json

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    django.setup()
    print("[OK] Django setup successful")
except Exception as e:
    print(f"[ERROR] Django setup failed: {e}")
    sys.exit(1)

from django.db.models import Count, Sum, Avg, Q
from dashboard.models import LiveBot, LiveTrade, BacktestResult, TradingPair
from dashboard.backtester import DayTradingStrategy, GridStrategy


class StrategyAnalyzer:
    """Analyze trading strategy performance and suggest optimizations"""
    
    def __init__(self):
        self.bots = LiveBot.objects.all()
        self.analysis_results = {}
        
    def analyze_all_bots(self):
        """Comprehensive analysis of all bots"""
        print("\n" + "="*80)
        print("STRATEGY PERFORMANCE ANALYSIS")
        print("="*80)
        
        results = {}
        
        for bot in self.bots:
            print(f"\nAnalyzing Bot: {bot.name} ({bot.strategy_type})")
            bot_analysis = self.analyze_bot(bot)
            results[bot.id] = bot_analysis
            
            # Print summary
            if bot_analysis['trades_count'] > 0:
                win_rate = bot_analysis['win_rate']
                profit_factor = bot_analysis['profit_factor']
                status = "✅ GOOD" if profit_factor > 1.5 else "⚠️ WARNING" if profit_factor > 1.0 else "❌ POOR"
                
                print(f"  Status: {status}")
                print(f"  Win Rate: {win_rate:.1f}%")
                print(f"  Profit Factor: {profit_factor:.2f}")
                print(f"  Total PNL: ${bot_analysis['total_pnl']:.2f}")
                print(f"  Issues: {', '.join(bot_analysis['issues'])}")
        
        self.analysis_results = results
        return results
    
    def analyze_bot(self, bot):
        """Analyze individual bot performance"""
        trades = LiveTrade.objects.filter(bot=bot)
        
        if trades.count() == 0:
            return {
                'bot_id': bot.id,
                'bot_name': bot.name,
                'strategy': bot.strategy_type,
                'trades_count': 0,
                'issues': ['No trades executed'],
                'recommendations': ['Need to activate bot']
            }
        
        # Calculate metrics
        closed_trades = trades.filter(status='CLOSED')
        winning_trades = closed_trades.filter(pnl__gt=0)
        losing_trades = closed_trades.filter(pnl__lt=0)
        
        total_trades = closed_trades.count()
        win_rate = (winning_trades.count() / total_trades * 100) if total_trades > 0 else 0
        
        total_profit = winning_trades.aggregate(total=Sum('pnl'))['total'] or Decimal('0')
        total_loss = abs(losing_trades.aggregate(total=Sum('pnl'))['total'] or Decimal('0'))
        
        profit_factor = float(total_profit / total_loss) if total_loss > 0 else float('inf') if total_profit > 0 else 0
        
        avg_win = winning_trades.aggregate(avg=Avg('pnl'))['avg'] or Decimal('0')
        avg_loss = losing_trades.aggregate(avg=Avg('pnl'))['avg'] or Decimal('0')
        
        # Identify issues
        issues = []
        
        if bot.status == 'ERROR':
            issues.append(f'Bot in ERROR state: {bot.last_error[:100]}')
        
        if win_rate < 40:
            issues.append(f'Low win rate ({win_rate:.1f}%)')
        
        if profit_factor < 1.2:
            issues.append(f'Low profit factor ({profit_factor:.2f})')
        
        if avg_loss > abs(avg_win) * 0.7:  # Losses too large relative to wins
            issues.append('Losses too large relative to wins')
        
        # Check for parameter issues
        params = bot.parameters or {}
        if bot.strategy_type == 'GRID':
            if not params.get('upper_price') or not params.get('lower_price'):
                issues.append('Missing grid boundaries')
            if not params.get('grid_levels') or int(params.get('grid_levels', 0)) < 3:
                issues.append('Too few grid levels')
        
        elif bot.strategy_type == 'DAYTRADING':
            # Check for reasonable parameters
            rsi_buy = params.get('rsi_buy', 55)
            rsi_sell = params.get('rsi_sell', 45)
            if rsi_buy <= rsi_sell:
                issues.append('RSI buy threshold <= sell threshold')
        
        # Generate recommendations
        recommendations = self.generate_recommendations(bot, {
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'avg_win': float(avg_win),
            'avg_loss': float(avg_loss),
            'total_trades': total_trades
        })
        
        return {
            'bot_id': bot.id,
            'bot_name': bot.name,
            'strategy': bot.strategy_type,
            'status': bot.status,
            'trades_count': total_trades,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'total_pnl': float(trades.aggregate(total=Sum('pnl'))['total'] or Decimal('0')),
            'avg_win': float(avg_win),
            'avg_loss': float(avg_loss),
            'issues': issues,
            'recommendations': recommendations,
            'parameters': params
        }
    
    def generate_recommendations(self, bot, metrics):
        """Generate optimization recommendations based on performance"""
        recommendations = []
        params = bot.parameters or {}
        
        if bot.strategy_type == 'GRID':
            # Grid strategy optimizations
            if metrics['profit_factor'] < 1.5:
                recommendations.append('Consider adjusting grid boundaries based on recent price action')
                recommendations.append('Reduce grid levels and increase spacing for better risk/reward')
                recommendations.append('Add dynamic stop loss based on ATR')
            
            if metrics['win_rate'] > 80 and metrics['profit_factor'] < 1.2:
                recommendations.append('Winning too often but small profits - increase take profit distance')
            
            if not params.get('global_stop_loss'):
                recommendations.append('Add global stop loss to protect capital')
        
        elif bot.strategy_type == 'DAYTRADING':
            # Day trading optimizations
            if metrics['win_rate'] < 40:
                recommendations.append('Consider adjusting RSI thresholds (try 60/40 instead of 55/45)')
                recommendations.append('Add ADX filter (>25) to trade only in trending markets')
                recommendations.append('Reduce position size until strategy proves profitable')
            
            if metrics['profit_factor'] < 1.0:
                recommendations.append('Strategy losing money - consider pausing and re-optimizing')
                recommendations.append('Increase stop loss multiplier to avoid being stopped out too early')
                recommendations.append('Try different timeframe (15m instead of 5m)')
            
            if abs(metrics['avg_loss']) > metrics['avg_win'] * 1.5:
                recommendations.append('Losses too large - tighten stop loss or reduce position size')
        
        # General recommendations
        if bot.status == 'ERROR':
            recommendations.append(f'Fix error: {bot.last_error[:100]}')
        
        if metrics['trades_count'] < 20:
            recommendations.append('Need more trades for statistical significance')
        
        if metrics['profit_factor'] > 2.0 and metrics['win_rate'] > 60:
            recommendations.append('Strategy performing well - consider scaling up position size gradually')
        
        return recommendations
    
    def suggest_parameter_optimization(self, bot):
        """Suggest specific parameter optimizations"""
        params = bot.parameters or {}
        suggestions = []
        
        if bot.strategy_type == 'GRID':
            suggestions.append({
                'parameter': 'grid_levels',
                'current': params.get('grid_levels', 'Not set'),
                'suggestion': 'Try 5-7 levels instead of 10 for better risk concentration',
                'reason': 'Fewer levels with larger spacing can improve profit per trade'
            })
            
            suggestions.append({
                'parameter': 'amount_per_level',
                'current': params.get('amount_per_level', 'Not set'),
                'suggestion': 'Adjust based on volatility (higher ATR = larger spacing)',
                'reason': 'Dynamic sizing adapts to market conditions'
            })
        
        elif bot.strategy_type == 'DAYTRADING':
            suggestions.append({
                'parameter': 'rsi_buy / rsi_sell',
                'current': f"{params.get('rsi_buy', 55)}/{params.get('rsi_sell', 45)}",
                'suggestion': 'Try 60/40 for stronger signals',
                'reason': 'Higher thresholds filter out weak signals'
            })
            
            suggestions.append({
                'parameter': 'atr_sl / atr_tp',
                'current': f"{params.get('atr_sl', 1.5)}/{params.get('atr_tp', 3.0)}",
                'suggestion': 'Try 2.0/4.0 for better risk/reward',
                'reason': 'Wider stops reduce premature exits'
            })
        
        return suggestions
    
    def generate_optimization_report(self):
        """Generate comprehensive optimization report"""
        if not self.analysis_results:
            self.analyze_all_bots()
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'total_bots': len(self.bots),
            'bots_analysis': self.analysis_results,
            'summary': self.generate_summary(),
            'action_items': self.generate_action_items()
        }
        
        return report
    
    def generate_summary(self):
        """Generate executive summary"""
        total_bots = len(self.bots)
        running_bots = [b for b in self.bots if b.status == 'RUNNING']
        error_bots = [b for b in self.bots if b.status == 'ERROR']
        
        profitable_bots = 0
        for bot_id, analysis in self.analysis_results.items():
            if analysis.get('profit_factor', 0) > 1.5 and analysis.get('trades_count', 0) > 10:
                profitable_bots += 1
        
        return {
            'total_bots': total_bots,
            'running_bots': len(running_bots),
            'error_bots': len(error_bots),
            'profitable_bots': profitable_bots,
            'error_rate': (len(error_bots) / total_bots * 100) if total_bots > 0 else 0,
            'profitability_rate': (profitable_bots / len(running_bots) * 100) if running_bots else 0
        }
    
    def generate_action_items(self):
        """Generate prioritized action items"""
        action_items = []
        
        # Priority 1: Fix ERROR bots
        error_bots = [b for b in self.bots if b.status == 'ERROR']
        for bot in error_bots:
            action_items.append({
                'priority': 'CRITICAL',
                'action': f'Fix ERROR bot: {bot.name}',
                'reason': f'Error: {bot.last_error[:100] if bot.last_error else "Unknown error"}',
                'estimated_effort': '1-2 hours'
            })
        
        # Priority 2: Poor performing bots
        for bot_id, analysis in self.analysis_results.items():
            if analysis.get('profit_factor', 0) < 1.0 and analysis.get('trades_count', 0) > 10:
                bot = LiveBot.objects.get(id=bot_id)
                action_items.append({
                    'priority': 'HIGH',
                    'action': f'Optimize poorly performing bot: {bot.name}',
                    'reason': f'Profit factor: {analysis["profit_factor"]:.2f}, Win rate: {analysis["win_rate"]:.1f}%',
                    'estimated_effort': '2-4 hours'
                })
        
        # Priority 3: Missing risk management
        for bot in self.bots:
            params = bot.parameters or {}
            if bot.strategy_type == 'GRID' and not params.get('global_stop_loss'):
                action_items.append({
                    'priority': 'MEDIUM',
                    'action': f'Add stop loss to grid bot: {bot.name}',
                    'reason': 'No global stop loss configured',
                    'estimated_effort': '30 minutes'
                })
        
        return action_items


class StrategyOptimizer:
    """Optimize trading strategies using historical data"""
    
    def __init__(self):
        self.strategies = {
            'DAYTRADING': DayTradingStrategy,
            'GRID': GridStrategy
        }
    
    def optimize_daytrading_parameters(self, historical_data, initial_params=None):
        """Optimize DayTrading strategy parameters using grid search"""
        print("\nOptimizing DayTrading parameters...")
        
        # Default parameter ranges
        param_ranges = {
            'ema_fast': [5, 9, 12],
            'ema_med': [15, 21, 26],
            'ema_slow': [30, 50, 60],
            'ema_trend': [100, 200, 300],
            'rsi_period': [7, 14, 21],
            'rsi_buy': [55, 60, 65],
            'rsi_sell': [35, 40, 45],
            'atr_sl': [1.0, 1.5, 2.0],
            'atr_tp': [2.0, 3.0, 4.0]
        }
        
        # Simple optimization (for demonstration)
        # In production, use more sophisticated methods like genetic algorithms
        best_score = -float('inf')
        best_params = initial_params or {}
        
        # Test a few combinations
        test_combinations = [
            {'rsi_buy': 60, 'rsi_sell': 40, 'atr_sl': 2.0, 'atr_tp': 4.0},
            {'rsi_buy': 65, 'rsi_sell': 35, 'atr_sl': 1.5, 'atr_tp': 3.0},
            {'rsi_buy': 58, 'rsi_sell': 42, 'atr_sl': 1.8, 'atr_tp': 3.6}
        ]
        
        for params in test_combinations:
            print(f"  Testing params: {params}")
            # In a real implementation, you would run backtest here
            # score = self.run_backtest(historical_data, params)
            score = np.random.random()  # Placeholder
        
        print("Optimization complete!")
        return best_params
    
    def optimize_grid_parameters(self, price_data, initial_params=None):
        """Optimize Grid strategy parameters"""
        print("\nOptimizing Grid parameters...")
        
        # Analyze price data
        recent_prices = price_data['close'].tail(100)
        current_price = recent_prices.iloc[-1]
        volatility = recent_prices.pct_change().std()
        
        # Calculate optimal grid based on volatility
        atr = price_data['high'].tail(14).max() - price_data['low'].tail(14).min()
        grid_spacing = atr * 1.5
        
        # Determine grid boundaries
        upper_bound = recent_prices.max() * 1.02
        lower_bound = recent_prices.min() * 0.98
        
        # Calculate optimal number of levels
        price_range = upper_bound - lower_bound
        optimal_levels = max(5, min(10, int(price_range / grid_spacing)))
        
        optimized_params = {
            'upper_price': float(upper_bound),
            'lower_price': float(lower_bound),
            'grid_levels': optimal_levels,
            'amount_per_level': 100,  # Default
            'global_stop_loss': float(lower_bound * 0.95),
            'grid_spacing': float(grid_spacing)
        }
        
        print(f"  Current price: ${current_price:.2f}")
        print(f"  Suggested grid: ${lower_bound:.2f} - ${upper_bound:.2f}")
        print(f"  Levels: {optimal_levels}, Spacing: ${grid_spacing:.2f}")
        
        return optimized_params


def main():
    """Main function"""
    print("="*80)
    print("CRYPTO TRADING DASHBOARD - STRATEGY OPTIMIZER")
    print("="*80)
    
    # Initialize analyzer
    analyzer = StrategyAnalyzer()
    
    # Analyze all bots
    print("\n1. Analyzing bot performance...")
    analysis_results = analyzer.analyze_all_bots()
    
    # Generate report
    print("\n2. Generating optimization report...")
    report = analyzer.generate_optimization_report()
    
    # Print summary
    summary = report['summary']
    print(f"\nSystem Summary:")
    print(f"  Total bots: {summary['total_bots']}")
    print(f"  Running bots: {summary['running_bots']}")
    print(f"  Error bots: {summary['error_bots']} ({summary['error_rate']:.1f}%)")
    print(f"  Profitable bots: {summary['profitable_bots']} ({summary['profitability_rate']:.1f}%)")
    
    # Print action items
    print("\n3. Action Items (Prioritized):")
    for i, item in enumerate(report['action_items'][:5], 1):
        print(f"\n  {i}. [{item['priority']}] {item['action']}")
        print(f"     Reason: {item['reason']}")
        print(f"     Effort: {item['estimated_effort']}")
    
    # Save report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_filename = f"strategy_optimization_report_{timestamp}.json"
    
    with open(report_filename, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"\n4. Report saved to: {report_filename}")
    
    # Generate specific recommendations
    print("\n5. Specific Recommendations:")
    
    optimizer = StrategyOptimizer()
    
    for bot in LiveBot.objects.all():
        if bot.status == 'RUNNING' and bot.strategy_type == 'GRID':
            print(f"\n  Grid Bot '{bot.name}':")
            params = bot.parameters or {}
            current_levels = params.get('grid_levels', 'Not set')
            print(f"    Current levels: {current_levels}")
            print(f"    Recommendation: Use 5-7 levels with ATR-based spacing")
        
        elif bot.status == 'RUNNING' and bot.strategy_type == 'DAYTRADING':
            print(f"\n  Day Trading Bot '{bot.name}':")
            params = bot.parameters or {}
            rsi_buy = params.get('rsi_buy', 55)
            rsi_sell = params.get('rsi_sell', 45)
            print(f"    Current RSI: Buy={rsi_buy}, Sell={rsi_sell}")
            print(f"    Recommendation: Try Buy=60, Sell=40 for stronger signals")
    
    print("\n" + "="*80)
    print("OPTIMIZATION COMPLETE")
    print("="*80)
    
    # Final recommendations
    print("\nNext Steps:")
    print("1. Fix ERROR state bots immediately")
    print("2. Optimize Day Trading RSI thresholds (60/40)")
    print("3. Add stop losses to Grid bots")
    print("4. Run backtests with optimized parameters")
    print("5. Implement gradual position size increases for profitable bots")


if __name__ == "__main__":
    main()