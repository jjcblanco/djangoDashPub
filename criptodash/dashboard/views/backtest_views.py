"""
Vista de backtesting.

Este módulo contiene la vista completa para ejecutar backtests sobre
estrategias de trading usando señales existentes o estrategias personalizadas.
"""

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import datetime
import pandas as pd

from ..backtester import Backtester, SignalBasedStrategy, SupertrendStrategy
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
            strategy_type = request.POST.get('strategy', 'signal-based')  # 'signal-based' o 'supertrend'

            # Convertir fechas
            start_date = timezone.make_aware(datetime.strptime(start_date_str, '%Y-%m-%d'))
            end_date = timezone.make_aware(datetime.strptime(end_date_str, '%Y-%m-%d'))

            # Crear backtester
            backtester = Backtester(initial_balance=initial_balance, commission=commission)

            # Ejecutar backtest según estrategia
            if strategy_type == 'signal-based':
                # Usar señales existentes de la BD
                results = backtester.run_backtest_from_signals(
                    pair_symbol=pair_symbol,
                    start_date=start_date,
                    end_date=end_date,
                    min_strength=min_strength
                )
            else:
                # Usar estrategia Supertrend
                strategy = SupertrendStrategy()
                results = backtester.run_backtest(
                    strategy=strategy,
                    pair_symbol=pair_symbol,
                    start_date=start_date,
                    end_date=end_date
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
                    timestamp__lte=end_date
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
                'strategy': strategy_type,
                'pairs': pairs,
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
