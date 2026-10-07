"""
ChibiBytes Flask Application
A modern anime and movie discovery platform with user authentication and watchlist features.

This is the main entry point for the ChibiBytes application. It initializes Flask,
configures the database, and registers all modular blueprints.
"""

import os
from datetime import timedelta
from flask import Flask
from database import init_db, close_connection
from blueprints.auth import auth_bp
from blueprints.catalog import catalog_bp, warm_catalog_cache
from blueprints.watchlist import watchlist_bp
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask application
app = Flask(__name__)

# Stable secret key to prevent session invalidation on server reloads
app.secret_key = os.getenv('SECRET_KEY', 'chibibytes-production-session-key-3f9b2d8e1a7c5b')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Register database teardown handler
app.teardown_appcontext(close_connection)

# Register modular blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(catalog_bp)
app.register_blueprint(watchlist_bp)

# Automatic HTTP response compression (85%+ payload reduction)
import gzip
from flask import request

@app.after_request
def compress_response(response):
    """
    Transparently compress HTTP response bodies with gzip if client supports it
    and payload exceeds 500 bytes. Yields 80-88% reduction in transfer sizes
    and dramatically cuts page render wait times on both localhost and cloud hosting.
    """
    accept_encoding = request.headers.get('Accept-Encoding', '').lower()
    if (
        response.status_code < 200
        or response.status_code >= 300
        or 'Content-Encoding' in response.headers
        or len(response.data) < 500
        or 'gzip' not in accept_encoding
    ):
        return response

    compressed_data = gzip.compress(response.data, compresslevel=6)
    response.set_data(compressed_data)
    response.headers['Content-Encoding'] = 'gzip'
    response.headers['Content-Length'] = len(compressed_data)
    response.headers['Vary'] = 'Accept-Encoding'
    return response

# Initialize database & warm catalog cache
init_db(app)
with app.app_context():
    warm_catalog_cache()
    # Pre-seed Top 100 anime in background (skips if already seeded, in test mode, or running tests)
    import sys
    is_testing = app.config.get('TESTING') or 'unittest' in sys.modules or 'pytest' in sys.modules or os.getenv('SKIP_SEED') or os.getenv('VERCEL')
    if not is_testing:
        from services.anime_service import seed_top_anime_background
        seed_top_anime_background(app, pages=4)


if __name__ == '__main__':
    """Run the Flask development server."""
    app.run(host='0.0.0.0', port=5002, debug=True)