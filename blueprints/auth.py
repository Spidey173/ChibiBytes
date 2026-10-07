"""
Authentication Blueprint for ChibiBytes.
Handles login, signup, logout, access control decorators, and admin user management.
"""

from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User
from chatbot import clear_history

auth_bp = Blueprint('auth', __name__)


def admin_required(f):
    """Decorator to enforce admin role access control."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.path.startswith('/api/'):
                return jsonify(success=False, error="Unauthorized"), 401
            return redirect(url_for('auth.login'))

        # Fast-path: trust cryptographically signed session role if already validated
        if session.get('role') == 'admin':
            return f(*args, **kwargs)

        user = db.session.get(User, session['user_id'])
        role = user.role if user else 'user'

        session['role'] = role
        if role != 'admin':
            if request.path.startswith('/api/'):
                return jsonify(success=False, error="Forbidden: Admin access required"), 403
            return redirect(url_for('catalog.anime'))
        return f(*args, **kwargs)
    return decorated_function


@auth_bp.after_request
def add_cache_headers(response):
    """Prevent back/forward caching of login/signup pages so browser back doesn't display stale forms."""
    if request.path in ['/login', '/signup']:
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login endpoint."""
    # If user is already authenticated on GET, redirect straight to their home
    if request.method == 'GET' and 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('catalog.admin'))
        return redirect(url_for('catalog.anime'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session.permanent = True
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role or 'user'

            if session['role'] == 'admin':
                return redirect(url_for('catalog.admin'))
            return redirect(url_for('catalog.anime'))
        else:
            error = "Invalid username or password"
            return render_template('login.html', error=error)

    return render_template('login.html')


@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    """User registration endpoint."""
    # If user is already authenticated on GET, redirect straight to anime
    if request.method == 'GET' and 'user_id' in session:
        return redirect(url_for('catalog.anime'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if password != confirm_password:
            return render_template('signup.html', error="Passwords do not match")

        # Check existing user
        existing = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing:
            return render_template('signup.html', error="Username or email already exists")

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        try:
            count = User.query.count()
            role = 'admin' if count == 0 or username.lower() == 'admin' else 'user'

            new_user = User(username=username, email=email, password=hashed_password, role=role)
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for('auth.login'))
        except Exception:
            db.session.rollback()
            return render_template('signup.html', error="Username or email already exists")

    return render_template('signup.html')


@auth_bp.route('/logout')
def logout():
    """Logout user and clear session state."""
    from blueprints.watchlist import invalidate_user_watchlist_cache
    user_id = session.get('user_id')
    if user_id:
        invalidate_user_watchlist_cache(user_id)
    session.pop('user_id', None)
    session.pop('username', None)
    session.pop('role', None)
    clear_history()
    return redirect(url_for('catalog.index'))


@auth_bp.route('/api/admin/users')
@admin_required
def admin_get_users():
    """Get list of all users."""
    try:
        users = User.query.order_by(User.id.asc()).all()
        return jsonify(success=True, users=[u.to_dict() for u in users])
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


@auth_bp.route('/api/admin/users/<int:user_id>/role', methods=['POST'])
@admin_required
def admin_update_user_role(user_id):
    """Update a user's role (admin/user)."""
    try:
        data = request.get_json() or {}
        new_role = data.get('role')
        if new_role not in ['admin', 'user']:
            return jsonify(success=False, error="Invalid role"), 400

        user = db.session.get(User, user_id)
        if not user:
            return jsonify(success=False, error="User not found"), 404

        user.role = new_role
        db.session.commit()
        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, error=str(e)), 500


@auth_bp.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@admin_required
def admin_delete_user(user_id):
    """Delete a user account and their associated records via cascade."""
    if user_id == session['user_id']:
        return jsonify(success=False, error="Cannot delete your own active admin account"), 400

    try:
        user = db.session.get(User, user_id)
        if not user:
            return jsonify(success=False, error="User not found"), 404

        db.session.delete(user)
        db.session.commit()
        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, error=str(e)), 500
