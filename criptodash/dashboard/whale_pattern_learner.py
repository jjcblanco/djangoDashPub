"""
Whale Pattern Learner - Aprende patrones de trades exitosos de ballenas.
"""
import numpy as np
import pandas as pd
from django.db.models import Count, Avg, Q
from datetime import datetime, timedelta
import logging
from .models import ShadowTrade, WhalePattern

logger = logging.getLogger(__name__)

class WhalePatternLearner:
    """
    Aprende patrones de indicadores técnicos que correlacionan con trades exitosos.
    """
    
    # Definición de rangos para cada indicador
    INDICATOR_RANGES = {
        'rsi_14': [
            ('oversold', lambda x: x < 30),
            ('low', lambda x: 30 <= x < 45),
            ('mid', lambda x: 45 <= x < 60),
            ('high', lambda x: 60 <= x < 75),
            ('overbought', lambda x: x >= 75),
        ],
        'volume_ratio': [
            ('very_low', lambda x: x < 0.5),
            ('low', lambda x: 0.5 <= x < 0.8),
            ('normal', lambda x: 0.8 <= x < 1.2),
            ('high', lambda x: 1.2 <= x < 2.0),
            ('very_high', lambda x: x >= 2.0),
        ],
        'bb_position': [
            ('lower_band', lambda x: x < 0.2),
            ('lower_mid', lambda x: 0.2 <= x < 0.4),
            ('middle', lambda x: 0.4 <= x < 0.6),
            ('upper_mid', lambda x: 0.6 <= x < 0.8),
            ('upper_band', lambda x: x >= 0.8),
        ],
        'in_uptrend': [
            ('uptrend', lambda x: x is True),
            ('downtrend', lambda x: x is False),
        ],
        'macd_cross': [
            ('bullish', lambda x: x == 'bullish'),
            ('bearish', lambda x: x == 'bearish'),
        ],
        'price_vs_sma50': [
            ('below', lambda x: x is not None and x < 0),
            ('above', lambda x: x is not None and x >= 0),
        ],
        'atr_pct': [
            ('low_vol', lambda x: x is not None and x < 1.0),
            ('medium_vol', lambda x: x is not None and 1.0 <= x < 3.0),
            ('high_vol', lambda x: x is not None and x >= 3.0),
        ],
    }
    
    @classmethod
    def analyze_trades(cls, min_trades=5, min_win_rate=0.6):
        """
        Analiza todos los trades cerrados y genera patrones.
        
        Args:
            min_trades: Mínimo número de trades para considerar un patrón
            min_win_rate: Tasa de aciertos mínima para considerar exitoso
            
        Returns:
            Lista de patrones encontrados
        """
        trades = ShadowTrade.objects.filter(
            status='CLOSED',
            market_context__isnull=False
        ).select_related('wallet')
        
        if trades.count() < min_trades:
            logger.warning(f"Insuficientes trades cerrados: {trades.count()}")
            return []
        
        # Convertir a DataFrame para análisis
        data = []
        for trade in trades:
            if not trade.market_context:
                continue
            ctx = trade.market_context
            row = {
                'trade_id': trade.id,
                'symbol': trade.token_symbol,
                'pnl': trade.pnl_percent,
                'win': 1 if trade.pnl_percent > 0 else 0,
                'wallet_id': trade.wallet_id,
                'created_at': trade.created_at,
            }
            # Añadir todos los indicadores del contexto
            for key, val in ctx.items():
                row[key] = val
            data.append(row)
        
        if not data:
            return []
        
        df = pd.DataFrame(data)
        
        # Asignar rangos a cada indicador
        for indicator, ranges in cls.INDICATOR_RANGES.items():
            if indicator not in df.columns:
                continue
            df[f'{indicator}_range'] = df[indicator].apply(
                lambda x: cls._get_range_label(x, ranges)
            )
        
        # Buscar combinaciones de rangos que tengan alta win rate
        patterns = cls._find_patterns(df, min_trades, min_win_rate)
        
        # Guardar patrones en la base de datos
        saved_patterns = cls._save_patterns(patterns)
        
        return saved_patterns
    
    @staticmethod
    def _get_range_label(value, ranges):
        """Devuelve la etiqueta del rango para un valor dado."""
        if value is None:
            return None
        for label, condition in ranges:
            if condition(value):
                return label
        return None
    
    @classmethod
    def _find_patterns(cls, df, min_trades, min_win_rate):
        """
        Encuentra patrones (combinaciones de rangos) con alta win rate.
        """
        patterns = []
        
        # Considerar cada indicador individualmente primero
        range_columns = [col for col in df.columns if col.endswith('_range')]
        
        # Para cada combinación de 2 indicadores
        for i, col1 in enumerate(range_columns):
            # Patrones de un solo indicador
            patterns.extend(cls._analyze_single_indicator(df, col1, min_trades, min_win_rate))
            
            for col2 in range_columns[i+1:]:
                # Patrones de dos indicadores
                patterns.extend(cls._analyze_pair_indicators(
                    df, col1, col2, min_trades, min_win_rate
                ))
        
        # Ordenar por win_rate * sqrt(sample_size) para equilibrar confianza y tamaño
        patterns.sort(key=lambda p: p['score'], reverse=True)
        return patterns
    
    @classmethod
    def _analyze_single_indicator(cls, df, column, min_trades, min_win_rate):
        """Analiza un solo indicador."""
        patterns = []
        for label in df[column].dropna().unique():
            mask = df[column] == label
            sample_size = mask.sum()
            if sample_size < min_trades:
                continue
            
            wins = df.loc[mask, 'win'].sum()
            win_rate = wins / sample_size
            avg_pnl = df.loc[mask, 'pnl'].mean()
            
            if win_rate >= min_win_rate:
                # Extraer nombre del indicador (sin _range)
                indicator = column.replace('_range', '')
                pattern_name = f"{indicator}_{label}"
                
                patterns.append({
                    'pattern_name': pattern_name,
                    'conditions': {indicator: label},
                    'sample_size': sample_size,
                    'win_rate': win_rate,
                    'avg_pnl': avg_pnl,
                    'score': win_rate * np.sqrt(sample_size),
                })
        
        return patterns
    
    @classmethod
    def _analyze_pair_indicators(cls, df, col1, col2, min_trades, min_win_rate):
        """Analiza pares de indicadores."""
        patterns = []
        
        # Agrupar por combinación de rangos
        grouped = df.groupby([col1, col2]).agg({
            'win': ['count', 'sum'],
            'pnl': 'mean'
        }).reset_index()
        
        # Renombrar columnas
        grouped.columns = [col1, col2, 'count', 'wins', 'avg_pnl']
        
        for _, row in grouped.iterrows():
            if row['count'] < min_trades:
                continue
            
            win_rate = row['wins'] / row['count']
            if win_rate < min_win_rate:
                continue
            
            # Crear condiciones
            ind1 = col1.replace('_range', '')
            ind2 = col2.replace('_range', '')
            conditions = {}
            if not pd.isna(row[col1]):
                conditions[ind1] = row[col1]
            if not pd.isna(row[col2]):
                conditions[ind2] = row[col2]
            
            if not conditions:
                continue
            
            pattern_name = f"{ind1}_{row[col1]}_{ind2}_{row[col2]}"
            
            patterns.append({
                'pattern_name': pattern_name,
                'conditions': conditions,
                'sample_size': row['count'],
                'win_rate': win_rate,
                'avg_pnl': row['avg_pnl'],
                'score': win_rate * np.sqrt(row['count']),
            })
        
        return patterns
    
    @classmethod
    def _save_patterns(cls, patterns):
        """Guarda patrones en la base de datos."""
        saved = []
        for pattern_data in patterns:
            # Convertir condiciones a formato de comparación
            # Actualmente condiciones son valores discretos, los convertimos a igualdad
            conditions = {}
            for key, value in pattern_data['conditions'].items():
                if isinstance(value, (int, float)):
                    # Para valores numéricos, usar rango aproximado
                    # Por simplicidad, usamos igualdad
                    conditions[f"{key}__eq"] = value
                else:
                    conditions[key] = value
            
            # Verificar si ya existe un patrón similar
            existing = WhalePattern.objects.filter(
                conditions=conditions,
                timeframe='4h'  # Por defecto
            ).first()
            
            if existing:
                # Actualizar estadísticas
                existing.sample_size = pattern_data['sample_size']
                existing.win_rate = pattern_data['win_rate']
                existing.avg_pnl = pattern_data['avg_pnl']
                existing.total_trades = pattern_data['sample_size']
                existing.save()
                saved.append(existing)
            else:
                pattern = WhalePattern.objects.create(
                    pattern_name=pattern_data['pattern_name'],
                    conditions=conditions,
                    timeframe='4h',
                    sample_size=pattern_data['sample_size'],
                    win_rate=pattern_data['win_rate'],
                    avg_pnl=pattern_data['avg_pnl'],
                    total_trades=pattern_data['sample_size'],
                    is_active=True
                )
                saved.append(pattern)
                logger.info(f"Patrón guardado: {pattern.pattern_name} (Win: {pattern.win_rate:.1%})")
        
        return saved
    
    @classmethod
    def generate_signal(cls, symbol, context):
        """
        Genera una señal basada en patrones aprendidos.
        
        Args:
            symbol: Símbolo del token
            context: Contexto de mercado actual
            
        Returns:
            Dict con signal (BUY/SELL/HOLD), confidence, matched_patterns
        """
        if not context:
            return {'signal': 'HOLD', 'confidence': 0.0, 'matched_patterns': []}
        
        # Obtener patrones activos
        patterns = WhalePattern.objects.filter(is_active=True)
        
        matched = []
        total_confidence = 0.0
        
        for pattern in patterns:
            if pattern.match_context(context):
                # Calcular confianza basada en win_rate y sample_size
                confidence = pattern.win_rate * min(1.0, pattern.sample_size / 10)
                matched.append({
                    'pattern': pattern.pattern_name,
                    'win_rate': pattern.win_rate,
                    'sample_size': pattern.sample_size,
                    'confidence': confidence
                })
                total_confidence += confidence
        
        if not matched:
            return {'signal': 'HOLD', 'confidence': 0.0, 'matched_patterns': []}
        
        # Promediar confianza
        avg_confidence = total_confidence / len(matched)
        
        # Decidir señal (asumimos que patrones son para compra)
        signal = 'BUY' if avg_confidence > 0.6 else 'HOLD'
        
        return {
            'signal': signal,
            'confidence': avg_confidence,
            'matched_patterns': matched
        }