"""
Whale Signal Service - Proporciona señales de trading basadas en actividad de ballenas.
"""
import logging
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q

from .models import ConsensusSignal, WhaleWallet
from .whale_analysis import WhaleAnalysisEngine
from .whale_pattern_learner import WhalePatternLearner
from .whale_intelligence import fetch_market_context

logger = logging.getLogger(__name__)

class WhaleSignalService:
    """
    Servicio unificado para obtener señales de ballenas.
    """
    
    @staticmethod
    def get_signal(pair_symbol, blockchain='solana'):
        """
        Obtiene señal de ballenas para un par específico.
        
        Args:
            pair_symbol: Símbolo del par (ej: 'SOL/USDT')
            blockchain: Blockchain principal del token
            
        Returns:
            Dict con:
                - signal: 'BUY', 'SELL', 'HOLD'
                - confidence: 0.0-1.0
                - sources: lista de fuentes que contribuyeron
                - details: información detallada
        """
        # Extraer símbolo base (SOL de SOL/USDT)
        if '/' in pair_symbol:
            symbol = pair_symbol.split('/')[0]
        else:
            symbol = pair_symbol
        
        signal = {
            'signal': 'HOLD',
            'confidence': 0.0,
            'sources': [],
            'details': {}
        }
        
        # 1. Verificar señales de consenso activas
        consensus = WhaleSignalService._check_consensus(symbol, blockchain)
        if consensus:
            signal['sources'].append('consensus')
            signal['details']['consensus'] = consensus
            # Aumentar confianza basada en consenso
            signal['confidence'] += consensus['confidence'] * 0.7
            if consensus['whale_count'] >= 3:
                signal['signal'] = 'BUY'
        
        # 2. Verificar patrones aprendidos
        context = fetch_market_context(symbol)
        if context:
            pattern_signal = WhalePatternLearner.generate_signal(symbol, context)
            if pattern_signal['confidence'] > 0:
                signal['sources'].append('patterns')
                signal['details']['patterns'] = pattern_signal
                signal['confidence'] += pattern_signal['confidence'] * 0.5
                if pattern_signal['signal'] == 'BUY' and pattern_signal['confidence'] > 0.6:
                    signal['signal'] = 'BUY'
        
        # 3. Verificar ballenas individuales con buen historial
        whale_scores = WhaleSignalService._get_whale_scores(symbol, blockchain)
        if whale_scores:
            signal['sources'].append('whale_scores')
            signal['details']['whale_scores'] = whale_scores
            avg_score = sum(ws['score'] for ws in whale_scores) / len(whale_scores)
            if avg_score > 0.7:
                signal['confidence'] += avg_score * 0.4
                if signal['signal'] == 'HOLD' and avg_score > 0.75:
                    signal['signal'] = 'BUY'
        
        # Normalizar confianza a máximo 1.0
        signal['confidence'] = min(1.0, signal['confidence'])
        
        # Determinar señal final basada en confianza
        if signal['confidence'] > 0.7:
            signal['signal'] = 'BUY'
        elif signal['confidence'] > 0.5:
            signal['signal'] = 'HOLD'  # Confianza media, no actuar
        else:
            signal['signal'] = 'HOLD'
        
        return signal
    
    @staticmethod
    def _check_consensus(symbol, blockchain):
        """
        Verifica si hay una señal de consenso activa para el token.
        """
        hour_ago = timezone.now() - timedelta(hours=1)
        consensus = ConsensusSignal.objects.filter(
            token_symbol=symbol,
            blockchain=blockchain,
            status='ACTIVE',
            detected_at__gte=hour_ago
        ).first()
        
        if not consensus:
            return None
        
        # Calcular confianza basada en número de ballenas y antigüedad
        whale_factor = min(consensus.whale_count / 5.0, 1.0)
        time_factor = 1.0 - min((timezone.now() - consensus.detected_at).total_seconds() / 3600 / 6, 0.5)
        confidence = whale_factor * time_factor
        
        return {
            'whale_count': consensus.whale_count,
            'detected_at': consensus.detected_at,
            'confidence': confidence,
            'price_change': consensus.price_change_pct,
        }
    
    @staticmethod
    def _get_whale_scores(symbol, blockchain):
        """
        Obtiene scores predictivos de ballenas individuales para este token.
        """
        # Buscar ballenas que hayan operado este token recientemente
        hour_ago = timezone.now() - timedelta(hours=24)
        wallets = WhaleWallet.objects.filter(
            is_active=True,
            blockchain=blockchain,
            transactions__to_asset=symbol,
            transactions__timestamp__gte=hour_ago
        ).distinct()
        
        scores = []
        for wallet in wallets:
            # Obtener contexto actual para calcular score predictivo
            context = fetch_market_context(symbol)
            if not context:
                continue
            
            score = WhaleAnalysisEngine.get_predictive_score(wallet.id, symbol, context)
            if score > 0.6:
                scores.append({
                    'wallet_id': wallet.id,
                    'wallet_name': wallet.name or wallet.address[:8],
                    'score': score,
                })
        
        return scores
    
    @staticmethod
    def should_override_technical_signal(pair_symbol, technical_signal, technical_confidence):
        """
        Determina si una señal de ballenas debe anular una señal técnica.
        
        Args:
            pair_symbol: Par a operar
            technical_signal: Señal técnica ('BUY', 'SELL', 'HOLD')
            technical_confidence: Confianza técnica (0-1)
            
        Returns:
            Tuple (final_signal, final_confidence, overridden)
        """
        whale_signal = WhaleSignalService.get_signal(pair_symbol)
        
        # Si no hay señal de ballena, mantener técnica
        if whale_signal['confidence'] < 0.3:
            return technical_signal, technical_confidence, False
        
        # Si señal de ballena es fuerte y opuesta a técnica, considerar anular
        if whale_signal['confidence'] > 0.8:
            if whale_signal['signal'] != technical_signal:
                # Ballena muy fuerte vs técnica débil
                if technical_confidence < 0.4:
                    return whale_signal['signal'], whale_signal['confidence'], True
        
        # Si ambas señales coinciden, aumentar confianza
        if whale_signal['signal'] == technical_signal:
            combined_confidence = (technical_confidence + whale_signal['confidence']) / 2
            return technical_signal, combined_confidence, False
        
        # Señales contradictorias, priorizar técnica pero reducir confianza
        if technical_confidence > whale_signal['confidence']:
            return technical_signal, technical_confidence * 0.7, False
        else:
            return whale_signal['signal'], whale_signal['confidence'] * 0.7, True