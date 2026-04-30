from django.db.models import Avg, Count, Q
from .models import WhaleWallet, WhaleTransaction, ShadowTrade
import json

class WhaleAnalysisEngine:
    @staticmethod
    def analyze_success_correlation(wallet_id=None, symbol=None):
        """
        Analiza qué indicadores tuvieron mejores resultados sin depender de pandas.
        """
        # Incluimos trades para dar feedback temprano
        trades = ShadowTrade.objects.filter(wallet_id=wallet_id).select_related('wallet')
        
        if symbol:
            trades = trades.filter(token_symbol=symbol)
            
        data = []
        missing_context_count = 0
        
        for trade in trades:
            # PNL actual (el tracker de PnL mantiene esto actualizado)
            pnl = float(trade.pnl_percent or 0)
            
            # Buscamos la transacción original para ver el contexto
            tx = WhaleTransaction.objects.filter(
                wallet=trade.wallet,
                to_asset=trade.token_symbol,
                timestamp__lte=trade.created_at
            ).order_by('-timestamp').first()
            
            if tx and tx.raw_data and 'market_context' in tx.raw_data:
                ctx = tx.raw_data['market_context']
                data.append({
                    'symbol': trade.token_symbol,
                    'pnl': pnl,
                    'rsi': ctx.get('rsi_14'),
                    'vol_ratio': ctx.get('volume_ratio'),
                    'macd_cross': ctx.get('macd_cross'),
                    'bb_pos': ctx.get('bb_position'),
                    'in_uptrend': ctx.get('in_uptrend')
                })
            else:
                missing_context_count += 1
        
        if not data:
            if trades.count() == 0:
                return {'error': 'Aún no tienes Shadow Trades registrados para esta ballena.'}
            if missing_context_count > 0:
                return {'error': f'Se encontraron {missing_context_count} trades, pero ninguno tiene historial de indicadores (Market Context).'}
            return {'error': 'Datos insuficientes para generar el análisis.'}
            
        # --- Análisis Manual (Sin Pandas) ---
        
        # 1. Definir Rangos de RSI
        rsi_ranges = {
            'Oversold (<30)': [],
            'Low (30-45)': [],
            'Mid (45-60)': [],
            'High (60-75)': [],
            'Overbought (>75)': []
        }
        
        for d in data:
            rsi = d['rsi']
            if rsi is None: continue
            
            if rsi < 30: rsi_ranges['Oversold (<30)'].append(d['pnl'])
            elif rsi < 45: rsi_ranges['Low (30-45)'].append(d['pnl'])
            elif rsi < 60: rsi_ranges['Mid (45-60)'].append(d['pnl'])
            elif rsi < 75: rsi_ranges['High (60-75)'].append(d['pnl'])
            else: rsi_ranges['Overbought (>75)'].append(d['pnl'])
            
        rsi_analysis = []
        for label, pnls in rsi_ranges.items():
            if not pnls: continue
            win_rate = (sum(1 for p in pnls if p > 0) / len(pnls)) * 100
            avg_pnl = sum(pnls) / len(pnls)
            rsi_analysis.append({
                'range': label,
                'count': len(pnls),
                'win_rate': round(win_rate, 1),
                'avg_pnl': round(avg_pnl, 2)
            })
            
        # 2. Análisis de Tendencia
        uptrend_pnls = [d['pnl'] for d in data if d.get('in_uptrend') is True]
        stats_uptrend = {
            'count': len(uptrend_pnls),
            'mean': round(sum(uptrend_pnls)/len(uptrend_pnls), 2) if uptrend_pnls else 0
        }
        
        return {
            'total_samples': len(data),
            'rsi_correlation': rsi_analysis,
            'uptrend_stats': {True: stats_uptrend},
            'best_indicator': WhaleAnalysisEngine._identify_best_pattern(data)
        }

    @staticmethod
    def _identify_best_pattern(data):
        """Identifica el patrón con mayor Win Rate (Pure Python)."""
        # Candidato 1: RSI bajo
        oversold = [d['pnl'] for d in data if d['rsi'] is not None and d['rsi'] < 40]
        if len(oversold) >= 3:
            wr = sum(1 for p in oversold if p > 0) / len(oversold)
            if wr > 0.6: return f"RSI Bajo (<40) con {round(wr*100)}% Win Rate"
            
        # Candidato 2: Volumen alto
        high_vol = [d['pnl'] for d in data if d['vol_ratio'] is not None and d['vol_ratio'] > 2.0]
        if len(high_vol) >= 3:
            wr = sum(1 for p in high_vol if p > 0) / len(high_vol)
            if wr > 0.6: return f"Pico de Volumen (>2x) con {round(wr*100)}% Win Rate"
            
        return "Datos insuficientes para patrón estadístico"

    @staticmethod
    def get_predictive_score(wallet_id, symbol, current_context):
        """
        Devuelve un score de confianza (0-1) basado en si el contexto actual
        coincide con los mejores trades históricos de esta ballena.
        """
        if not current_context or not isinstance(current_context, dict):
            return 0.5 # Neutral si no hay contexto
            
        analysis = WhaleAnalysisEngine.analyze_success_correlation(wallet_id=wallet_id)
        if 'error' in analysis:
            return 0.5 
            
        score = 0.5
        factors = 0
        
        # 1. RSI Match
        current_rsi = current_context.get('rsi_14')
        if current_rsi and analysis.get('rsi_correlation'):
            for r in analysis['rsi_correlation']:
                # Extraer rango numérico de la etiqueta
                try:
                    if 'Oversold' in r['range'] and current_rsi < 35:
                        if r['win_rate'] > 60: score += 0.2; factors += 1
                    elif 'High' in r['range'] and current_rsi > 65:
                        if r['win_rate'] > 60: score += 0.2; factors += 1
                except: pass
                
        # 2. Trend Match
        current_trend = current_context.get('in_uptrend')
        if current_trend is not None and analysis.get('uptrend_stats'):
            stats = analysis['uptrend_stats'].get(current_trend)
            if stats and stats['mean'] > 0: # PnL promedio positivo en esta tendencia
                score += 0.15; factors += 1
                
        # Normalizar score entre 0.1 y 0.95
        final_score = max(0.1, min(0.95, score))
        return final_score

    @staticmethod
    def analyze_token_performance(wallet_id):
        """
        Calcula win rate y PnL por token para una ballena.
        NO requiere market_context — usa directamente ShadowTrade + WhaleTransaction.
        
        Returns:
            list of dicts: [{token, trades, wins, win_rate, avg_pnl, last_trade}]
        """
        from .models import ShadowTrade, WhaleTransaction
        from django.utils import timezone
        from django.db.models import Avg, Count, Q
        
        results = {}

        # 1. Datos desde ShadowTrades cerrados (más confiables, tienen PnL real)
        shadow_trades = ShadowTrade.objects.filter(wallet_id=wallet_id, status='CLOSED')
        for st in shadow_trades:
            token = (st.token_symbol or '').upper().strip()
            if not token:
                continue
            if token not in results:
                results[token] = {'token': token, 'trades': 0, 'wins': 0, 'pnls': [], 'last_trade': None}
            results[token]['trades'] += 1
            pnl = float(st.pnl_percent or 0)
            results[token]['pnls'].append(pnl)
            if pnl > 0:
                results[token]['wins'] += 1
            if results[token]['last_trade'] is None or (st.closed_at and st.closed_at > results[token]['last_trade']):
                results[token]['last_trade'] = st.closed_at

        # 2. Si hay pocos shadow trades, enriquecer con WhaleTransactions (proxy)
        if sum(v['trades'] for v in results.values()) < 5:
            txs = WhaleTransaction.objects.filter(
                wallet_id=wallet_id,
                tx_type__in=['BUY', 'SWAP', 'UNKNOWN']
            ).order_by('-timestamp')[:100]
            
            for tx in txs:
                token = (tx.to_asset or '').upper().strip()
                if not token or token in ('USDT', 'USDC', 'DAI', 'BUSD'):
                    continue
                if token not in results:
                    results[token] = {'token': token, 'trades': 0, 'wins': 0, 'pnls': [], 'last_trade': None}
                # Solo contamos como trade, sin PnL (no disponible desde TX directamente)
                results[token]['trades'] += 1
                if results[token]['last_trade'] is None or (tx.timestamp and tx.timestamp > results[token]['last_trade']):
                    results[token]['last_trade'] = tx.timestamp

        # Calcular métricas finales
        output = []
        for token, data in results.items():
            win_rate = round((data['wins'] / data['trades']) * 100, 1) if data['trades'] > 0 else 0
            avg_pnl = round(sum(data['pnls']) / len(data['pnls']), 2) if data['pnls'] else None
            output.append({
                'token': token,
                'trades': data['trades'],
                'wins': data['wins'],
                'win_rate': win_rate,
                'avg_pnl': avg_pnl,
                'last_trade': data['last_trade'].strftime('%d/%m %H:%M') if data['last_trade'] else None,
            })
        
        # Ordenar por número de trades descendente
        output.sort(key=lambda x: x['trades'], reverse=True)
        return output[:15]  # Top 15 tokens

    @staticmethod
    def classify_behavior(wallet_id):
        """
        Clasifica el comportamiento de la ballena:
        - ACUMULADOR: mayormente compras, pocas ventas
        - TRADER: alta rotación buy/sell balanceada
        - DISTRIBUIDOR: más ventas que compras
        - OBSERVACION: pocos datos
        
        También calcula holding time promedio, RSI promedio de compra, 
        y horario de mayor actividad.
        
        Returns dict con: mode, buy_ratio, avg_holding_hours, 
                          preferred_rsi, active_hours, tx_count
        """
        from .models import WhaleTransaction, ShadowTrade
        from django.utils import timezone
        from collections import Counter
        import math
        
        txs = WhaleTransaction.objects.filter(wallet_id=wallet_id).order_by('timestamp')
        tx_count = txs.count()
        
        if tx_count < 3:
            return {
                'mode': 'OBSERVACION',
                'mode_label': 'En Observación',
                'mode_icon': '👁️',
                'mode_color': '#6c757d',
                'buy_ratio': None,
                'avg_holding_hours': None,
                'preferred_rsi': None,
                'active_hours': [],
                'tx_count': tx_count,
                'description': 'Pocas transacciones para clasificar.',
                'top_indicators': []
            }
        
        # Contar BUY vs SELL
        buy_types = ['BUY', 'SWAP']
        sell_types = ['SELL', 'TRANSFER']
        
        buys = txs.filter(tx_type__in=buy_types).count()
        sells = txs.filter(tx_type__in=sell_types).count()
        
        # También inferir por from_asset/to_asset para SWAP/UNKNOWN
        unknown_txs = txs.filter(tx_type='UNKNOWN')
        for tx in unknown_txs:
            if tx.to_asset and tx.to_asset.upper() not in ('USDT', 'USDC', 'SOL', 'ETH'):
                buys += 1  # Comprando un token
            elif tx.from_asset and tx.from_asset.upper() not in ('USDT', 'USDC', 'SOL', 'ETH'):
                sells += 1  # Vendiendo un token
        
        total_classified = buys + sells
        buy_ratio = buys / total_classified if total_classified > 0 else 0.5
        
        # Clasificar modo
        if tx_count < 5:
            mode = 'OBSERVACION'
            mode_label = 'En Observación'
            mode_icon = '👁️'
            mode_color = '#6c757d'
        elif buy_ratio >= 0.75:
            mode = 'ACUMULADOR'
            mode_label = 'Acumulador DCA'
            mode_icon = '🏦'
            mode_color = '#0dcaf0'
        elif buy_ratio <= 0.35:
            mode = 'DISTRIBUIDOR'
            mode_label = 'Distribución'
            mode_icon = '📤'
            mode_color = '#dc3545'
        elif tx_count >= 15:
            mode = 'TRADER'
            mode_label = 'Trader Activo'
            mode_icon = '⚡'
            mode_color = '#ffc107'
        else:
            mode = 'SWING'
            mode_label = 'Swing Trader'
            mode_icon = '🌊'
            mode_color = '#6f42c1'
        
        # Holding time desde shadow trades cerrados
        closed_trades = ShadowTrade.objects.filter(wallet_id=wallet_id, status='CLOSED')
        holding_hours_list = []
        for st in closed_trades:
            if st.closed_at and st.created_at:
                delta = (st.closed_at - st.created_at).total_seconds() / 3600
                if 0 < delta < 720:
                    holding_hours_list.append(delta)
        avg_holding = round(sum(holding_hours_list) / len(holding_hours_list), 1) if holding_hours_list else None
        
        # RSI promedio de compra (desde market_context si existe)
        rsi_values = []
        for tx in txs.filter(tx_type__in=['BUY', 'SWAP'])[:50]:
            rd = tx.raw_data or {}
            ctx = rd.get('market_context', {})
            if ctx.get('rsi_14'):
                try:
                    rsi_values.append(float(ctx['rsi_14']))
                except Exception:
                    pass
        preferred_rsi = round(sum(rsi_values) / len(rsi_values), 1) if rsi_values else None
        
        # Horas de mayor actividad
        hour_counts = Counter()
        for tx in txs:
            if tx.timestamp:
                hour_counts[tx.timestamp.hour] += 1
        active_hours = [h for h, _ in hour_counts.most_common(3)]
        
        # Top indicadores (desde market_context)
        indicator_hits = Counter()
        for tx in txs.filter(tx_type__in=['BUY', 'SWAP'])[:50]:
            rd = tx.raw_data or {}
            ctx = rd.get('market_context', {})
            if ctx.get('rsi_14') and ctx['rsi_14'] < 40:
                indicator_hits['RSI Bajo (<40)'] += 1
            if ctx.get('volume_ratio') and ctx['volume_ratio'] > 1.5:
                indicator_hits['Vol. Alto (>1.5x)'] += 1
            if ctx.get('macd_cross') == 'bullish':
                indicator_hits['MACD Bullish'] += 1
            if ctx.get('in_uptrend') is True:
                indicator_hits['Tendencia Alcista'] += 1
            if ctx.get('bb_position') and ctx['bb_position'] < 0.3:
                indicator_hits['BB Bajo (<0.3)'] += 1
        top_indicators = [ind for ind, _ in indicator_hits.most_common(3)]
        
        description_map = {
            'ACUMULADOR': f'Compra de forma progresiva ({round(buy_ratio*100)}% compras). Estrategia DCA.',
            'TRADER': f'Alta rotación buy/sell. {tx_count} txs totales.',
            'DISTRIBUIDOR': f'En fase de venta ({round((1-buy_ratio)*100)}% ventas).',
            'SWING': f'Posiciones de mediano plazo. Hold promedio: {avg_holding}h.' if avg_holding else 'Swing trader con pocas operaciones.',
            'OBSERVACION': 'Pocos datos disponibles.',
        }
        
        return {
            'mode': mode,
            'mode_label': mode_label,
            'mode_icon': mode_icon,
            'mode_color': mode_color,
            'buy_ratio': round(buy_ratio * 100, 1),
            'avg_holding_hours': avg_holding,
            'preferred_rsi': preferred_rsi,
            'active_hours': active_hours,
            'tx_count': tx_count,
            'description': description_map.get(mode, ''),
            'top_indicators': top_indicators,
        }

    @staticmethod
    def suggest_bot_params(wallet_id, token_symbol=None):
        """
        Analiza el historial de una ballena y sugiere parámetros para crear un bot.
        Devuelve parámetros para GRID y DayTrading basados en datos reales.
        """
        from .models import WhaleTransaction

        txs = WhaleTransaction.objects.filter(
            wallet_id=wallet_id
        ).filter(
            Q(tx_type='BUY') | Q(tx_type='SWAP') | Q(tx_type='UNKNOWN')
        ).order_by('-timestamp')

        if token_symbol:
            txs = txs.filter(to_asset__iexact=token_symbol)

        # Si aún no hay transacciones o el filtro por token las vació, 
        # intentar buscar BUYS genéricas si no se especificó un token
        if not txs.exists():
            return {'error': 'No hay transacciones de compra o intercambio registradas para esta ballena. Asegúrate de haber realizado un Deep Sync para procesar el historial.'}

        # Extraer precios de entrada desde raw_data
        entry_prices = []
        rsi_values = []
        holding_hours = []
        tokens_freq = {}

        for tx in txs[:50]:  # Limitar a 50 más recientes
            rd = tx.raw_data or {}
            # Precio de entrada
            price = None
            if 'priceUsd' in rd:
                try:
                    price = float(rd['priceUsd'])
                except Exception:
                    pass
            elif 'px' in rd:
                try:
                    price = float(rd['px'])
                except Exception:
                    pass

            if price and price > 0:
                entry_prices.append(price)

            # RSI del momento de la compra
            ctx = rd.get('market_context', {})
            if ctx.get('rsi_14'):
                try:
                    rsi_values.append(float(ctx['rsi_14']))
                except Exception:
                    pass

            # Frecuencia de tokens
            sym = tx.to_asset
            if sym:
                tokens_freq[sym] = tokens_freq.get(sym, 0) + 1

        # Holding time desde Shadow Trades cerrados
        closed_trades = ShadowTrade.objects.filter(
            wallet_id=wallet_id, status='CLOSED'
        )
        if token_symbol:
            closed_trades = closed_trades.filter(token_symbol__iexact=token_symbol)

        for st in closed_trades:
            if st.closed_at and st.created_at:
                delta = (st.closed_at - st.created_at).total_seconds() / 3600
                if 0 < delta < 720:  # Entre 0 y 30 días
                    holding_hours.append(delta)

        # ---- Calcular parámetros ----
        # GRID
        if entry_prices:
            sorted_prices = sorted(entry_prices)
            n = len(sorted_prices)
            # Percentil 10 → lower, Percentil 90 → upper
            lower = sorted_prices[max(0, int(n * 0.10))]
            upper = sorted_prices[min(n - 1, int(n * 0.90))]
            # Si el rango es muy pequeño (ej: stablecoin), ampliar 5%
            if upper <= lower * 1.02:
                lower *= 0.95
                upper *= 1.05
            avg_price = sum(entry_prices) / len(entry_prices)
            # Stop loss sugerido: 8% por debajo del lower
            stop_loss = round(lower * 0.92, 6)
            grid_levels = min(10, max(5, n // 2))
        else:
            lower = upper = avg_price = stop_loss = 0
            grid_levels = 5

        # DayTrading timeframe
        if holding_hours:
            avg_hold = sum(holding_hours) / len(holding_hours)
        else:
            avg_hold = 24  # default 1 día

        if avg_hold <= 4:
            timeframe = '1h'
            tf_label = '1h (operaciones rápidas)'
        elif avg_hold <= 24:
            timeframe = '4h'
            tf_label = '4h (operaciones intradía)'
        elif avg_hold <= 72:
            timeframe = '1d'
            tf_label = '1d (swing trading)'
        else:
            timeframe = '1d'
            tf_label = '1d (posiciones largas)'

        # RSI promedio de entrada
        avg_rsi = round(sum(rsi_values) / len(rsi_values), 1) if rsi_values else 45.0

        # ---- Alpha Score (Inteligencia Predictiva) ----
        # Intentar obtener un score predictivo para el activo sugerido
        alpha_score = 0.5
        top_token = token_symbol
        if not top_token and tokens_freq:
            top_token = max(tokens_freq, key=tokens_freq.get)

        if top_token:
            from .whale_intelligence import fetch_market_context
            context = fetch_market_context(top_token)
            alpha_score = WhaleAnalysisEngine.get_predictive_score(wallet_id, top_token, context)

        return {
            'top_token': top_token or 'SOL',
            'grid': {
                'upper_price': round(upper, 6),
                'lower_price': round(lower, 6),
                'grid_levels': grid_levels,
                'stop_loss': stop_loss,
                'description': f"Basado en {len(entry_prices)} precios de entrada detectados."
            },
            'daytrading': {
                'timeframe': timeframe,
                'description': f"Hold medio: {round(avg_hold, 1)}h ({tf_label})"
            },
            'alpha_score': alpha_score
        }
