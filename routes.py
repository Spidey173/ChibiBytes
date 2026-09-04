"""
Routes module for ChibiBytes application.
Handles all Flask routes and API endpoints, including Admin Dashboard.
"""

from functools import wraps
import sqlite3
from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db, is_postgres
from chatbot import (
    detect_intent,
    process_anime_info,
    call_gemini,
    get_smart_suggestions,
    get_anime_card_via_gemini,
    add_to_history,
    clear_history
)

routes = Blueprint('routes', __name__)


def admin_required(f):
    """Decorator to enforce admin role access control."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.path.startswith('/api/'):
                return jsonify(success=False, error="Unauthorized"), 401
            return redirect(url_for('routes.login'))

        # Fast-path: trust cryptographically signed session role if already validated
        if session.get('role') == 'admin':
            return f(*args, **kwargs)

        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT role FROM users WHERE id = ?', (session['user_id'],))
        user = cursor.fetchone()

        role = 'user'
        if user:
            role = user['role'] if isinstance(user, dict) and 'role' in user else user['role'] if hasattr(user, 'keys') and 'role' in user.keys() else 'user'
            if not role:
                role = 'user'

        session['role'] = role
        if role != 'admin':
            if request.path.startswith('/api/'):
                return jsonify(success=False, error="Forbidden: Admin access required"), 403
            return redirect(url_for('routes.anime'))
        return f(*args, **kwargs)
    return decorated_function


@routes.after_request
def add_cache_headers(response):
    """Prevent back/forward caching of login/signup pages so browser back doesn't display stale forms."""
    if request.path in ['/login', '/signup']:
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response


@routes.route('/')
def index():
    """Landing page for ChibiBytes."""
    return render_template('index.html')


