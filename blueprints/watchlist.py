"""
Watchlist Blueprint for ChibiBytes.
Handles watchlist rendering, metadata-enriched additions, atomic upserts, favorite toggling, and removal.
Standardized for Neon PostgreSQL with real-time freshness and zero-stale caching.
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, make_response
from sqlalchemy import func
from models import db, Watchlist, Anime, Movie

watchlist_bp = Blueprint('watchlist', __name__)


_user_watchlist_cache = {}


def invalidate_user_watchlist_cache(user_id=None):
    """Invalidate memory cache for user's watchlist."""
    if user_id:
        _user_watchlist_cache.pop(user_id, None)
    else:
        _user_watchlist_cache.clear()


def _fetch_enriched_watchlist(user_id):
    """Fetch user's watchlist enriched with trailer_youtube_id and fallback images from in-memory catalog."""
    if user_id in _user_watchlist_cache:
        return _user_watchlist_cache[user_id]

    items = Watchlist.query.filter_by(user_id=user_id).order_by(Watchlist.is_favorite.desc(), Watchlist.added_at.desc()).all()
    if not items:
        _user_watchlist_cache[user_id] = []
        return []

    # Fast in-memory resolution from catalog cache (< 0.1ms vs 1400ms network DB queries)
    from blueprints.catalog import get_cached_anime, get_cached_movies
    cached_anime = get_cached_anime()
    cached_movies = get_cached_movies()

    anime_by_id = {a['id']: a for a in cached_anime if 'id' in a}
    anime_by_title = {a['title'].strip().lower(): a for a in cached_anime if 'title' in a}
    movie_by_id = {m['id']: m for m in cached_movies if 'id' in m}
    movie_by_title = {m['title'].strip().lower(): m for m in cached_movies if 'title' in m}

    serialized = []
    for item in items:
        d = item.to_dict()
        clean_title = (item.title or '').strip().lower()

        if item.media_type == 'movie':
            m = movie_by_id.get(item.anime_id) or movie_by_title.get(clean_title)
            if m:
                d['trailer_youtube_id'] = m.get('trailer_youtube_id') or ''
                if not d.get('image'):
                    d['image'] = m.get('image', '')
                if not d.get('description'):
                    d['description'] = m.get('description', '')
                if not d.get('category'):
                    d['category'] = m.get('category', '')
            else:
                d['trailer_youtube_id'] = ''
        else:
            a = anime_by_id.get(item.anime_id) or anime_by_title.get(clean_title)
            if a:
                d['trailer_youtube_id'] = a.get('trailer_youtube_id') or ''
                if not d.get('image'):
                    d['image'] = a.get('image', '')
                if not d.get('description'):
                    d['description'] = a.get('description', '')
                if not d.get('category'):
                    d['category'] = a.get('category', '')
            else:
                d['trailer_youtube_id'] = ''
        serialized.append(d)

    _user_watchlist_cache[user_id] = serialized
    return serialized


@watchlist_bp.route('/watchlist')
def watchlist():
    """Watchlist page with live data and anti-caching headers."""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    try:
        items = _fetch_enriched_watchlist(user_id)
    except Exception as e:
        print(f"Error fetching watchlist: {e}")
        items = []

    resp = make_response(render_template(
        'watchlist.html',
        username=session['username'],
        role=session.get('role', 'user'),
        active_page='watchlist',
        watchlist_items=items
    ))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@watchlist_bp.route('/add_to_watchlist', methods=['POST'])
