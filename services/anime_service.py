"""
Anime Ingest & Synchronization Service for ChibiBytes.
Handles live fetching from the Jikan API (MyAnimeList v4),
write-through caching in Neon PostgreSQL, Top 100 seeding,
and trailer resolution.
"""

import time
import threading
from datetime import datetime, timezone
import requests
from sqlalchemy import func
from models import db, Anime

JIKAN_BASE_URL = "https://api.jikan.moe/v4"
_last_request_time = 0.0
_request_lock = threading.Lock()
MIN_REQUEST_INTERVAL = 0.4  # Minimum interval (seconds) between calls to respect ~3 req/s limit

HEADERS = {
    'User-Agent': 'ChibiBytes/2.0 (Anime Discovery Platform)',
    'Accept': 'application/json'
}


def _fetch_from_jikan(endpoint: str, params: dict = None) -> dict | None:
    """
    Rate-limited HTTP client for the Jikan v4 API with retry on 429.
    Thread-safe to prevent concurrent burst throttling.
    """
    global _last_request_time

    with _request_lock:
        now = time.time()
        elapsed = now - _last_request_time
        if elapsed < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - elapsed)

        url = f"{JIKAN_BASE_URL}{endpoint}"
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=(4, 8))
            _last_request_time = time.time()

            if resp.status_code == 429:
                # Rate limited - back off and retry once
                time.sleep(2.0)
                resp = requests.get(url, params=params, headers=HEADERS, timeout=(4, 8))
                _last_request_time = time.time()

            if resp.status_code == 200:
                return resp.json()
            else:
                print(f"[Jikan API] Non-200 status {resp.status_code} for {endpoint}")
                return None
        except requests.RequestException as exc:
            print(f"[Jikan API] Request error for {endpoint}: {exc}")
            return None


def map_jikan_to_anime_data(item: dict) -> dict:
    """
    Transforms a Jikan v4 anime object into internal ChibiBytes Anime attributes.
    """
    trailer = item.get('trailer') or {}
    images = item.get('images') or {}
    webp = images.get('webp') or {}
    jpg = images.get('jpg') or {}

    # Image priority: WebP large -> JPG large -> fallback
    img_url = webp.get('large_image_url') or jpg.get('large_image_url') or webp.get('image_url') or jpg.get('image_url') or ''
    
    # Wide/banner artwork fallback: trailer maximum image -> large trailer image -> cover art
    trailer_images = trailer.get('images') or {}
    banner_url = (
        trailer_images.get('maximum_image_url') or
        trailer_images.get('large_image_url') or
        trailer_images.get('medium_image_url') or
        img_url
    )

    # Categories from genres, explicit_genres, themes, demographics
    categories = []
    for g in item.get('genres') or []:
        if g.get('name'):
            categories.append(g['name'])
    for t in item.get('themes') or []:
        if t.get('name'):
            categories.append(t['name'])
    for d in item.get('demographics') or []:
        if d.get('name'):
            categories.append(d['name'])
    category_str = ', '.join(dict.fromkeys(categories)) or 'Anime'

    # Studios
    studios = [s.get('name') for s in (item.get('studios') or []) if s.get('name')]
    studio_str = ', '.join(studios)

    # Trailer YouTube ID & Embed URL
    youtube_id = trailer.get('youtube_id') or ''
    embed_url = trailer.get('embed_url') or ''
    if youtube_id and not embed_url:
        embed_url = f"https://www.youtube.com/embed/{youtube_id}"

    # Year
    year = str(item.get('year') or '')
    if not year and item.get('aired') and isinstance(item['aired'], dict):
        prop_year = item['aired'].get('prop', {}).get('from', {}).get('year')
        if prop_year:
            year = str(prop_year)

    # Score
    score = item.get('score')
    mal_score = float(score) if score is not None else 0.0
    rating_str = f"⭐ {mal_score:.2f}" if mal_score > 0 else '⭐ N/A'

    # Clean title
    title = item.get('title_english') or item.get('title') or 'Untitled Anime'
    jp_title = item.get('title_japanese') or ''

    # Clean synopsis
    synopsis = item.get('synopsis') or 'No synopsis available.'
    # Remove MAL attribution if present at end
    if '[Written by MAL Rewrite]' in synopsis:
        synopsis = synopsis.replace('[Written by MAL Rewrite]', '').strip()

    # Rank and popularity insight
    rank = item.get('rank')
    members = item.get('members') or 0
    insights = f"Ranked #{rank} on MyAnimeList with {members:,} members." if rank else f"MyAnimeList score: {mal_score:.2f}."

    return {
        'mal_id': item.get('mal_id'),
        'title': title,
        'japanese_title': jp_title,
        'year': year,
        'rating': rating_str,
        'mal_score': mal_score,
        'image': img_url,
        'modalImage': img_url,
        'banner_image': banner_url,
        'category': category_str,
        'description': synopsis,
        'insights': insights,
        'episodes': str(item.get('episodes') or 'TV'),
        'status': item.get('status') or 'Finished Airing',
        'studio': studio_str,
        'trailer_url': embed_url,
        'trailer_youtube_id': youtube_id,
        'source': 'jikan',
        'fetched_at': datetime.now(timezone.utc)
    }


