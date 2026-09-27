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

# Initialize database & warm catalog cache
init_db(app)
with app.app_context():
    warm_catalog_cache()


if __name__ == '__main__':
    """Run the Flask development server."""
    app.run(host='0.0.0.0', port=5002, debug=True)