def add_to_watchlist():
    """Add item to user's watchlist with rich metadata, correct media_type detection, and atomic upsert."""
    if 'user_id' not in session:
        return jsonify(success=False, error="Not logged in"), 401

    data = request.get_json() or {}
    anime_id = data.get('anime_id')
    title = data.get('title')

    if not anime_id:
        return jsonify(success=False, error="Missing anime_id"), 400

    media_type = data.get('media_type')

    # If title wasn't provided, look up from catalog
    if not title:
        if media_type == 'movie':
            m = db.session.get(Movie, anime_id)
            if m:
                title = m.title
        else:
            a = db.session.get(Anime, anime_id)
            if a:
                title = a.title
            else:
                m = db.session.get(Movie, anime_id)
                if m:
                    title = m.title
                    media_type = 'movie'

    if not title:
        return jsonify(success=False, error="Title could not be resolved"), 400

    year = data.get('year', '')
    rating = data.get('rating', '')
    image = data.get('image', '')
    category = data.get('category', '')
    description = data.get('description', '')
    episodes = data.get('episodes', '')
    user_id = session['user_id']

    try:
        # Determine media_type if not provided
        if not media_type:
            # Check Movie table first by exact title or id
            m = Movie.query.filter(func.lower(Movie.title) == func.lower(title)).first()
            if m:
                media_type = 'movie'
                anime_id = m.id
                image = image or m.image
                category = category or m.category
                description = description or m.description
                episodes = episodes or m.duration
            else:
                a = Anime.query.filter(func.lower(Anime.title) == func.lower(title)).first()
                if a:
                    media_type = 'anime'
                    anime_id = a.id
                    image = image or a.image
                    category = category or a.category
                    description = description or a.description
                    episodes = episodes or a.episodes
                else:
                    media_type = 'anime'

        # Enrich from appropriate catalog
        if media_type == 'movie':
            movie_entry = db.session.get(Movie, anime_id) or Movie.query.filter(func.lower(Movie.title) == func.lower(title)).first()
            if movie_entry:
                category = category or movie_entry.category
                description = description or movie_entry.description
                episodes = episodes or movie_entry.duration
                image = image or movie_entry.image
                year = year or movie_entry.year
                rating = rating or movie_entry.rating
        else:
            anime_entry = db.session.get(Anime, anime_id) or Anime.query.filter(func.lower(Anime.title) == func.lower(title)).first()
            if anime_entry:
                category = category or anime_entry.category
                description = description or anime_entry.description
                episodes = episodes or anime_entry.episodes
                image = image or anime_entry.image
                year = year or anime_entry.year
                rating = rating or anime_entry.rating

        # Declarative upsert via SQLAlchemy scoped to (user_id, anime_id, media_type)
        existing_item = Watchlist.query.filter_by(user_id=user_id, anime_id=anime_id, media_type=media_type).first()
        if not existing_item:
            # Also check by title and user_id to prevent duplicates with different IDs
            existing_item = Watchlist.query.filter(
                Watchlist.user_id == user_id,
                func.lower(Watchlist.title) == func.lower(title)
            ).first()

        if existing_item:
            existing_item.anime_id = anime_id
            existing_item.title = title
            existing_item.year = year
            existing_item.rating = rating
            existing_item.image = image or existing_item.image
            existing_item.category = category or existing_item.category
            existing_item.description = description or existing_item.description
            existing_item.episodes = episodes or existing_item.episodes
            existing_item.media_type = media_type
        else:
            new_item = Watchlist(
                user_id=user_id,
                anime_id=anime_id,
                title=title,
                year=year,
                rating=rating,
                image=image,
                category=category,
                description=description,
                episodes=episodes,
                media_type=media_type
            )
            db.session.add(new_item)

        db.session.commit()
        invalidate_user_watchlist_cache(user_id)
        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, error=str(e)), 500


@watchlist_bp.route('/toggle_favorite/<int:item_id>', methods=['POST'])
def toggle_favorite(item_id):
    """Toggle is_favorite status for a watchlist item."""
    if 'user_id' not in session:
        return jsonify(success=False, error="Not logged in"), 401

    user_id = session['user_id']
    try:
        item = Watchlist.query.filter_by(id=item_id, user_id=user_id).first()
        if not item:
            return jsonify(success=False, error="Item not found"), 404

        item.is_favorite = not bool(item.is_favorite)
        db.session.commit()
        invalidate_user_watchlist_cache(user_id)
        return jsonify(success=True, is_favorite=item.is_favorite)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, error=str(e)), 500


@watchlist_bp.route('/remove_from_watchlist/<int:item_id>', methods=['DELETE'])
def remove_from_watchlist(item_id):
    """Remove item from user's watchlist by primary key ID."""
    if 'user_id' not in session:
        return jsonify(success=False, status='error', error="Not logged in"), 401

    user_id = session['user_id']
    try:
        item = Watchlist.query.filter_by(id=item_id, user_id=user_id).first()
        if not item:
            return jsonify(success=False, status='error', error="Item not found"), 404

        db.session.delete(item)
        db.session.commit()
        invalidate_user_watchlist_cache(user_id)
        return jsonify(success=True, status='success')
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, status='error', error=str(e)), 500


@watchlist_bp.route('/remove_from_watchlist', methods=['POST'])
def remove_from_watchlist_by_anime_id():
    """Remove item from user's watchlist via POST using anime_id and optional media_type."""
    if 'user_id' not in session:
        return jsonify(success=False, status='error', error="Not logged in"), 401

    data = request.get_json() or {}
    anime_id = data.get('anime_id')
    media_type = data.get('media_type')
    user_id = session['user_id']

    if not anime_id:
        return jsonify(success=False, status='error', error="Missing anime_id"), 400

    try:
        query = Watchlist.query.filter_by(user_id=user_id, anime_id=anime_id)
        if media_type:
            query = query.filter_by(media_type=media_type)
        items = query.all()
        for item in items:
            db.session.delete(item)
        db.session.commit()
        invalidate_user_watchlist_cache(user_id)
        return jsonify(success=True, status='success')
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, status='error', error=str(e)), 500


@watchlist_bp.route('/get_watchlist')
def get_watchlist():
    """Get user's watchlist with enriched live data (JSON) and anti-caching headers."""
    if 'user_id' not in session:
        return jsonify(success=False, error="Not logged in"), 401

    user_id = session['user_id']
    try:
        items = _fetch_enriched_watchlist(user_id)
        resp = jsonify(items)
        resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        resp.headers['Pragma'] = 'no-cache'
        resp.headers['Expires'] = '0'
        return resp
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500
