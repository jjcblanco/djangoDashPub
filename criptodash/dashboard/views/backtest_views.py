"""
Vista de backtesting.

Este módulo contiene la vista completa para ejecutar backtests sobre
estrategias de trading usando señales existentes o estrategias personalizadas.
"""

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import datetime, timedelta
import pandas as pd

from ..backtester import Backtester, SignalBasedStrategy, SupertrendStrategy, DayTradingStrategy, GridStrategy
from ..models import TradingPair, TradeSignal, BacktestResult, OHLCVData


@login_required
def backtest_view(request):
    """Vista para ejecutar backtests usando señales existentes"""
    
    # Obtener pares disponibles
    pairs = TradingPair.objects.all().order_by('symbol')
    
    # Obtener resultados históricos de backtests
    historical_results = BacktestResult.objects.all().order_by('-created_at')[:10]
    
    if request.method == 'POST':
        try:
            pair_symbol = request.POST.get('pair', 'ETH/USDT')
            start_date_str = request.POST.get('start_date')
            end_date_str = request.POST.get('end_date')
            initial_balance = float(request.POST.get('initial_balance', 10000))
            commission = float(request.POST.get('commission', 0.001))
            min_strength = int(request.POST.get('min_strength', 0))
            min_adx = float(request.POST.get('min_adx', 0))
            stop_loss = request.POST.get('stop_loss')
            take_profit = request.POST.get('take_profit')
            
            # Convertir a float si existen
            stop_loss_pct = float(stop_loss) if stop_loss else None
            take_profit_pct = float(take_profit) if take_profit else None
            
            atr_mult_sl = float(request.POST.get('atr_mult_sl', 1.5))
            atr_mult_tp = float(request.POST.get('atr_mult_tp', 3.0))
            trailing_stop = request.POST.get('trailing_stop') == 'on'
            use_candles = request.POST.get('use_candles') == 'on'
            strategy_mode = request.POST.get('strategy_mode', 'balanced')
            use_bollinger_filter = request.POST.get('use_bollinger_filter') == 'on'
            risk_per_trade_pct = float(request.POST.get('risk_per_trade_pct', 2.0))

            strategy_type = request.POST.get('strategy', 'signal-based')  # 'signal-based', 'supertrend', 'day-trading', 'grid'
            timeframe = request.POST.get('timeframe', '1h')
            
            # Parámetros específicos de Grid
            upper_price = request.POST.get('upper_price')
            lower_price = request.POST.get('lower_price')
            grid_levels = request.POST.get('grid_levels', 10)
            amount_per_level = request.POST.get('amount_per_level', 100)
            global_stop_loss = request.POST.get('global_stop_loss')

            # Convertir fechas
            start_date = timezone.make_aware(datetime.strptime(start_date_str, '%Y-%m-%d'))
            # +1 día para incluir el día final completo
            end_date = timezone.make_aware(datetime.strptime(end_date_str, '%Y-%m-%d')) + timedelta(days=1)

            # Crear backtester
            backtester = Backtester(
                initial_balance=initial_balance,
                commission=commission,
                risk_per_trade_pct=risk_per_trade_pct
            )

            # Ejecutar backtest según estrategia
            if strategy_type == 'signal-based':
                # Usar señales existentes de la BD
                results = backtester.run_backtest_from_signals(
                    pair_symbol=pair_symbol,
                    start_date=start_date,
                    end_date=end_date,
                    timeframe=timeframe,
                    min_strength=min_strength,
                    min_adx=min_adx,
                    stop_loss_pct=stop_loss_pct,
                    take_profit_pct=take_profit_pct,
                    atr_mult_sl=atr_mult_sl,
                    atr_mult_tp=atr_mult_tp,
                    trailing_stop=trailing_stop
                )
            elif strategy_type == 'supertrend':
                # Usar estrategia Supertrend
                strategy = SupertrendStrategy()
                results = backtester.run_backtest(
                    strategy=strategy,
                    pair_symbol=pair_symbol,
                    start_date=start_date,
                    end_date=end_date,
                    timeframe=timeframe,
                    stop_loss_pct=stop_loss_pct,
                    take_profit_pct=take_profit_pct,
                    trailing_stop=trailing_stop,
                    atr_mult_sl=atr_mult_sl,
                    atr_mult_tp=atr_mult_tp
                )
            elif strategy_type == 'day-trading':
                # Usar estrategia Day-Trading con parámetros del usuario
                strategy_params = {
                    'min_strength': min_strength,
                    'min_adx': min_adx,
                    'atr_sl': atr_mult_sl,
                    'atr_tp': atr_mult_tp,
                    'use_candles': use_candles,
                    'strategy_mode': strategy_mode,
                    'use_bollinger_filter': use_bollinger_filter,
                    'risk_per_trade_pct': risk_per_trade_pct
                }
                strategy = DayTradingStrategy(parameters=strategy_params)
                results = backtester.run_backtest(
                    strategy=strategy,
                    pair_symbol=pair_symbol,
                    start_date=start_date,
                    end_date=end_date,
                    timeframe=timeframe,
                    stop_loss_pct=stop_loss_pct,
                    take_profit_pct=take_profit_pct,
                    trailing_stop=trailing_stop,
                    atr_mult_sl=atr_mult_sl,
                    atr_mult_tp=atr_mult_tp
                )
            elif strategy_type == 'grid':
                # Estrategia de Grid Trading
                grid_params = {
                    'upper_price': float(upper_price) if upper_price else 0,
                    'lower_price': float(lower_price) if lower_price else 0,
                    'grid_levels': int(grid_levels),
                    'amount_per_level': float(amount_per_level),
                    'global_stop_loss': float(global_stop_loss) if global_stop_loss else None
                }
                strategy = GridStrategy(parameters=grid_params)
                results = backtester.run_backtest(
                    strategy=strategy,
                    pair_symbol=pair_symbol,
                    start_date=start_date,
                    end_date=end_date,
                    timeframe=timeframe
                )

            # Verificar si hubo error
            if 'error' in results:
                messages.error(request, f"Error en backtest: {results['error']}")
                return render(request, 'dashboard/backtest.html', {
                    'pairs': pairs,
                    'historical_results': historical_results
                })

            # Generar gráficos
            equity_chart = backtester.generate_equity_chart(results)
            
            # Obtener datos OHLCV para el gráfico de trades
            try:
                pair = TradingPair.objects.get(symbol=pair_symbol)
                ohlcv_data = OHLCVData.objects.filter(
                    pair=pair,
                    timestamp__gte=start_date,
                    timestamp__lte=end_date,
                    timeframe=timeframe
                ).order_by('timestamp')
                
                if ohlcv_data.exists():
                    df_price = pd.DataFrame(list(ohlcv_data.values(
                        'timestamp', 'open', 'high', 'low', 'close', 'volume'
                    )))
                    df_price['timestamp'] = pd.to_datetime(df_price['timestamp'])
                    for col in ['open', 'high', 'low', 'close']:
                        df_price[col] = df_price[col].astype(float)
                else:
                    df_price = None
            except:
                df_price = None
            
            trades_chart = backtester.generate_trades_chart(results, df_price)

            # Preparar datos de trades para la tabla
            trades_list = results.get('trades', [])
            
            # Formatear trades para mostrar
            formatted_trades = []
            buy_trades = [t for t in trades_list if t['action'] == 'BUY']
            sell_trades = [t for t in trades_list if t['action'] == 'SELL']
            
            for i in range(min(len(buy_trades), len(sell_trades))):
                buy = buy_trades[i]
                sell = sell_trades[i]
                
                pnl = sell.get('pnl', 0)
                pnl_pct = sell.get('pnl_pct', 0)
                
                formatted_trades.append({
                    'entry_time': buy['timestamp'],
                    'exit_time': sell['timestamp'],
                    'entry_price': buy['price'],
                    'exit_price': sell['price'],
                    'size': buy['size'],
                    'strength': buy.get('strength', 0),
                    'pnl': pnl,
                    'pnl_pct': pnl_pct,
                    'reason': sell.get('reason', 'SIGNAL'),
                    'sl_price': buy.get('sl_price'),
                    'tp_price': buy.get('tp_price'),
                    'result': 'Win' if pnl > 0 else 'Loss'
                })

            context = {
                'results': results,
                'equity_chart': equity_chart,
                'trades_chart': trades_chart,
                'trades': formatted_trades,
                'pair': pair_symbol,
                'start_date': start_date_str,
                'end_date': end_date_str,
                'initial_balance': initial_balance,
                'commission': commission,
                'min_strength': min_strength,
                'min_adx': min_adx,
                'stop_loss_pct': stop_loss_pct,
                'take_profit_pct': take_profit_pct,
                'atr_mult_sl': atr_mult_sl,
                'atr_mult_tp': atr_mult_tp,
                'trailing_stop': trailing_stop,
                'use_candles': use_candles,
                'strategy_mode': strategy_mode,
                'use_bollinger_filter': use_bollinger_filter,
                'strategy': strategy_type,
                'timeframe': timeframe,
                'pairs': pairs,
                # More grid params for context
                'upper_price': upper_price,
                'lower_price': lower_price,
                'grid_levels': grid_levels,
                'amount_per_level': amount_per_level,
                'global_stop_loss': global_stop_loss,
                'historical_results': historical_results
            }

            messages.success(request, f"Backtest completado exitosamente. Retorno total: {results['total_return']:.2f}%")
            return render(request, 'dashboard/backtest_results.html', context)

        except Exception as e:
            import traceback
            traceback.print_exc()
            messages.error(request, f"Error ejecutando backtest: {str(e)}")
            return render(request, 'dashboard/backtest.html', {
                'pairs': pairs,
                'historical_results': historical_results
            })

    return render(request, 'dashboard/backtest.html', {
        'pairs': pairs,
        'historical_results': historical_results
    })
