"""
FASE 2b: shim de compatibilidad.

OptimizedDayTradingStrategy fue fusionada con DayTradingStrategy
(ver dashboard/backtester.py — la clase fusionada normaliza parámetros
legacy automáticamente). Este alias existe para no romper imports.
EnhancedRiskManager fue eliminada (código muerto, 0 referencias).
"""
from .backtester import DayTradingStrategy as OptimizedDayTradingStrategy

__all__ = ['OptimizedDayTradingStrategy']
