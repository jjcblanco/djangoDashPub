"""
Whale Analysis Engine - Fase 2 de Whale Intelligence.
Calcula la correlación entre indicadores técnicos y el éxito de los trades.
"""

from django.db.models import Avg, Count, Q
from .models import WhaleWallet, WhaleTransaction, ShadowTrade
import pandas as pd
import numpy as np

class WhaleAnalysisEngine:
    @staticmethod
    def analyze_success_correlation(wallet_id=None, symbol=None):
        """
        Analiza qué indicadores tuvieron mejores resultados.
        Filtra por wallet_id o symbol si se proporcionan.
        """
        # AHORA: Incluimos trades abiertos para dar feedback temprano
        trades = ShadowTrade.objects.filter(wallet_id=wallet_id).select_related('wallet')
        
        if symbol:
            trades = trades.filter(token_symbol=symbol)
            
        data = []
        missing_context_count = 0
        
        for trade in trades:
            # PNL: Si está cerrado usamos el real, si está abierto estimamos
            if trade.status == 'CLOSED':
                pnl = float(trade.pnl_percent or 0)
            else:
                # Estimación simple (esto se podría mejorar con fetch_current_price)
                pnl = float(trade.pnl_percent or 0) # El tracker de PnL ya actualiza este campo periódicamente
            
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
                return {'error': f'Se encontraron {missing_context_count} trades, pero ninguno tiene "Market Context". Asegúrate de que las monedas estén en Binance.'}
            return {'error': 'Datos insuficientes para generar el análisis.'}
            
        df = pd.DataFrame(data)
        
        # Análisis por rangos de RSI
        rsi_analysis = []
        bins = [0, 30, 45, 60, 75, 100]
        labels = ['Oversold (<30)', 'Low (30-45)', 'Mid (45-60)', 'High (60-75)', 'Overbought (>75)']
        df['rsi_range'] = pd.cut(df['rsi'], bins=bins, labels=labels)
        
        for name, group in df.groupby('rsi_range', observed=True):
            win_rate = (group['pnl'] > 0).mean() * 100
            avg_pnl = group['pnl'].mean()
            rsi_analysis.append({
                'range': name,
                'count': len(group),
                'win_rate': round(win_rate, 1),
                'avg_pnl': round(avg_pnl, 2)
            })
            
        # Análisis por tendencia
        uptrend_analysis = df.groupby('in_uptrend', observed=True)['pnl'].agg(['count', 'mean']).to_dict('index')
        
        return {
            'total_samples': len(df),
            'rsi_correlation': rsi_analysis,
            'uptrend_stats': uptrend_analysis,
            'best_indicator': WhaleAnalysisEngine._identify_best_pattern(df)
        }

    @staticmethod
    def _identify_best_pattern(df):
        """Identifica el patrón con mayor Win Rate y N suficiente."""
        # Candidato 1: RSI bajo
        oversold = df[df['rsi'] < 40]
        if len(oversold) >= 3:
            wr = (oversold['pnl'] > 0).mean()
            if wr > 0.6: return f"RSI Bajo (<40) con {round(wr*100)}% Win Rate"
            
        # Candidato 2: Volumen alto
        high_vol = df[df['vol_ratio'] > 2.0]
        if len(high_vol) >= 3:
            wr = (high_vol['pnl'] > 0).mean()
            if wr > 0.6: return f"Pico de Volumen (>2x) con {round(wr*100)}% Win Rate"
            
        return "Datos insuficientes para patrón estadístico"
