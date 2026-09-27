"""
Blueprints package for ChibiBytes.
Exposes auth_bp, catalog_bp, and watchlist_bp.
"""

from blueprints.auth import auth_bp
from blueprints.catalog import catalog_bp
from blueprints.watchlist import watchlist_bp

__all__ = ['auth_bp', 'catalog_bp', 'watchlist_bp']