def save_or_update_anime(anime_data: dict) -> Anime:
    """
    Saves an anime into the database if not present, or updates it if present.
    Ensures safe unique primary key generation and mal_id deduplication.
    """
    mal_id = anime_data.get('mal_id')
    existing = None

    if mal_id:
        existing = Anime.query.filter_by(mal_id=mal_id).first()

    if not existing:
        # Check by exact title to prevent duplicates
        title = anime_data.get('title')
        if title:
            existing = Anime.query.filter(func.lower(Anime.title) == title.lower()).first()

    if existing:
        # Update missing or dynamic fields (score, trailer, banner)
        if anime_data.get('trailer_youtube_id') and not existing.trailer_youtube_id:
            existing.trailer_youtube_id = anime_data['trailer_youtube_id']
            existing.trailer_url = anime_data['trailer_url']
        if anime_data.get('banner_image') and (not existing.banner_image or existing.banner_image == existing.image):
            existing.banner_image = anime_data['banner_image']
        if anime_data.get('mal_score') and (not existing.mal_score or existing.mal_score == 0.0):
            existing.mal_score = anime_data['mal_score']
        if anime_data.get('mal_id') and not existing.mal_id:
            existing.mal_id = anime_data['mal_id']
        existing.fetched_at = datetime.now(timezone.utc)
        db.session.commit()
        return existing

    # Allocate new integer primary key
    max_id = db.session.query(func.max(Anime.id)).scalar() or 0
    new_id = max_id + 1

    anime = Anime(
        id=new_id,
        mal_id=anime_data.get('mal_id'),
        title=anime_data['title'],
        year=anime_data.get('year', ''),
        rating=anime_data.get('rating', ''),
        mal_score=anime_data.get('mal_score', 0.0),
        image=anime_data.get('image', ''),
        modalImage=anime_data.get('modalImage', anime_data.get('image', '')),
        banner_image=anime_data.get('banner_image', anime_data.get('image', '')),
        category=anime_data.get('category', 'Anime'),
        description=anime_data.get('description', ''),
        insights=anime_data.get('insights', ''),
        episodes=anime_data.get('episodes', ''),
        status=anime_data.get('status', 'Finished Airing'),
        studio=anime_data.get('studio', ''),
        japanese_title=anime_data.get('japanese_title', ''),
        main_characters=anime_data.get('main_characters', ''),
        trailer_url=anime_data.get('trailer_url', ''),
        trailer_youtube_id=anime_data.get('trailer_youtube_id', ''),
        source=anime_data.get('source', 'jikan'),
        fetched_at=datetime.now(timezone.utc)
    )
    db.session.add(anime)
    db.session.commit()
    return anime


def seed_top_anime(pages: int = 4, per_page: int = 25, min_threshold: int = 40) -> int:
    """
    Seeds the Top anime titles from Jikan (e.g. 4 pages * 25 = 100 titles).
    Skips if database already contains enough synced titles, unless forced.
    Returns the total number of anime added or updated.
    """
    try:
        total_anime_count = Anime.query.count()
        if total_anime_count >= min_threshold:
            print(f"[Seed] Skipping Top Anime seed; catalog already populated with {total_anime_count} titles.")
            return total_anime_count

        print(f"[Seed] Ingesting Top {pages * per_page} anime from MyAnimeList v4...")
        total_ingested = 0

        for page in range(1, pages + 1):
            data = _fetch_from_jikan("/top/anime", params={'page': page, 'limit': per_page})
            if not data or 'data' not in data:
                print(f"[Seed] Failed to fetch page {page} of top anime.")
                break

            items = data.get('data') or []
            for item in items:
                try:
                    anime_data = map_jikan_to_anime_data(item)
                    save_or_update_anime(anime_data)
                    total_ingested += 1
                except Exception as inner_ex:
                    db.session.rollback()
                    print(f"[Seed] Error saving anime {item.get('title')}: {inner_ex}")

            print(f"[Seed] Finished page {page}/{pages} ({len(items)} items processed).")

        print(f"[Seed] Completed Top Anime seed. {total_ingested} titles ingested/updated.")
        return total_ingested

    except Exception as ex:
        print(f"[Seed] Top Anime seed error: {ex}")
        return 0


def seed_top_anime_background(app, pages: int = 4):
    """
    Runs the Top 100 seed asynchronously in a daemon thread so server boot is non-blocking.
    """
    def _worker():
        with app.app_context():
            # Small initial sleep so Flask finishes socket binding
            time.sleep(1.5)
            seed_top_anime(pages=pages)

    thread = threading.Thread(target=_worker, daemon=True, name="JikanSeedWorker")
    thread.start()


