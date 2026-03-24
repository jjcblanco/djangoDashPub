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
                timestamp__lte=trade.entry_at
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
