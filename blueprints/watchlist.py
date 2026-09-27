"""
Watchlist Blueprint for ChibiBytes.
Handles watchlist rendering, metadata-enriched additions, atomic upserts, favorite toggling, and removal.
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from models import db, Watchlist, Anime, Movie

watchlist_bp = Blueprint('watchlist', __name__)

_user_watchlist_cache = {}


def invalidate_user_watchlist_cache(user_id=None):
    """Invalidate watchlist memory cache for a single user or all users."""
    if user_id:
        _user_watchlist_cache.pop(user_id, None)
    else:
        _user_watchlist_cache.clear()


@watchlist_bp.route('/watchlist')
def watchlist():
    """Watchlist page."""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    if user_id not in _user_watchlist_cache:
        try:
            items = Watchlist.query.filter_by(user_id=user_id).order_by(Watchlist.is_favorite.desc(), Watchlist.added_at.desc()).all()
            _user_watchlist_cache[user_id] = [item.to_dict() for item in items]
        except Exception as e:
            print(f"Error fetching watchlist: {e}")
            _user_watchlist_cache[user_id] = []

    return render_template('watchlist.html', username=session['username'], role=session.get('role', 'user'), active_page='watchlist', watchlist_items=_user_watchlist_cache[user_id])


@watchlist_bp.route('/add_to_watchlist', methods=['POST'])
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
        # If genre or description wasn't supplied, enrich from catalog
        if not category or not description:
            anime_entry = db.session.get(Anime, anime_id)
            if anime_entry:
                category = category or anime_entry.category
                description = description or anime_entry.description
                episodes = episodes or anime_entry.episodes
                media_type = 'anime'
            else:
                movie_entry = db.session.get(Movie, anime_id)
                if movie_entry:
                    category = category or movie_entry.category
                    description = description or movie_entry.description
                    episodes = episodes or movie_entry.duration
                    media_type = 'movie'

        # Declarative upsert via SQLAlchemy
        existing_item = Watchlist.query.filter_by(user_id=user_id, anime_id=anime_id).first()
        if existing_item:
            existing_item.title = title
            existing_item.year = year
            existing_item.rating = rating
            existing_item.image = image
            existing_item.category = category
            existing_item.description = description
            existing_item.episodes = episodes
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
    """Remove item from user's watchlist."""
    if 'user_id' not in session:
        return jsonify(success=False, error="Not logged in"), 401

    user_id = session['user_id']
    try:
        item = Watchlist.query.filter_by(id=item_id, user_id=user_id).first()
        if not item:
            return jsonify(success=False, error="Item not found"), 404

        db.session.delete(item)
        db.session.commit()
        invalidate_user_watchlist_cache(user_id)
        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, error=str(e)), 500


@watchlist_bp.route('/get_watchlist')
def get_watchlist():
    """Get user's watchlist with enriched data (JSON)."""
    if 'user_id' not in session:
        return jsonify(success=False, error="Not logged in"), 401

    user_id = session['user_id']
    if user_id not in _user_watchlist_cache:
        try:
            items = Watchlist.query.filter_by(user_id=user_id).order_by(Watchlist.is_favorite.desc(), Watchlist.added_at.desc()).all()
            _user_watchlist_cache[user_id] = [item.to_dict() for item in items]
        except Exception as e:
            return jsonify(success=False, error=str(e)), 500

    return jsonify(_user_watchlist_cache[user_id])
