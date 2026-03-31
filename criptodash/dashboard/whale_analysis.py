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

        # Token más frecuente
        top_token = max(tokens_freq, key=tokens_freq.get) if tokens_freq else (token_symbol or 'N/A')
        top_token_count = tokens_freq.get(top_token, 0)

        return {
            'wallet_id': wallet_id,
            'top_token': top_token,
            'top_token_count': top_token_count,
            'total_txs_analyzed': len(entry_prices),
            'avg_entry_price': round(avg_price, 6) if entry_prices else 0,
            'avg_hold_hours': round(avg_hold, 1),
            'timeframe_label': tf_label,
            'grid': {
                'lower_price': round(lower, 6),
                'upper_price': round(upper, 6),
                'grid_levels': grid_levels,
                'global_stop_loss': stop_loss,
                'description': f"Basado en {len(entry_prices)} precios de entrada históricos"
            },
            'daytrading': {
                'timeframe': timeframe,
                'min_strength': 3,
                'min_adx': 20,
                'risk_per_trade_pct': 2.0,
                'atr_mult_sl': 1.5,
                'atr_mult_tp': 3.0,
                'cooldown_bars': 3,
                'rsi_context': avg_rsi,
                'description': f"Timeframe sugerido: {tf_label}. RSI promedio de entrada de la ballena: {avg_rsi}"
            }
        }