@routes.route('/login', methods=['GET', 'POST'])
def login():
    """User login endpoint."""
    # If user is already authenticated on GET, redirect straight to their home
    if request.method == 'GET' and 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('routes.admin'))
        return redirect(url_for('routes.anime'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT id, password, role FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()

        if user and check_password_hash(user['password'], password):
            session.permanent = True
            session['user_id'] = user['id']
            session['username'] = username
            user_role = user['role'] if isinstance(user, dict) and user.get('role') else user['role'] if hasattr(user, 'keys') and 'role' in user.keys() and user['role'] else 'user'
            session['role'] = user_role

            if user_role == 'admin':
                return redirect(url_for('routes.admin'))
            return redirect(url_for('routes.anime'))
        else:
            error = "Invalid username or password"
            return render_template('login.html', error=error)

    return render_template('login.html')


@routes.route('/signup', methods=['GET', 'POST'])
def signup():
    """User registration endpoint."""
    # If user is already authenticated on GET, redirect straight to anime
    if request.method == 'GET' and 'user_id' in session:
        return redirect(url_for('routes.anime'))

    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            return render_template('signup.html', error="Passwords do not match")

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        try:
            db = get_db()
            cursor = db.cursor()
            
            # Check if this is the first user; if so, make them admin!
            cursor.execute('SELECT COUNT(*) FROM users')
            row = cursor.fetchone()
            count = list(row.values())[0] if isinstance(row, dict) else row[0]
            role = 'admin' if count == 0 or username.lower() == 'admin' else 'user'

            cursor.execute('INSERT INTO users (username, email, password, role) VALUES (?, ?, ?, ?)',
                           (username, email, hashed_password, role))
            db.commit()
            return redirect(url_for('routes.login'))
        except (sqlite3.IntegrityError, Exception) as e:
            return render_template('signup.html', error="Username or email already exists")

    return render_template('signup.html')


def get_cached_anime():
    if _catalog_cache['anime'] is None:
        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute('SELECT * FROM anime ORDER BY id ASC')
            _catalog_cache['anime'] = [dict(row) for row in cursor.fetchall()]
        except Exception:
            _catalog_cache['anime'] = []
    return _catalog_cache['anime']


def get_cached_movies():
    if _catalog_cache['movies'] is None:
        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute('SELECT * FROM movies ORDER BY id ASC')
            _catalog_cache['movies'] = [dict(row) for row in cursor.fetchall()]
        except Exception:
            _catalog_cache['movies'] = []
    return _catalog_cache['movies']


def warm_catalog_cache():
    """Pre-warm catalog cache on server boot."""
    get_cached_anime()
    get_cached_movies()


@routes.route('/anime')
def anime():
    """Anime page."""
    if 'user_id' not in session:
        return redirect(url_for('routes.login'))
    return render_template('anime.html', username=session['username'], role=session.get('role', 'user'), active_page='anime', anime_list=get_cached_anime())


@routes.route('/movies')
def movies():
    """Movies page."""
    if 'user_id' not in session:
        return redirect(url_for('routes.login'))
    return render_template('movies.html', username=session['username'], role=session.get('role', 'user'), active_page='movies', movies_list=get_cached_movies())


@routes.route('/genres')
def genres():
    """Genres page."""
    if 'user_id' not in session:
        return redirect(url_for('routes.login'))
    return render_template('genres.html', username=session['username'], role=session.get('role', 'user'), active_page='genres', anime_list=get_cached_anime())


@routes.route('/chat')
def chat():
    """Chat page."""
    if 'user_id' not in session:
        return redirect(url_for('routes.login'))
    return render_template('chat.html', username=session['username'], role=session.get('role', 'user'), active_page='chat')


@routes.route('/trending')
def trending():
    """Trending page."""
    if 'user_id' not in session:
        return redirect(url_for('routes.login'))
    return render_template('trending.html', username=session['username'], role=session.get('role', 'user'), active_page='trending', anime_list=get_cached_anime(), movies_list=get_cached_movies())


_user_watchlist_cache = {}

def invalidate_user_watchlist_cache(user_id=None):
    if user_id:
        _user_watchlist_cache.pop(user_id, None)
    else:
        _user_watchlist_cache.clear()


@routes.route('/watchlist')
def watchlist():
    """Watchlist page."""
    if 'user_id' not in session:
        return redirect(url_for('routes.login'))

    user_id = session['user_id']
    if user_id not in _user_watchlist_cache:
        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute('''
                SELECT id, anime_id, title, year, rating, image, category, description, episodes, media_type, is_favorite
                FROM watchlist
                WHERE user_id = ?
                ORDER BY is_favorite DESC, added_at DESC
            ''', (user_id,))
            _user_watchlist_cache[user_id] = [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error fetching watchlist: {e}")
            _user_watchlist_cache[user_id] = []

    return render_template('watchlist.html', username=session['username'], role=session.get('role', 'user'), active_page='watchlist', watchlist_items=_user_watchlist_cache[user_id])


@routes.route('/admin')
@admin_required
def admin():
    """Admin Dashboard Page."""
    return render_template('admin.html', username=session['username'], role=session.get('role', 'admin'), active_page='admin')


@routes.route('/logout')
def logout():
    """Logout user."""
    user_id = session.get('user_id')
    if user_id:
        invalidate_user_watchlist_cache(user_id)
    session.pop('user_id', None)
    session.pop('username', None)
    session.pop('role', None)
    clear_history()
    return redirect(url_for('routes.index'))


# -------------------------------
# Client API Endpoints (Cached for High Performance)
# -------------------------------

_catalog_cache = {
    'anime': None,
    'movies': None
}

def clear_catalog_cache():
    _catalog_cache['anime'] = None
    _catalog_cache['movies'] = None


@routes.route('/api/movies')
def get_movies():
    """Get all movies from database (cached)."""
    if _catalog_cache['movies'] is not None:
        return jsonify(_catalog_cache['movies'])

    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT * FROM movies ORDER BY id ASC')
        movies_list = [dict(row) for row in cursor.fetchall()]
        _catalog_cache['movies'] = movies_list
        return jsonify(movies_list)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@routes.route('/api/anime')
def get_anime():
    """Get all anime from database (cached)."""
    if _catalog_cache['anime'] is not None:
        return jsonify(_catalog_cache['anime'])

    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT * FROM anime ORDER BY id ASC')
        anime_list = [dict(row) for row in cursor.fetchall()]
        _catalog_cache['anime'] = anime_list
        return jsonify(anime_list)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@routes.route('/add_to_watchlist', methods=['POST'])
def add_to_watchlist():
    """Add item to user's watchlist with rich metadata."""
    if 'user_id' not in session:
        return jsonify(success=False, error="Not logged in"), 401

    data = request.get_json() or {}
    anime_id = data.get('anime_id')
    title = data.get('title')

    if not anime_id or not title:
        return jsonify(success=False, error="Missing required data"), 400

    year = data.get('year', '')
    rating = data.get('rating', '')
    image = data.get('image', '')
    category = data.get('category', '')
    description = data.get('description', '')
    episodes = data.get('episodes', '')
    media_type = data.get('media_type', 'anime')
    user_id = session['user_id']

    try:
        db = get_db()
        cursor = db.cursor()

        # If genre or description wasn't supplied, enrich from catalog
        if not category or not description:
            try:
                cursor.execute('SELECT category, description, episodes FROM anime WHERE id = ?', (anime_id,))
                row = cursor.fetchone()
                if row:
                    category = category or (row['category'] if isinstance(row, dict) else row[0])
                    description = description or (row['description'] if isinstance(row, dict) else row[1])
                    episodes = episodes or (row.get('episodes', '') if isinstance(row, dict) else (row[2] if len(row) > 2 else ''))
                    media_type = 'anime'
                else:
                    cursor.execute('SELECT category, description, duration FROM movies WHERE id = ?', (anime_id,))
                    mrow = cursor.fetchone()
                    if mrow:
                        category = category or (mrow['category'] if isinstance(mrow, dict) else mrow[0])
                        description = description or (mrow['description'] if isinstance(mrow, dict) else mrow[1])
                        episodes = episodes or (mrow['duration'] if isinstance(mrow, dict) else mrow[2])
                        media_type = 'movie'
            except Exception:
                pass

        if is_postgres():
            cursor.execute('''
                INSERT INTO watchlist (user_id, anime_id, title, year, rating, image, category, description, episodes, media_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (user_id, anime_id) DO UPDATE
                SET category = EXCLUDED.category,
                    description = EXCLUDED.description,
                    episodes = EXCLUDED.episodes,
                    media_type = EXCLUDED.media_type
            ''', (user_id, anime_id, title, year, rating, image, category, description, episodes, media_type))
        else:
            cursor.execute('''
                INSERT OR REPLACE INTO watchlist (user_id, anime_id, title, year, rating, image, category, description, episodes, media_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, anime_id, title, year, rating, image, category, description, episodes, media_type))

        db.commit()
        invalidate_user_watchlist_cache(user_id)
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


@routes.route('/toggle_favorite/<int:item_id>', methods=['POST'])
def toggle_favorite(item_id):
    """Toggle is_favorite status for a watchlist item."""
    if 'user_id' not in session:
        return jsonify(success=False, error="Not logged in"), 401

    user_id = session['user_id']
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT is_favorite FROM watchlist WHERE id = ? AND user_id = ?', (item_id, user_id))
        row = cursor.fetchone()
        if not row:
            return jsonify(success=False, error="Item not found"), 404

        curr_fav = row['is_favorite'] if isinstance(row, dict) else row[0]
        new_fav = not bool(curr_fav)

        cursor.execute('UPDATE watchlist SET is_favorite = ? WHERE id = ? AND user_id = ?', (new_fav, item_id, user_id))
        db.commit()
        invalidate_user_watchlist_cache(user_id)
        return jsonify(success=True, is_favorite=new_fav)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


@routes.route('/remove_from_watchlist/<int:item_id>', methods=['DELETE'])
def remove_from_watchlist(item_id):
    """Remove item from user's watchlist."""
    if 'user_id' not in session:
        return jsonify(success=False, error="Not logged in"), 401

    user_id = session['user_id']
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            DELETE FROM watchlist
            WHERE id = ? AND user_id = ?
        ''', (item_id, user_id))

        if cursor.rowcount == 0:
            return jsonify(success=False, error="Item not found"), 404

        db.commit()
        invalidate_user_watchlist_cache(user_id)
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


@routes.route('/get_watchlist')
def get_watchlist():
    """Get user's watchlist with enriched data."""
    if 'user_id' not in session:
        return jsonify(success=False, error="Not logged in"), 401

    user_id = session['user_id']
    if user_id not in _user_watchlist_cache:
        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute('''
                SELECT id, anime_id, title, year, rating, image, category, description, episodes, media_type, is_favorite
                FROM watchlist
                WHERE user_id = ?
                ORDER BY is_favorite DESC, added_at DESC
            ''', (user_id,))
            _user_watchlist_cache[user_id] = [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            return jsonify(success=False, error=str(e)), 500

    return jsonify(_user_watchlist_cache[user_id])


@routes.route('/api/reviews', methods=['GET', 'POST'])
def api_reviews():
    """Submit or retrieve community reviews."""
    db = get_db()
    cursor = db.cursor()

    if request.method == 'POST':
        if 'user_id' not in session:
            return jsonify(success=False, error="Not logged in"), 401
        data = request.get_json() or {}
        anime_id = data.get('anime_id')
        score = data.get('score', 10)
        comment = data.get('comment', '').strip()
        media_type = data.get('media_type', 'anime')

        if not anime_id:
            return jsonify(success=False, error="Missing anime_id"), 400

        try:
            cursor.execute('''
                INSERT INTO reviews (user_id, anime_id, media_type, score, comment)
                VALUES (?, ?, ?, ?, ?)
            ''', (session['user_id'], anime_id, media_type, score, comment))
            db.commit()
            return jsonify(success=True)
        except Exception as e:
            return jsonify(success=False, error=str(e)), 500

    # GET reviews
    anime_id = request.args.get('anime_id')
    if not anime_id:
        return jsonify([])
    try:
        cursor.execute('''
            SELECT r.id, r.score, r.comment, r.created_at, u.username, u.avatar_url
            FROM reviews r
            JOIN users u ON r.user_id = u.id
            WHERE r.anime_id = ?
            ORDER BY r.created_at DESC
            LIMIT 20
        ''', (anime_id,))
        return jsonify([dict(row) for row in cursor.fetchall()])
    except Exception as e:
        return jsonify([])


# -------------------------------
# Admin REST API Endpoints
# -------------------------------

@routes.route('/api/admin/stats')
@admin_required
def admin_stats():
    """Return platform statistics and database engine status."""
    try:
        db = get_db()
        cursor = db.cursor()

        cursor.execute('''
            SELECT
                (SELECT COUNT(*) FROM users) as total_users,
                (SELECT COUNT(*) FROM watchlist) as total_watchlist,
                (SELECT COUNT(*) FROM anime) as total_anime,
                (SELECT COUNT(*) FROM movies) as total_movies
        ''')
        row = cursor.fetchone()
        total_users = row['total_users'] if isinstance(row, dict) else row[0]
        total_watchlist = row['total_watchlist'] if isinstance(row, dict) else row[1]
        total_anime = row['total_anime'] if isinstance(row, dict) else row[2]
        total_movies = row['total_movies'] if isinstance(row, dict) else row[3]

        db_engine = "Neon PostgreSQL (Cloud)" if is_postgres() else "SQLite3 (Local)"

        return jsonify(success=True, stats={
            'total_users': total_users,
            'total_watchlist': total_watchlist,
            'total_anime': total_anime,
            'total_movies': total_movies,
            'total_catalog': total_anime + total_movies,
            'db_engine': db_engine
        })
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


@routes.route('/api/admin/users')
@admin_required
def admin_get_users():
    """Get list of all users."""
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT id, username, email, role, created_at FROM users ORDER BY id ASC')
        users = [dict(row) for row in cursor.fetchall()]
        return jsonify(success=True, users=users)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


@routes.route('/api/admin/users/<int:user_id>/role', methods=['POST'])
@admin_required
def admin_update_user_role(user_id):
    """Update a user's role (admin/user)."""
    try:
        data = request.get_json()
        new_role = data.get('role')
        if new_role not in ['admin', 'user']:
            return jsonify(success=False, error="Invalid role"), 400

        db = get_db()
        cursor = db.cursor()
        cursor.execute('UPDATE users SET role = ? WHERE id = ?', (new_role, user_id))
        db.commit()
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


@routes.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@admin_required
def admin_delete_user(user_id):
    """Delete a user account and their watchlist entries."""
    if user_id == session['user_id']:
        return jsonify(success=False, error="Cannot delete your own active admin account"), 400

    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('DELETE FROM watchlist WHERE user_id = ?', (user_id,))
        cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        db.commit()
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


@routes.route('/api/admin/catalog/<catalog_type>', methods=['POST'])
@admin_required
def admin_save_catalog_item(catalog_type):
    """Add or update an anime or movie catalog entry."""
    if catalog_type not in ['anime', 'movies']:
        return jsonify(success=False, error="Invalid catalog type"), 400

    data = request.get_json()
    title = data.get('title')
    image = data.get('image', '/static/images/placeholder.jpg')
    modal_image = data.get('modalImage', image)
    category = data.get('category', 'Anime')
    description = data.get('description', '')
    insights = data.get('insights', '')
    year = data.get('year', '2024')
    rating = data.get('rating', '⭐ 8.5')
    item_id = data.get('id')

    if not title:
        return jsonify(success=False, error="Title is required"), 400

    try:
        db = get_db()
        cursor = db.cursor()

        if item_id:
            # Update existing item
            if catalog_type == 'anime':
                cursor.execute('''
                    UPDATE anime SET title=?, year=?, rating=?, image=?, modalImage=?, category=?, description=?, insights=?
                    WHERE id=?
                ''', (title, year, rating, image, modal_image, category, description, insights, item_id))
            else:
                director = data.get('director', 'Unknown')
                duration = data.get('duration', '120 min')
                cursor.execute('''
                    UPDATE movies SET title=?, year=?, rating=?, image=?, modalImage=?, category=?, description=?, insights=?, director=?, duration=?
                    WHERE id=?
                ''', (title, year, rating, image, modal_image, category, description, insights, director, duration, item_id))
        else:
            # Get global max ID across both anime and movies to prevent ID collisions
            cursor.execute('SELECT MAX(max_id) FROM (SELECT MAX(id) as max_id FROM anime UNION ALL SELECT MAX(id) as max_id FROM movies) t')
            r = cursor.fetchone()
            max_id = (list(r.values())[0] if isinstance(r, dict) else r[0]) or 0
            new_id = max_id + 1

            if catalog_type == 'anime':
                cursor.execute('''
                    INSERT INTO anime (id, title, year, rating, image, modalImage, category, description, insights)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (new_id, title, year, rating, image, modal_image, category, description, insights))
            else:
                director = data.get('director', 'Unknown')
                duration = data.get('duration', '120 min')
                cursor.execute('''
                    INSERT INTO movies (id, title, year, rating, image, modalImage, category, description, insights, director, duration)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (new_id, title, year, rating, image, modal_image, category, description, insights, director, duration))

        db.commit()
        clear_catalog_cache()
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


@routes.route('/api/admin/catalog/<catalog_type>/<int:item_id>', methods=['DELETE'])
@admin_required
def admin_delete_catalog_item(catalog_type, item_id):
    """Delete an item from anime or movies catalog."""
    if catalog_type not in ['anime', 'movies']:
        return jsonify(success=False, error="Invalid catalog type"), 400

    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(f'DELETE FROM {catalog_type} WHERE id = ?', (item_id,))
        db.commit()
        clear_catalog_cache()
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


# -------------------------------
# Chatbot API Routes
# -------------------------------

@routes.route('/api/chat', methods=['POST'])
def chat_api():
    """Main chat endpoint: anime info from DB, genre & movie filtering, fallback to Gemini or local picks."""
    if 'user_id' not in session:
        return jsonify(success=False, error="Not logged in"), 401

    data = request.get_json()
    user_message = data.get('message', '').strip()
    if not user_message:
        return jsonify(success=False, error="Empty message"), 400

    add_to_history('user', user_message)
    intent_data = detect_intent(user_message)
    intent = intent_data['intent']

    response_text = ""

    try:
        db = get_db()
        cursor = db.cursor()

        if intent in ('anime_info', 'character_info'):
            title = intent_data['title']
            char_focus = (intent == 'character_info')
            info = process_anime_info(title, character_focus=char_focus)
            if info:
                response_text = info
            else:
                response_text = get_anime_card_via_gemini(title)
                if not response_text:
                    response_text = call_gemini(user_message)

        elif intent == 'movies':
            cursor.execute("SELECT title FROM movies ORDER BY RANDOM() LIMIT 2")
            rows = cursor.fetchall()
            if rows:
                cards = []
                for r in rows:
                    t = r['title'] if isinstance(r, dict) else r[0]
                    card = process_anime_info(t)
                    if card:
                        cards.append(card)
                response_text = "🍿 **Some movie picks for you:**\n" + "".join(cards)
            else:
                response_text = call_gemini(user_message)

        elif intent == 'genre':
            genre_name = intent_data['genre']
            cursor.execute("SELECT title FROM anime WHERE LOWER(category) LIKE ? ORDER BY RANDOM() LIMIT 2", (f'%{genre_name}%',))
            rows = cursor.fetchall()
            if not rows:
                cursor.execute("SELECT title FROM movies WHERE LOWER(category) LIKE ? ORDER BY RANDOM() LIMIT 2", (f'%{genre_name}%',))
                rows = cursor.fetchall()

            if rows:
                cards = []
                for r in rows:
                    t = r['title'] if isinstance(r, dict) else r[0]
                    card = process_anime_info(t)
                    if card:
                        cards.append(card)
                response_text = f"⚔️ **Some {genre_name.capitalize()} picks for you:**\n" + "".join(cards)
            else:
                response_text = call_gemini(user_message)

        elif intent == 'top_rated':
            cursor.execute("SELECT title FROM anime ORDER BY RANDOM() LIMIT 2")
            rows = cursor.fetchall()
            if rows:
                cards = []
                for r in rows:
                    t = r['title'] if isinstance(r, dict) else r[0]
                    card = process_anime_info(t)
                    if card:
                        cards.append(card)
                response_text = "🏆 **Some top picks for you:**\n" + "".join(cards)
            else:
                response_text = call_gemini(user_message)

        elif intent == 'recommend':
            cursor.execute("SELECT title FROM anime ORDER BY RANDOM() LIMIT 2")
            rows = cursor.fetchall()
            if rows:
                cards = [process_anime_info(r['title'] if isinstance(r, dict) else r[0]) for r in rows if process_anime_info(r['title'] if isinstance(r, dict) else r[0])]
                response_text = "🎯 **Some picks for you:**\n" + "".join(cards)
            else:
                response_text = "I couldn't load recommendations right now."

        elif intent == 'help':
            response_text = (
                "🤖 **Chibi AI Companion - Capabilities**\n\n"
                "I am your personal AI assistant for everything anime & movies! Here is what I can do:\n\n"
                "• 🔍 **Instant Anime & Movie Search**: Type any title (e.g., *'Solo Leveling'*, *'Jujutsu Kaisen'*, or *'Spirited Away'*) to view instant ratings, plot overviews, and AI insights.\n"
                "• 🎯 **Recommendations**: Say *'Recommend an anime'* or click quick prompts to get recommendations.\n"
                "• 🎭 **Genre & Movie Exploration**: Ask about top action, romance, shonen titles, or top-rated movies.\n"
                "• 💡 **Watchlist Integration**: Click **Add to Watchlist** directly on any recommendation card!"
            )

        else:
            words = [w.strip('?!.,') for w in user_message.lower().split() if len(w.strip('?!.,')) > 2]
            found_titles = []
            for word in words:
                if word in ['anime', 'show', 'series', 'best', 'good', 'list', 'what', 'give', 'find', 'top', 'rated']:
                    continue
                cursor.execute("SELECT title FROM anime WHERE LOWER(title) LIKE ? OR LOWER(category) LIKE ? OR LOWER(description) LIKE ?", 
                               (f'%{word}%', f'%{word}%', f'%{word}%'))
                rows = cursor.fetchall()
                if not rows:
                    cursor.execute("SELECT title FROM movies WHERE LOWER(title) LIKE ? OR LOWER(category) LIKE ? OR LOWER(description) LIKE ?", 
                                   (f'%{word}%', f'%{word}%', f'%{word}%'))
                    rows = cursor.fetchall()
                
                for r in rows:
                    t = r['title'] if isinstance(r, dict) else r[0]
                    if t not in found_titles:
                        found_titles.append(t)
                        if len(found_titles) >= 2:
                            break
                if len(found_titles) >= 2:
                    break

            if found_titles:
                cards = [process_anime_info(t) for t in found_titles if process_anime_info(t)]
                response_text = "🔍 **Some picks for you:**\n" + "".join(cards)
            else:
                response_text = call_gemini(user_message)

        # Smart fallback: If Gemini API key is missing or failed, serve random database recommendations gracefully
        if not response_text or "having trouble connecting to my AI brain" in response_text:
            cursor.execute("SELECT title FROM anime ORDER BY RANDOM() LIMIT 2")
            rows = cursor.fetchall()
            if rows:
                cards = [process_anime_info(r['title'] if isinstance(r, dict) else r[0]) for r in rows if process_anime_info(r['title'] if isinstance(r, dict) else r[0])]
                response_text = "✨ **Some picks for you:**\n" + "".join(cards)
            else:
                response_text = "I am ready to help! Try asking about Solo Leveling, Naruto, or One Piece."

        add_to_history('assistant', response_text)
        return jsonify(success=True, response=response_text, quick_replies=[])

    except Exception as e:
        print(f"Chat error: {e}")
        error_msg = "⚠️ Oops! Something went wrong. Please try again."
        add_to_history('assistant', error_msg)
        return jsonify(success=False, error=str(e)), 500


@routes.route('/api/chat/history', methods=['GET'])
def get_chat_history():
    """Retrieve recent conversation history."""
    if 'user_id' not in session:
        return jsonify(success=False, error="Not logged in"), 401
    from chatbot import get_conversation_history
    history = get_conversation_history()
    return jsonify(success=True, messages=history[-10:])


@routes.route('/api/chat/clear', methods=['POST'])
def clear_chat_history():
    """Clear conversation history."""
    if 'user_id' not in session:
        return jsonify(success=False, error="Not logged in"), 401
    clear_history()
    return jsonify(success=True)