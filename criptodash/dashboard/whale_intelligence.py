"""Shim de retrocompatibilidad — el código vive en dashboard/whale/context.py."""
from .whale.context import fetch_market_context, fetch_market_context_at  # noqa: F401