def search_anime(query: str, limit: int = 15) -> list[dict]:
    """
    Hybrid Smart Ingest search:
    1. Check Neon PostgreSQL database first (< 5ms response time).
    2. If matches < 3 or cache miss, live-query Jikan API and write-through cache to DB.
    3. Return combined deduplicated results.
    """
    clean_q = query.strip()
    if not clean_q:
        return []

    # 1. Local Database lookup (Case-insensitive matching title, japanese title, and category)
    db_matches = Anime.query.filter(
        (func.lower(Anime.title).like(f'%{clean_q.lower()}%')) |
        (func.lower(Anime.japanese_title).like(f'%{clean_q.lower()}%')) |
        (func.lower(Anime.category).like(f'%{clean_q.lower()}%'))
    ).order_by(Anime.mal_score.desc()).limit(limit).all()

    results = [a.to_dict() for a in db_matches]

    # Return immediately on database match (< 5ms)
    if results:
        return results

    # Avoid external API calls during testing
    try:
        from flask import current_app
        if current_app and current_app.config.get('TESTING'):
            return results
    except Exception:
        pass

    # 2. Live Jikan API fallback on cache miss (missing or obscure titles)
    try:
        jikan_res = _fetch_from_jikan("/anime", params={'q': clean_q, 'limit': 6, 'sfw': 'true'})
        if jikan_res and 'data' in jikan_res:
            jikan_items = jikan_res.get('data') or []
            existing_ids = {r['id'] for r in results}
            existing_mal_ids = {r['mal_id'] for r in results if r.get('mal_id')}

            for item in jikan_items:
                try:
                    anime_data = map_jikan_to_anime_data(item)
                    saved_anime = save_or_update_anime(anime_data)
                    if saved_anime.id not in existing_ids and (not saved_anime.mal_id or saved_anime.mal_id not in existing_mal_ids):
                        results.append(saved_anime.to_dict())
                        existing_ids.add(saved_anime.id)
                except Exception as save_err:
                    db.session.rollback()
                    print(f"[Search Ingest] Failed to ingest {item.get('title')}: {save_err}")

    except Exception as api_err:
        print(f"[Search Ingest] Jikan fallback error: {api_err}")

    return results


def get_featured_anime() -> dict | None:
    """
    Finds the highest-rated anime with a verified YouTube trailer to feature in the hero section.
    """
    # 1. Prefer top-scored anime with a valid trailer
    featured = (
        Anime.query
        .filter(Anime.trailer_youtube_id != '', Anime.trailer_youtube_id.isnot(None))
        .order_by(Anime.mal_score.desc())
        .first()
    )

    if featured:
        return featured.to_dict()

    # 2. Fallback to any anime
    fallback = Anime.query.order_by(Anime.id.asc()).first()
    return fallback.to_dict() if fallback else None


_characters_cache: dict[int, list[dict]] = {}

def get_anime_characters(mal_id: int) -> list[dict]:
    """
    Fetches characters and voice actors for an anime from Jikan v4:
    GET /v4/anime/{mal_id}/characters
    Returns a clean list of top characters and Japanese voice actors.
    Cached in-memory to prevent repeated API hits.
    """
    if not mal_id:
        return []

    if mal_id in _characters_cache:
        return _characters_cache[mal_id]

    try:
        from flask import current_app
        if current_app and current_app.config.get('TESTING'):
            # Return dummy characters during testing to avoid external network calls
            dummy = [
                {
                    'id': 1,
                    'name': 'Test Character',
                    'role': 'Main',
                    'image': '/static/images/placeholder.jpg',
                    'voice_actor': {
                        'name': 'Test Voice Actor',
                        'language': 'Japanese',
                        'image': '/static/images/placeholder.jpg'
                    }
                }
            ]
            _characters_cache[mal_id] = dummy
            return dummy
    except Exception:
        pass

    try:
        data = _fetch_from_jikan(f"/anime/{mal_id}/characters")
        if not data or 'data' not in data:
            return []

        chars = []
        for item in data.get('data', []):
            char_data = item.get('character', {})
            char_name = char_data.get('name', 'Unknown')
            char_images = char_data.get('images', {})
            char_img = (
                char_images.get('webp', {}).get('image_url') or
                char_images.get('jpg', {}).get('image_url') or
                ''
            )
            role = item.get('role', 'Supporting')

            # Find Japanese voice actor first
            va_name = ''
            va_img = ''
            va_lang = ''
            for va in item.get('voice_actors', []):
                if va.get('language') == 'Japanese':
                    person = va.get('person', {})
                    va_name = person.get('name', '')
                    va_p_images = person.get('images', {})
                    va_img = va_p_images.get('jpg', {}).get('image_url', '')
                    va_lang = 'Japanese'
                    break

            if not va_name and item.get('voice_actors'):
                first_va = item['voice_actors'][0]
                va_person = first_va.get('person', {})
                va_name = va_person.get('name', '')
                va_lang = first_va.get('language', '')
                va_img = va_person.get('images', {}).get('jpg', {}).get('image_url', '')

            chars.append({
                'id': char_data.get('mal_id'),
                'name': char_name,
                'role': role,
                'image': char_img,
                'voice_actor': {
                    'name': va_name,
                    'language': va_lang,
                    'image': va_img
                }
            })

        _characters_cache[mal_id] = chars[:12]
        return _characters_cache[mal_id]
    except Exception as ex:
        print(f"[Characters] Error fetching characters for mal_id {mal_id}: {ex}")
        return []

