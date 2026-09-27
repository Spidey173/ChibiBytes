"""
Compatibility bridge for legacy imports from routes.
Exposes routes blueprint by bundling auth, catalog, and watchlist blueprints,
along with warm_catalog_cache, clear_catalog_cache, and invalidate_user_watchlist_cache.
"""

from flask import Blueprint
from blueprints.auth import auth_bp
from blueprints.catalog import catalog_bp, warm_catalog_cache, clear_catalog_cache, get_cached_anime, get_cached_movies
from blueprints.watchlist import watchlist_bp, invalidate_user_watchlist_cache

# Main blueprint maintained for any external consumers
routes = Blueprint('routes', __name__)

__all__ = [
    'routes',
    'auth_bp',
    'catalog_bp',
    'watchlist_bp',
    'warm_catalog_cache',
    'clear_catalog_cache',
    'invalidate_user_watchlist_cache',
    'get_cached_anime',
    'get_cached_movies'
]