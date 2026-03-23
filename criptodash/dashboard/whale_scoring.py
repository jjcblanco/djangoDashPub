"""
Whale Scoring Engine - Sistema de puntuación y confianza para ballenas
"""

from django.db.models import Avg, Count, Q, Sum, F
from django.utils import timezone
from datetime import timedelta
import math
from decimal import Decimal

from .models import WhaleWallet, WhaleTransaction, PatternInsight, ShadowTrade


class WhaleScoringEngine:
    """
    Calcula un score de confianza (0-100) para cada ballena basado en:
    - Precisión histórica (shadow trades)
    - Rendimiento reciente
    - Consistencia de volumen
    - Early entry score
    - Actividad en red
    - Patrones detectados
    """
    
    WEIGHTS = {
        'historical_accuracy': 0.25,    # 25% - Precisión histórica
        'recent_performance': 0.30,      # 30% - Rendimiento último mes
        'volume_consistency': 0.10,      # 10% - Consistencia en volumen
        'early_entry_score': 0.20,       # 20% - Capacidad de entrada temprana
        'network_activity': 0.10,        # 10% - Actividad consistente
        'pattern_score': 0.05,           # 5%  - Patrones detectados recientes
    }
    
    # Umbrales para categorización
    THRESHOLDS = {
        'legendary': 85,    # Legendario: >85
        'elite': 70,        # Élite: 70-85
        'proven': 55,       # Probado: 55-70
        'developing': 40,   # En desarrollo: 40-55
        'risky': 25,        # Riesgoso: 25-40
        'untested': 0,      # No probado: <25
    }
    
    @classmethod
    def calculate_score(cls, wallet_obj):
        """
        Calcula score completo para una ballena.
        Retorna dict con score y desglose.
        """
        if not wallet_obj.is_active:
            return cls._empty_score(wallet_obj, reason="Inactiva")
        
        scores = {}
        
        # 1. Precisión histórica (shadow trades cerrados)
        scores['historical_accuracy'] = cls._calc_historical_accuracy(wallet_obj)
        
        # 2. Rendimiento reciente (últimos 30 días)
        scores['recent_performance'] = cls._calc_recent_performance(wallet_obj)
        
        # 3. Consistencia de volumen
        scores['volume_consistency'] = cls._calc_volume_consistency(wallet_obj)
        
        # 4. Early entry score (qué tan temprano detecta pumps)
        scores['early_entry_score'] = cls._calc_early_entry_score(wallet_obj)
        
        # 5. Network activity (frecuencia y regularidad)
        scores['network_activity'] = cls._calc_network_activity(wallet_obj)
        
        # 6. Pattern score (patrones recientes detectados)
        scores['pattern_score'] = cls._calc_pattern_score(wallet_obj)
        
        # Calcular score total ponderado
        total = 0
        breakdown = {}
        
        for key, value in scores.items():
            weight = cls.WEIGHTS.get(key, 0)
            weighted = value * weight
            total += weighted
            breakdown[key] = {
                'raw': round(value, 1),
                'weight': weight,
                'weighted': round(weighted, 1)
            }
        
        # Redondear y limitar a 100
        total = min(100, max(0, round(total, 1)))
        
        # Categoría
        category = cls._get_category(total)
        
        return {
            'score': total,
            'category': category,
            'breakdown': breakdown,
            'sufficient_data': scores['historical_accuracy'] > 0 or scores['recent_performance'] > 0
        }

    @classmethod
    def get_top_whales(cls, limit=5, min_trades=3):
        """
        Retorna las ballenas mejor puntuadas que tengan al menos X trades históricos.
        """
        wallets = WhaleWallet.objects.filter(is_active=True)
        results = []
        
        for wallet in wallets:
            # Usamos shadow trades cerrados para validar performance real
            trades_count = wallet.shadow_trades.filter(status='CLOSED').count()
            
            if trades_count >= min_trades:
                score_data = cls.calculate_score(wallet)
                results.append({
                    'id': wallet.id,
                    'address': wallet.address,
                    'name': wallet.name,
                    'score': score_data['score'],
                    'accuracy': score_data['breakdown']['historical_accuracy']['raw'],
                    'total_trades': trades_count
                })
        
        # Ordenar por score descendente
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:limit]
    
    @staticmethod
    def _calc_historical_accuracy(wallet_obj):
        """Calcula % de aciertos en shadow trades cerrados"""
        closed_trades = wallet_obj.shadow_trades.filter(status='CLOSED')
        total = closed_trades.count()
        
        if total == 0:
            return 0
        
        wins = closed_trades.filter(pnl_percent__gt=0).count()
        win_rate = (wins / total) * 100
        
        # Bonus por cantidad de trades (más datos = más confianza)
        # Máximo bonus +10% si tiene más de 50 trades
        volume_bonus = min(10, total / 5)
        
        return min(100, win_rate + volume_bonus)
    
    @staticmethod
    def _calc_recent_performance(wallet_obj):
        """Calcula rendimiento en los últimos 30 días"""
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        recent_trades = wallet_obj.shadow_trades.filter(
            status='CLOSED',
            closed_at__gte=thirty_days_ago
        )
        total = recent_trades.count()
        
        if total == 0:
            # Si no hay trades recientes, usar histórico como base
            historical = wallet_obj.shadow_trades.filter(status='CLOSED')
            if historical.exists():
                wins = historical.filter(pnl_percent__gt=0).count()
                return (wins / historical.count()) * 50  # Penalizado
            return 0
        
        wins = recent_trades.filter(pnl_percent__gt=0).count()
        win_rate = (wins / total) * 100
        
        # Bonus por tendencia (si mejora vs histórico)
        historical_win_rate = 0
        historical = wallet_obj.shadow_trades.filter(status='CLOSED')
        if historical.count() > total:
            historical_wins = historical.filter(pnl_percent__gt=0).count()
            historical_win_rate = (historical_wins / historical.count()) * 100
        
        trend_bonus = 0
        if historical_win_rate > 0 and win_rate > historical_win_rate:
            trend_bonus = min(15, (win_rate - historical_win_rate) * 0.5)
        
        return min(100, win_rate + trend_bonus)
    
    @staticmethod
    def _calc_volume_consistency(wallet_obj):
        """Calcula consistencia de volumen (Coeficiente de Variación bajo = mejor)"""
        txs = wallet_obj.transactions.all().order_by('-timestamp')[:100]
        
        if txs.count() < 5:
            return 50  # Neutral si pocos datos
        
        volumes = []
        for tx in txs:
            amount = tx.amount_in or tx.amount_out
            if amount:
                volumes.append(float(amount))
        
        if not volumes or len(volumes) < 3:
            return 50
        
        mean_vol = sum(volumes) / len(volumes)
        if mean_vol == 0:
            return 50
        
        variance = sum((v - mean_vol) ** 2 for v in volumes) / len(volumes)
        std_dev = math.sqrt(variance)
        cv = std_dev / mean_vol
        
        # CV bajo = consistente = mejor score
        # CV 0.2 -> 90 pts, CV 1.0 -> 50 pts, CV > 2 -> 20 pts
        if cv < 0.2:
            score = 90 + (0.2 - cv) * 50  # hasta 100
        elif cv < 0.5:
            score = 80 - (cv - 0.2) * 100  # 80 a 50
        elif cv < 1.0:
            score = 50 - (cv - 0.5) * 60  # 50 a 20
        else:
            score = max(10, 20 - (cv - 1.0) * 20)
        
        return min(100, max(10, round(score, 1)))
    
    @staticmethod
    def _calc_early_entry_score(wallet_obj):
        """
        Evalúa si la ballena entra temprano en tokens.
        Basado en confianza de patrones de acumulación.
        """
        # Buscar patrones de acumulación en insights
        accumulation_patterns = wallet_obj.insights.filter(
            pattern_type__in=['ACUMULACIÓN', 'ACUMULACIÓN AGRESIVA', 'SMART_MONEY']
        )
        
        if not accumulation_patterns.exists():
            # Si no tiene patrones de acumulación, score neutral
            return 50
        
        # Promedio de confianza de los patrones
        avg_confidence = accumulation_patterns.aggregate(
            avg=Avg('confidence')
        )['avg'] or 0
        
        # Convertir confianza (0-1) a score (0-100)
        base_score = avg_confidence * 100
        
        # Bonus por acumulaciones recientes (últimos 7 días)
        recent = accumulation_patterns.filter(
            detected_at__gte=timezone.now() - timedelta(days=7)
        )
        recent_bonus = min(15, recent.count() * 5)
        
        return min(100, base_score + recent_bonus)
    
    @staticmethod
    def _calc_network_activity(wallet_obj):
        """Evalúa frecuencia y regularidad de actividad"""
        txs = wallet_obj.transactions.all().order_by('-timestamp')
        count = txs.count()
        
        if count < 5:
            return 20  # Baja actividad
        
        # Frecuencia: transacciones por día
        oldest = txs.last().timestamp
        days_active = (timezone.now() - oldest).days + 1
        freq = count / max(days_active, 1)
        
        # Score por frecuencia: 0.5 tx/día = 20 pts, 5 tx/día = 100 pts
        freq_score = min(100, freq * 16)
        
        # Bonus por consistencia (transacciones en días consecutivos)
        # Simplificado: si tiene actividad en >50% de días, +20%
        if days_active > 7:
            active_days = txs.dates('timestamp', 'day', order='DESC').count()
            consistency = active_days / days_active
            if consistency > 0.5:
                freq_score = min(100, freq_score * 1.2)
        
        return round(freq_score, 1)
    
    @staticmethod
    def _calc_pattern_score(wallet_obj):
        """Evalúa patrones recientes detectados"""
        recent_insights = wallet_obj.insights.filter(
            detected_at__gte=timezone.now() - timedelta(days=14)
        )
        
        if not recent_insights.exists():
            return 0
        
        # Ponderación por tipo de patrón
        pattern_weights = {
            'ACUMULACIÓN AGRESIVA': 1.0,
            'SMART_MONEY': 0.9,
            'ACUMULACIÓN': 0.8,
            'SNIPER': 0.7,
            'OBSERVACIÓN': 0.3,
            'FILTRADO': 0.1,
        }
        
        total_weight = 0
        for insight in recent_insights:
            weight = pattern_weights.get(insight.pattern_type, 0.3)
            total_weight += weight * insight.confidence
        
        # Normalizar a 100
        max_possible = recent_insights.count() * 1.0
        if max_possible == 0:
            return 0
        
        score = (total_weight / max_possible) * 100
        return min(100, round(score, 1))
    
    @staticmethod
    def _get_category(score):
        """Retorna categoría basada en score"""
        if score >= 85:
            return {'name': 'Legendaria', 'icon': '👑', 'color': 'gold', 'description': 'Historial impecable, alta confianza'}
        elif score >= 70:
            return {'name': 'Élite', 'icon': '⭐', 'color': 'purple', 'description': 'Excelente rendimiento consistente'}
        elif score >= 55:
            return {'name': 'Probada', 'icon': '✅', 'color': 'green', 'description': 'Buen historial, confiable'}
        elif score >= 40:
            return {'name': 'En Desarrollo', 'icon': '🌱', 'color': 'blue', 'description': 'Potencial, requiere más datos'}
        elif score >= 25:
            return {'name': 'Riesgosa', 'icon': '⚠️', 'color': 'orange', 'description': 'Inconsistente, operar con cautela'}
        else:
            return {'name': 'No Probada', 'icon': '❓', 'color': 'gray', 'description': 'Pocos datos o inactiva'}
    
    @staticmethod
    def _empty_score(wallet_obj, reason):
        """Retorna score vacío para wallet inactiva"""
        return {
            'score': 0,
            'category': {'name': 'Inactiva', 'icon': '⏸️', 'color': 'gray', 'description': reason},
            'breakdown': {},
            'sufficient_data': False
        }
    
    @classmethod
    def get_top_whales(cls, limit=5, min_trades=3):
        """
        Retorna las ballenas con mejor score.
        Filtra por mínimo de trades para asegurar datos suficientes.
        """
        wallets = WhaleWallet.objects.filter(is_active=True)
        scored = []
        
        for wallet in wallets:
            # Verificar mínimo de trades
            trade_count = wallet.shadow_trades.filter(status='CLOSED').count()
            if trade_count < min_trades:
                continue
            
            score_data = cls.calculate_score(wallet)
            if score_data['sufficient_data']:
                scored.append({
                    'id': wallet.id,
                    'name': wallet.name,
                    'address': wallet.address,
                    'blockchain': wallet.blockchain,
                    'score': score_data['score'],
                    'category': score_data['category']['name'],
                    'category_icon': score_data['category']['icon'],
                    'accuracy': score_data['breakdown'].get('recent_performance', {}).get('raw', 0),
                    'total_trades': trade_count,
                    'win_rate': score_data['breakdown'].get('historical_accuracy', {}).get('raw', 0)
                })
        
        # Ordenar por score descendente
        scored.sort(key=lambda x: x['score'], reverse=True)
        
        return scored[:limit]


