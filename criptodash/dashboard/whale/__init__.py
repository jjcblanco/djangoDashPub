"""
Paquete Whale Intelligence — seguimiento y análisis de ballenas.

Organización:
- trackers.py: sincronización con blockchains (Solana RPC, Etherscan V2, Hyperliquid)
- pipeline.py: PatternEngine (análisis, shadow trades, consenso, DNA, PnL)
- scoring.py: WhaleScoringEngine (score de confianza 0-100)
- analysis.py: WhaleAnalysisEngine (correlación de éxito, comportamiento, params de bots)
- context.py: contexto de mercado (indicadores vía Binance/ccxt)
- learner.py: WhalePatternLearner (aprendizaje de patrones de trades exitosos)
"""
from .trackers import SolanaWhaleTracker, EVMWhaleTracker, HyperliquidWhaleTracker
from .pipeline import PatternEngine
from .scoring import WhaleScoringEngine, WhalePerformanceTracker
from .analysis import WhaleAnalysisEngine
from .context import fetch_market_context, fetch_market_context_at
from .learner import WhalePatternLearner

__all__ = [
    'SolanaWhaleTracker', 'EVMWhaleTracker', 'HyperliquidWhaleTracker',
    'PatternEngine', 'WhaleScoringEngine', 'WhalePerformanceTracker',
    'WhaleAnalysisEngine', 'fetch_market_context', 'fetch_market_context_at',
    'WhalePatternLearner',
]
