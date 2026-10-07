"""
Catalog Blueprint for ChibiBytes.
Handles browsing, genres, movies, anime, admin dashboard, community reviews, and AI chat endpoints.
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from sqlalchemy import func
from database import is_postgres
from models import db, User, Watchlist, Anime, Movie, Review
from blueprints.auth import admin_required
from chatbot import (
    detect_intent,
    process_anime_info,
    call_gemini,
    get_anime_card_via_gemini,
    add_to_history,
    clear_history
)

catalog_bp = Blueprint('catalog', __name__)

_catalog_cache = {
    'anime': None,
    'movies': None
}


def clear_catalog_cache():
    """Clear memory cache for catalog items."""
    _catalog_cache['anime'] = None
    _catalog_cache['movies'] = None


def get_cached_anime():
    """Retrieve all anime from database with caching."""
    if _catalog_cache['anime'] is None:
        try:
            items = Anime.query.order_by(Anime.id.asc()).all()
            _catalog_cache['anime'] = [a.to_dict() for a in items]
        except Exception:
            _catalog_cache['anime'] = []
    return _catalog_cache['anime']


def get_cached_movies():
    """Retrieve all movies from database with caching."""
    if _catalog_cache['movies'] is None:
        try:
            items = Movie.query.order_by(Movie.id.asc()).all()
            _catalog_cache['movies'] = [m.to_dict() for m in items]
        except Exception:
            _catalog_cache['movies'] = []
    return _catalog_cache['movies']


def warm_catalog_cache():
    """Pre-warm catalog cache on server boot."""
    get_cached_anime()
    get_cached_movies()


@catalog_bp.route('/')
def index():
    """Landing page for ChibiBytes."""
    return render_template('index.html')


@catalog_bp.route('/anime')
def anime():
    """Anime listing page."""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    return render_template('anime.html', username=session['username'], role=session.get('role', 'user'), active_page='anime', anime_list=get_cached_anime())


@catalog_bp.route('/movies')
def movies():
    """Movies listing page."""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    return render_template('movies.html', username=session['username'], role=session.get('role', 'user'), active_page='movies', movies_list=get_cached_movies())


@catalog_bp.route('/genres')
def genres():
    """Genres exploration page."""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    return render_template('genres.html', username=session['username'], role=session.get('role', 'user'), active_page='genres', anime_list=get_cached_anime())


@catalog_bp.route('/chat')
def chat():
    """AI Chat Assistant page."""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    return render_template('chat.html', username=session['username'], role=session.get('role', 'user'), active_page='chat')


@catalog_bp.route('/trending')
def trending():
    """Trending titles page."""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    return render_template('trending.html', username=session['username'], role=session.get('role', 'user'), active_page='trending', anime_list=get_cached_anime(), movies_list=get_cached_movies())


@catalog_bp.route('/admin')
@admin_required
def admin():
    """Admin Dashboard Page."""
    return render_template('admin.html', username=session['username'], role=session.get('role', 'admin'), active_page='admin')


@catalog_bp.route('/api/movies')
def get_movies():
    """Get all movies from database (cached JSON)."""
    return jsonify(get_cached_movies())


@catalog_bp.route('/api/anime')
def get_anime():
    """Get all anime from database (cached JSON)."""
    return jsonify(get_cached_anime())


@catalog_bp.route('/api/anime/search')
def api_search_anime():
    """Search anime: DB-first with Jikan auto-fetch fallback."""
    query = request.args.get('q', '').strip()
    if not query or len(query) < 2:
        return jsonify([])
    from services.anime_service import search_anime
    results = search_anime(query)
    return jsonify(results)


@catalog_bp.route('/api/anime/featured')
def api_featured_anime():
    """Return the #1 trending anime with trailer for hero spotlight."""
    from services.anime_service import get_featured_anime
    featured = get_featured_anime()
    return jsonify(featured or {})


@catalog_bp.route('/api/anime/<int:anime_id>/characters')
def api_anime_characters(anime_id):
    """Retrieve characters and Japanese voice cast for an anime via Jikan v4."""
    from services.anime_service import get_anime_characters
    anime_entry = db.session.get(Anime, anime_id)
    mal_id = anime_entry.mal_id if (anime_entry and anime_entry.mal_id) else anime_id
    characters = get_anime_characters(mal_id)
    return jsonify(success=True, anime_id=anime_id, mal_id=mal_id, characters=characters)


