"""
Paquete de tests de dashboard (Fase 3).

Los tests usan SQLite in-memory vía SQLiteTestCase para no depender
de MySQL/Redis locales.
"""
from .base import SQLiteTestCase  # noqa: F401