class WhalePerformanceTracker:
    """
    Trackea el rendimiento agregado de un portfolio que sigue ballenas.
    """
    
    def __init__(self, user_id, initial_balance=10000):
        self.user_id = user_id
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.allocations = {}  # {whale_id: allocation_pct}
        self.trades = []  # Historial de trades simulados
    
    def allocate_to_whale(self, whale_id, allocation_pct):
        """
        Asigna un porcentaje del portfolio a seguir a una ballena.
        allocation_pct: 0-100
        """
        if allocation_pct <= 0:
            return False
        
        self.allocations[whale_id] = allocation_pct
        return True
    
    def execute_shadow_trade(self, whale_id, token, side, price, amount):
        """
        Simula ejecutar un trade siguiendo a la ballena.
        """
        allocation = self.allocations.get(whale_id, 0)
        if allocation == 0:
            return None
        
        # Calcular tamaño de posición basado en asignación
        position_value = (allocation / 100) * self.balance
        trade_amount = position_value / price if price else 0
        
        trade = {
            'whale_id': whale_id,
            'token': token,
            'side': side,
            'price': price,
            'amount': trade_amount,
            'value': position_value,
            'timestamp': timezone.now()
        }
        
        self.trades.append(trade)
        return trade
    
    def get_performance_metrics(self):
        """
        Calcula métricas de rendimiento del portfolio simulado.
        """
        # Implementación simplificada
        closed_trades = [t for t in self.trades if t.get('closed')]
        if not closed_trades:
            return {
                'total_return': 0,
                'total_trades': 0,
                'win_rate': 0,
                'sharpe_ratio': 0,
                'max_drawdown': 0
            }
        
        # Calcular returns
        returns = [t.get('return_pct', 0) for t in closed_trades if t.get('return_pct')]
        wins = [r for r in returns if r > 0]
        losses = [r for r in returns if r <= 0]
        
        win_rate = (len(wins) / len(returns)) * 100 if returns else 0
        total_return = sum(returns)
        
        return {
            'total_return': round(total_return, 2),
            'total_trades': len(returns),
            'win_rate': round(win_rate, 1),
            'avg_win': round(sum(wins) / len(wins), 2) if wins else 0,
            'avg_loss': round(sum(losses) / len(losses), 2) if losses else 0,
            'best_trade': round(max(returns), 2) if returns else 0,
            'worst_trade': round(min(returns), 2) if returns else 0
        }