@catalog_bp.route('/api/reviews', methods=['GET', 'POST'])
def api_reviews():
    """Submit or retrieve community reviews."""
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
            review = Review(user_id=session['user_id'], anime_id=anime_id, media_type=media_type, score=score, comment=comment)
            db.session.add(review)
            db.session.commit()
            return jsonify(success=True)
        except Exception as e:
            db.session.rollback()
            return jsonify(success=False, error=str(e)), 500

    # GET reviews
    anime_id = request.args.get('anime_id')
    if not anime_id:
        return jsonify([])
    try:
        reviews = Review.query.filter_by(anime_id=anime_id).order_by(Review.created_at.desc()).limit(20).all()
        return jsonify([r.to_dict() for r in reviews])
    except Exception:
        return jsonify([])


@catalog_bp.route('/api/admin/stats')
@admin_required
def admin_stats():
    """Return platform statistics and database engine status."""
    try:
        total_users = User.query.count()
        total_watchlist = Watchlist.query.count()
        total_anime = Anime.query.count()
        total_movies = Movie.query.count()

        db_engine = "Neon PostgreSQL (Cloud)"

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


@catalog_bp.route('/api/admin/sync_mal', methods=['POST'])
@admin_required
def admin_sync_mal():
    """Trigger on-demand sync of Top anime from MyAnimeList v4 (Jikan)."""
    try:
        data = request.get_json() or {}
        pages = int(data.get('pages', 4))
        pages = min(max(pages, 1), 6)
        from services.anime_service import seed_top_anime
        count = seed_top_anime(pages=pages, min_threshold=0)
        clear_catalog_cache()
        return jsonify(success=True, message=f"Successfully synced {count} titles from MyAnimeList v4.", count=count)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500



@catalog_bp.route('/api/admin/catalog/<catalog_type>', methods=['POST'])
@admin_required
def admin_save_catalog_item(catalog_type):
    """Add or update an anime or movie catalog entry."""
    if catalog_type not in ['anime', 'movies']:
        return jsonify(success=False, error="Invalid catalog type"), 400

    data = request.get_json() or {}
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
        model = Anime if catalog_type == 'anime' else Movie

        if item_id:
            item = db.session.get(model, item_id)
            if not item:
                return jsonify(success=False, error="Item not found"), 404
            item.title = title
            item.year = year
            item.rating = rating
            item.image = image
            item.modalImage = modal_image
            item.category = category
            item.description = description
            item.insights = insights
            if catalog_type == 'movies':
                item.director = data.get('director', 'Unknown')
                item.duration = data.get('duration', '120 min')
        else:
            max_a = db.session.query(func.max(Anime.id)).scalar() or 0
            max_m = db.session.query(func.max(Movie.id)).scalar() or 0
            new_id = max(max_a, max_m) + 1

            if catalog_type == 'anime':
                item = Anime(
                    id=new_id, title=title, year=year, rating=rating, image=image,
                    modalImage=modal_image, category=category, description=description, insights=insights
                )
            else:
                director = data.get('director', 'Unknown')
                duration = data.get('duration', '120 min')
                item = Movie(
                    id=new_id, title=title, year=year, rating=rating, image=image,
                    modalImage=modal_image, category=category, description=description, insights=insights,
                    director=director, duration=duration
                )
            db.session.add(item)

        db.session.commit()
        clear_catalog_cache()
        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, error=str(e)), 500


@catalog_bp.route('/api/admin/catalog/<catalog_type>/<int:item_id>', methods=['DELETE'])
@admin_required
def admin_delete_catalog_item(catalog_type, item_id):
    """Delete an item from anime or movies catalog."""
    if catalog_type not in ['anime', 'movies']:
        return jsonify(success=False, error="Invalid catalog type"), 400

    try:
        model = Anime if catalog_type == 'anime' else Movie
        item = db.session.get(model, item_id)
        if item:
            db.session.delete(item)
            db.session.commit()
        clear_catalog_cache()
        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, error=str(e)), 500


