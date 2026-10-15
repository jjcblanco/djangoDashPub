"""Shim de retrocompatibilidad — el código vive en dashboard/whale/scoring.py."""
from .whale.scoring import WhaleScoringEngine, WhalePerformanceTracker  # noqa: F401