@catalog_bp.route('/api/chat', methods=['POST'])
def chat_api():
    """Main chat endpoint: anime info from DB, genre & movie filtering, fallback to Gemini or local picks."""
    if 'user_id' not in session:
        return jsonify(success=False, error="Not logged in"), 401

    data = request.get_json() or {}
    user_message = data.get('message', '').strip()
    if not user_message:
        return jsonify(success=False, error="Empty message"), 400

    add_to_history('user', user_message)
    intent_data = detect_intent(user_message)
    intent = intent_data['intent']

    response_text = ""

    try:
        if intent == 'greeting':
            # Natural AI greeting via Groq / Gemini
            ai_reply = call_gemini(user_message)
            if not ai_reply or "trouble connecting" in ai_reply:
                ai_reply = "Hey there! 👋 I'm Chibi, your anime and movie assistant! What kind of anime or movies are you in the mood for today? You can ask for recommendations, details about any series, or help finding something to watch! ✨"
            response_text = ai_reply

        elif intent in ('anime_info', 'character_info'):
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
            cached_m = get_cached_movies()
            import random
            movies_sample = random.sample(cached_m, min(2, len(cached_m))) if cached_m else []
            if movies_sample:
                cards = [process_anime_info(m['title']) for m in movies_sample if process_anime_info(m['title'])]
                response_text = "🍿 **Here are some top movie picks for you:**\n" + "".join(cards)
            else:
                response_text = call_gemini(user_message)

        elif intent == 'genre':
            genre_name = intent_data['genre'].lower()
            cached_a = get_cached_anime()
            matching = [a for a in cached_a if genre_name in (a.get('category') or '').lower()]
            import random
            selected = random.sample(matching, min(2, len(matching))) if matching else []
            if selected:
                cards = [process_anime_info(a['title']) for a in selected if process_anime_info(a['title'])]
                response_text = f"⚔️ **Top {intent_data['genre'].capitalize()} picks for you:**\n" + "".join(cards)
            else:
                response_text = call_gemini(user_message)

        elif intent == 'top_rated':
            cached_a = get_cached_anime()
            import random
            top_pool = cached_a[:30] if cached_a else []
            selected = random.sample(top_pool, min(2, len(top_pool))) if top_pool else []
            if selected:
                cards = [process_anime_info(a['title']) for a in selected if process_anime_info(a['title'])]
                response_text = "🏆 **Top-rated anime picks for you:**\n" + "".join(cards)
            else:
                response_text = call_gemini(user_message)

        elif intent == 'recommend':
            cached_a = get_cached_anime()
            import random
            selected = random.sample(cached_a, min(2, len(cached_a))) if cached_a else []
            if selected:
                cards = [process_anime_info(a['title']) for a in selected if process_anime_info(a['title'])]
                response_text = "🎯 **Here are some recommendations for you:**\n" + "".join(cards)
            else:
                response_text = call_gemini(user_message)

        elif intent == 'help':
            response_text = (
                "🤖 **Chibi AI Companion - Capabilities**\n\n"
                "I am your personal AI assistant for everything anime & movies! Here is what I can do:\n\n"
                "• 💬 **Chat & Anime Trivia**: Ask me anything about plots, lore, character backgrounds, or creator insights!\n"
                "• 🔍 **Instant Anime & Movie Cards**: Type any title (e.g., *'Solo Leveling'*, *'Jujutsu Kaisen'*, *'Spirited Away'*) to view instant ratings, plot overviews, and official trailers.\n"
                "• 🎯 **Smart Recommendations**: Say *'Recommend an anime'* or ask for genres like *'Action'*, *'Romance'*, or *'Isekai'*.\n"
                "• 💡 **Watchlist Integration**: Click **Watchlist** directly on any recommendation card to save it instantly!"
            )

        else:
            # Full conversational response from Groq or Gemini AI
            response_text = call_gemini(user_message)

        if not response_text:
            response_text = "I am ready to help! Try asking about Solo Leveling, Naruto, or One Piece."

        add_to_history('assistant', response_text)
        return jsonify(success=True, response=response_text, quick_replies=[])

    except Exception as e:
        print(f"Chat error: {e}")
        error_msg = "⚠️ Oops! Something went wrong. Please try again."
        add_to_history('assistant', error_msg)
        return jsonify(success=False, error=str(e)), 500


@catalog_bp.route('/api/chat/history', methods=['GET'])
def get_chat_history():
    """Retrieve recent conversation history."""
    if 'user_id' not in session:
        return jsonify(success=False, error="Not logged in"), 401
    from chatbot import get_conversation_history
    history = get_conversation_history()
    return jsonify(success=True, messages=history[-10:])


@catalog_bp.route('/api/chat/clear', methods=['POST'])
def clear_chat_history():
    """Clear conversation history."""
    if 'user_id' not in session:
        return jsonify(success=False, error="Not logged in"), 401
    clear_history()
    return jsonify(success=True)
