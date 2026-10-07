"""
Chatbot module for ChibiBytes - AI Anime Assistant
Uses Google GenAI SDK (new version) with fallback.
"""

import os
import re
import json
import requests
from flask import session
from database import get_db
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

# Configure Gemini client (new SDK)
_client = None
_offline_mode = True

def get_client():
    global _client, _offline_mode
    if genai is None:
        _offline_mode = True
        return None
        
    api_key = os.getenv('GEMINI_API_KEY')
    
    if _client and not _offline_mode:
        return _client
        
    if not api_key:
        _client = genai.Client(api_key="OFFLINE_MODE")
        _offline_mode = True
    else:
        _client = genai.Client(api_key=api_key)
        _offline_mode = False
    return _client

# Try these model names in order until one works
MODEL_CANDIDATES = [
    "gemini-1.5-flash",
    "gemini-1.5-flash-latest",
    "gemini-2.0-flash-exp",
    "gemini-2.0-flash",
    "gemini-1.5-pro",
]
WORKING_MODEL = None


def get_working_model():
    """Find the first available model that supports generateContent."""
    global WORKING_MODEL
    if WORKING_MODEL:
        return WORKING_MODEL
    try:
        for model in get_client().models.list():
            if "gemini" in model.name and "generateContent" in model.supported_actions:
                WORKING_MODEL = model.name
                print(f"✅ Using Gemini model: {WORKING_MODEL}")
                return WORKING_MODEL
    except Exception as e:
        print(f"Error listing models: {e}")
    # Fallback to first candidate if listing fails
    for name in MODEL_CANDIDATES:
        WORKING_MODEL = name
        return name

from sqlalchemy import func
from models import db, Anime, Movie, ChatMessage

def get_conversation_history():
    user_id = session.get('user_id')
    if user_id:
        try:
            messages = ChatMessage.query.filter_by(user_id=user_id).order_by(ChatMessage.id.asc()).limit(20).all()
            if messages:
                return [{'role': m.role, 'content': m.content} for m in messages]
        except Exception:
            pass
        return []

    return session.get('chat_history', [])

def add_to_history(role, content):
    user_id = session.get('user_id')
    if user_id:
        try:
            msg = ChatMessage(user_id=user_id, role=role, content=content)
            db.session.add(msg)
            db.session.commit()
        except Exception:
            db.session.rollback()
        # Keep session cookie lean to prevent 4093-byte cookie overflow
        session.pop('chat_history', None)
        return

    # For anonymous users, sanitize HTML cards and keep string representation compact
    short_content = content
    if '<div class="anime-db-card"' in short_content:
        match = re.search(r'data-title="([^"]+)"', short_content)
        title_ref = match.group(1) if match else "anime details"
        short_content = f"Here are the details for {title_ref}."
    elif len(short_content) > 300:
        short_content = short_content[:300] + "..."

    history = session.get('chat_history', [])
    history.append({'role': role, 'content': short_content})
    if len(history) > 6:
        history = history[-6:]
    session['chat_history'] = history

def clear_history():
    user_id = session.get('user_id')
    if user_id:
        try:
            ChatMessage.query.filter_by(user_id=user_id).delete()
            db.session.commit()
        except Exception:
            db.session.rollback()
    session.pop('chat_history', None)

GREETING_WORDS = {
    'hi', 'hello', 'hey', 'yo', 'sup', 'heyy', 'heyyy', 'howdy', 'hola',
    'good morning', 'good afternoon', 'good evening', 'good night',
    "what's up", 'whats up', 'wassup', 'who are you', 'how are you',
    'how are you doing', 'how r u', 'thanks', 'thank you', 'thx',
    'bye', 'goodbye', 'see ya', 'ok', 'okay', 'cool', 'nice', 'yes', 'no'
}

STOP_WORDS = {
    'the', 'and', 'for', 'with', 'about', 'who', 'what', 'when', 'where', 'why', 'how',
    'are', 'you', 'can', 'see', 'tell', 'show', 'give', 'this', 'that', 'from', 'have',
    'not', 'will', 'just', 'more', 'some', 'much', 'like', 'than', 'into', 'them'
}

def detect_intent(message):
    """Detect if user is asking for anime/movie info, genres, recommendations, greetings, or general chat."""
    msg_lower = message.lower().strip()
    msg_clean = msg_lower.rstrip('?!.,').strip()

    # 1. Greetings & conversational check (e.g. "hi", "hello", "hey chibi", "what's up")
    if (
        msg_clean in GREETING_WORDS
        or any(msg_clean.startswith(g + ' ') for g in ['hi', 'hello', 'hey', 'yo', 'sup', 'howdy'])
        or msg_clean.startswith(('hi,', 'hello,', 'hey,'))
    ):
        return {'intent': 'greeting', 'query': msg_clean}

    # 2. Help intents
    if msg_clean in ('help', 'what can you do', 'how do you work', 'commands', 'features'):
        return {'intent': 'help'}

    # 3. Recommendation intents (e.g. "recommend an anime", "suggest something", "what should i watch")
    if any(k in msg_clean for k in ['recommend', 'suggest', 'what should i watch', 'something to watch', 'anime to watch', 'good anime to watch']):
        return {'intent': 'recommend', 'query': msg_clean}

    # 4. Movies intent (e.g. "Top rated movies", "best movies", "movies list", "movie night")
    if any(k in msg_clean for k in ['movie', 'movies', 'film', 'cinema']):
        return {'intent': 'movies', 'query': msg_clean}

    # 5. Character intent patterns
    char_patterns = [
        r'(?:who (?:is|are) the )?(?:main )?characters? (?:of|in) (.+)',
        r'(?:who (?:is|are) the )?protagonists? (?:of|in) (.+)',
        r'who (?:leads|stars in) (.+)',
        r'(.+) (?:main )?characters?',
        r'cast of (.+)'
    ]
    for pattern in char_patterns:
        match = re.search(pattern, msg_lower)
        if match:
            title = match.group(1).strip().strip('"\'').rstrip('?!.').strip()
            if title and title not in GREETING_WORDS and title not in STOP_WORDS:
                return {'intent': 'character_info', 'title': title}

    # 6. Top rated / popular intents
    if any(k in msg_clean for k in ['top rated', 'highest rated', 'best anime', 'top anime', 'popular anime', 'trending anime']):
        return {'intent': 'top_rated', 'query': msg_clean}

    # 7. Genre intents
    genres = ['action', 'shonen', 'romance', 'comedy', 'fantasy', 'drama', 'sci-fi', 'scifi', 'thriller', 'adventure', 'supernatural', 'slice of life', 'sports', 'mystery', 'horror', 'isekai']
    for g in genres:
        if re.search(rf'\b{re.escape(g)}\b', msg_clean):
            return {'intent': 'genre', 'genre': g, 'query': msg_clean}

    # 8. Explicit anime info patterns
    info_patterns = [
        r'(?:tell me about|info about|details? (?:of|about)|what is|summary of|synopsis of|describe|plot of) (.+)',
        r'(.+) (?:anime )?(?:info|details|summary|synopsis|plot)'
    ]
    for pattern in info_patterns:
        match = re.search(pattern, msg_lower)
        if match:
            title = match.group(1).strip().strip('"\'').rstrip('?!.').strip()
            if title and title not in GREETING_WORDS and title not in STOP_WORDS:
                return {'intent': 'anime_info', 'title': title}

    # 9. Standalone title question (ONLY exact title match or distinct prefix match for >= 4 chars, NEVER greetings/stopwords)
    if msg_clean not in GREETING_WORDS and msg_clean not in STOP_WORDS and len(msg_clean) >= 3:
        try:
            # 1. Exact title match
            exact_a = Anime.query.filter(func.lower(Anime.title) == msg_clean).first()
            if exact_a:
                return {'intent': 'anime_info', 'title': exact_a.title}
            exact_m = Movie.query.filter(func.lower(Movie.title) == msg_clean).first()
            if exact_m:
                return {'intent': 'anime_info', 'title': exact_m.title}

            # 2. Distinct title prefix match (e.g. "naruto", "jujutsu", "death note", "solo level")
            if len(msg_clean) >= 4:
                prefix_a = Anime.query.filter(func.lower(Anime.title).like(f'{msg_clean}%')).first()
                if prefix_a:
                    return {'intent': 'anime_info', 'title': prefix_a.title}
                prefix_m = Movie.query.filter(func.lower(Movie.title).like(f'{msg_clean}%')).first()
                if prefix_m:
                    return {'intent': 'anime_info', 'title': prefix_m.title}
        except Exception:
            pass

    return {'intent': 'general', 'query': msg_clean}

def process_anime_info(title, character_focus=False):
    """Fetch anime or movie details from database or live Jikan ingest, returning a formatted rich HTML card with trailer and character info."""
    try:
        clean_title = title.lower().strip()
        item = Anime.query.filter(func.lower(Anime.title).like(f'%{clean_title}%')).first()
        if not item:
            item = Movie.query.filter(func.lower(Movie.title).like(f'%{clean_title}%')).first()

        # If not found in local database, auto-ingest live from Jikan v4
        if not item and len(clean_title) >= 3:
            try:
                from services.anime_service import search_anime
                matches = search_anime(clean_title, limit=1)
                if matches:
                    item = Anime.query.filter_by(id=matches[0]['id']).first()
            except Exception as search_err:
                print(f"[Chat Ingest] Jikan fallback note: {search_err}")

        if not item:
            return None

        a = item.to_dict()
        categories_list = [c.strip() for c in a['category'].split(',')] if a.get('category') else []
        cat_badges = ''.join([f'<span class="chat-card-tag">{c}</span>' for c in categories_list[:3]])

        safe_title = a['title'].replace("'", "\\'").replace('"', '&quot;')
        safe_img = a['image'].replace("'", "\\'")
        safe_banner = (a.get('banner_image') or a.get('modalImage') or a['image']).replace("'", "\\'")
        safe_desc = (a.get('description') or '').replace("'", "\\'").replace('"', '&quot;').replace('\n', ' ')
        chars_text = a.get('main_characters', '')
        studio_text = a.get('studio', '') or a.get('director', '')
        episodes_text = a.get('episodes', '') or a.get('duration', '')
        trailer_yt_id = a.get('trailer_youtube_id', '')

        chars_html = f'<div class="chat-card-characters"><i class="fas fa-users"></i> <strong>Main Characters:</strong> {chars_text}</div>' if chars_text else ''
        meta_extra = f'<span class="chat-card-tag"><i class="fas fa-video"></i> {studio_text}</span>' if studio_text else ''
        eps_extra = f'<span class="chat-card-tag"><i class="fas fa-clock"></i> {episodes_text}</span>' if episodes_text else ''

        trailer_btn = f'''<button class="chat-trailer-btn" onclick="openTrailerFromChat('{trailer_yt_id}', '{safe_title}', '{safe_banner}')" title="Watch Trailer">
            <i class="fas fa-play"></i> <span>Trailer</span>
        </button>''' if trailer_yt_id else ''

        intro = f"<p>👥 <strong>Key Characters & Details for {a['title']}:</strong></p>" if character_focus else ""

        return f"""{intro}
<div class="anime-db-card" data-anime-id="{a['id']}" data-title="{safe_title}" data-year="{a['year']}" data-rating="{a['rating']}" data-image="{safe_img}">
    <div class="chat-card-poster">
        <img src="{a['image']}" alt="{a['title']}" loading="lazy">
        <span class="chat-card-score"><i class="fas fa-star"></i> {a['rating']}</span>
    </div>
    <div class="chat-card-body">
        <div class="chat-card-header">
            <div>
                <h3 class="chat-card-title">{a['title']} <span class="chat-card-year">({a['year']})</span></h3>
                <div class="chat-card-tags">{cat_badges}{meta_extra}{eps_extra}</div>
            </div>
            <div class="chat-card-actions">
                {trailer_btn}
                <button class="chat-watchlist-btn" onclick="addChatCardToWatchlist(this, '{a['id']}', '{safe_title}', '{a['year']}', '{a['rating']}', '{safe_img}')" title="Add to Watchlist">
                    <i class="fas fa-bookmark"></i> <span>Watchlist</span>
                </button>
            </div>
        </div>
        <p class="chat-card-desc">{a['description']}</p>
        {chars_html}
        {f'<div class="chat-card-insight"><i class="fas fa-lightbulb"></i> <span>{a["insights"]}</span></div>' if a.get('insights') else ''}
    </div>
</div>
"""
    except Exception as ex:
        print(f"Error in process_anime_info: {ex}")
        return None

# Groq Fast Cloud LLM Integration
GROQ_MODELS = [
    'qwen/qwen3.8-27b',
    'openai/gpt-oss-120b',
    'openai/gpt-oss-20b',
    'llama-3.3-70b-versatile'
]

def call_groq(messages, max_tokens=500, temperature=0.7, json_mode=False):
    """Call Groq API using high-performance open models."""
    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        return None
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    for model in GROQ_MODELS:
        payload = {
            'model': model,
            'messages': messages,
            'max_tokens': max_tokens,
            'temperature': temperature
        }
        if json_mode:
            payload['response_format'] = {'type': 'json_object'}
        try:
            resp = requests.post(
                'https://api.groq.com/openai/v1/chat/completions',
                headers=headers,
                json=payload,
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                return data['choices'][0]['message']['content'].strip()
            elif resp.status_code != 404:
                print(f"[Groq API] Model {model} status {resp.status_code}: {resp.text[:120]}")
        except Exception as ex:
            print(f"[Groq API] Error with {model}: {ex}")
            continue
    return None

def call_gemini(user_message):
    """Send user message to AI assistant (Groq or Gemini) with conversation history and database context."""
    system_instruction = """You are Chibi, a friendly anime assistant for the ChibiBytes platform.
You help users discover anime, answer questions about characters, plot, and insights.
Keep responses concise, warm, helpful, and use emojis occasionally."""

    # Search for canonical anime & character context from in-memory catalog cache (< 0.1ms)
    try:
        from blueprints.catalog import get_cached_anime
        cached = get_cached_anime()
        clean_user_msg = user_message.lower()
        for a in cached:
            if a.get('title') and a['title'].lower() in clean_user_msg:
                system_instruction += f"\n[Canon Database Context for {a['title']}]: Characters: {a.get('main_characters', '')}. Synopsis: {a.get('description', '')}."
                break
    except Exception:
        pass

    history = get_conversation_history()

    # 1. Try Groq first if GROQ_API_KEY is configured
    if os.getenv('GROQ_API_KEY'):
        groq_messages = [{'role': 'system', 'content': system_instruction}]
        for msg in history[:-1]:
            role = 'user' if msg['role'] == 'user' else 'assistant'
            content = msg.get('content', '')
            # Clean HTML card markup so Groq receives clean dialogue context
            if '<div class="anime-db-card"' in content:
                match = re.search(r'data-title="([^"]+)"', content)
                title_ref = match.group(1) if match else "anime details"
                content = f"I showed you the card and details for {title_ref}."
            groq_messages.append({'role': role, 'content': content})
        groq_messages.append({'role': 'user', 'content': user_message})

        groq_resp = call_groq(groq_messages, max_tokens=500, temperature=0.7)
        if groq_resp:
            return groq_resp

    # 2. Try Gemini if GEMINI_API_KEY is configured
    if os.getenv('GEMINI_API_KEY') and genai is not None:
        contents = []
        for msg in history[:-1]:
            role = "user" if msg['role'] == 'user' else "model"
            content = msg.get('content', '')
            if '<div class="anime-db-card"' in content:
                match = re.search(r'data-title="([^"]+)"', content)
                title_ref = match.group(1) if match else "anime details"
                content = f"I showed you the card and details for {title_ref}."
            contents.append(types.Content(role=role, parts=[types.Part(text=content)]))
        contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.7,
            max_output_tokens=500,
        )

        try:
            model_name = get_working_model()
            response = get_client().models.generate_content(
                model=model_name,
                contents=contents,
                config=config,
            )
            if response and response.text:
                return response.text.strip()
        except Exception as e:
            print(f"Gemini error: {e}")

    # 3. Offline / database recommendation fallback
    clean_msg = user_message.lower().strip().rstrip('?!.,')
    if clean_msg in GREETING_WORDS or clean_msg.startswith(('hi', 'hello', 'hey', 'yo', 'sup')):
        return "Hey there! 👋 I'm Chibi, your anime assistant! How can I help you today? Looking for recommendations, show details, or something new to watch? ✨"

    return (
        "I am ready to help! Try asking about an anime in my database like 'Solo Leveling', 'Naruto', or 'Spirited Away'."
    )

def get_smart_suggestions(response_text, original_message=""):
    """Ask AI (Groq or Gemini) to generate 2 relevant, short follow-up questions/suggestions based on the response."""
    if not response_text:
        return ["Recommend an anime", "What can you do?"]
        
    prompt = f"""Based on this assistant response:
"{response_text}"
Generate exactly 2 short follow-up buttons (under 30 characters each) that a user would likely click next.
Return ONLY the 2 items separated by a newline. Do not include numbers, bullets, quotes, or introductory text.
Example output format:
Who are the main characters?
Recommend similar anime"""

    # 1. Try Groq
    if os.getenv('GROQ_API_KEY'):
        groq_res = call_groq([
            {'role': 'system', 'content': 'You generate 2 short follow-up prompt buttons for an anime assistant.'},
            {'role': 'user', 'content': prompt}
        ], max_tokens=60, temperature=0.6)
        if groq_res:
            lines = [line.strip().strip('"-*•').strip() for line in groq_res.split('\n') if line.strip()]
            suggestions = [line for line in lines if line and len(line) < 40][:2]
            if len(suggestions) >= 2:
                return suggestions

    # 2. Try Gemini
    if os.getenv('GEMINI_API_KEY') and genai is not None:
        try:
            model_name = get_working_model()
            config = types.GenerateContentConfig(
                temperature=0.6,
                max_output_tokens=80,
            )
            response = get_client().models.generate_content(
                model=model_name,
                contents=prompt,
                config=config,
            )
            lines = [line.strip().strip('"-*•').strip() for line in response.text.strip().split('\n') if line.strip()]
            suggestions = [line for line in lines if line and len(line) < 40][:2]
            if len(suggestions) >= 2:
                return suggestions
        except Exception as e:
            print(f"Error generating suggestions: {e}")

    return ["Recommend similar anime", "Recommend an anime"]

def get_anime_card_via_gemini(title):
    """Query AI (Groq or Gemini) for structured details of an anime and return the exact same rich HTML card."""
    prompt = f"""Search details for the anime or movie titled: "{title}".
Provide the details in JSON format with the following keys:
- "title": Clean title name
- "year": Year of release
- "rating": Rating (e.g. 8.2)
- "category": Genres separated by comma (e.g. Action, Fantasy)
- "description": A concise, engaging 2-sentence description
- "insights": A short, interesting AI insight/fun fact (under 15 words)

Ensure the response is valid JSON only. Do not include markdown codeblocks or any additional text."""

    data = None

    # 1. Try Groq JSON mode
    if os.getenv('GROQ_API_KEY'):
        raw_json = call_groq([
            {'role': 'system', 'content': 'You are an anime metadata database assistant. Return valid JSON only with keys: title, year, rating, category, description, insights.'},
            {'role': 'user', 'content': prompt}
        ], max_tokens=350, temperature=0.2, json_mode=True)
        if raw_json:
            try:
                data = json.loads(raw_json)
            except Exception as j_err:
                print(f"[Groq JSON] Parse error: {j_err}")

    # 2. Try Gemini
    if not data and os.getenv('GEMINI_API_KEY') and genai is not None:
        try:
            model_name = get_working_model()
            config = types.GenerateContentConfig(
                temperature=0.2,
                response_mime_type="application/json"
            )
            response = get_client().models.generate_content(
                model=model_name,
                contents=prompt,
                config=config,
            )
            data = json.loads(response.text.strip())
        except Exception as e:
            print(f"Error fetching structured card: {e}")

    if not data or not isinstance(data, dict):
        return None

    clean_title = data.get('title', title)
    safe_title = clean_title.replace("'", "\\'").replace('"', '&quot;')
    cat_val = data.get('category', '')
    if isinstance(cat_val, list):
        categories_list = [str(c).strip() for c in cat_val]
    else:
        categories_list = [c.strip() for c in str(cat_val).split(',')] if cat_val else []
    cat_badges = ''.join([f'<span class="chat-card-tag">{c}</span>' for c in categories_list[:3]])

    mock_id = abs(hash(clean_title)) % 900000 + 100000
    default_img = "https://images.unsplash.com/photo-1607604276583-eef5d076aa5f?w=400&q=80"
    insight_text = data.get('insights', '')
    if isinstance(insight_text, list):
        insight_text = ' '.join(insight_text)

    return f"""
<div class="anime-db-card" data-anime-id="{mock_id}" data-title="{safe_title}" data-year="{data.get('year', '')}" data-rating="{data.get('rating', 'N/A')}" data-image="{default_img}">
    <div class="chat-card-poster placeholder-poster">
        <i class="fas fa-tv"></i>
        <span class="chat-card-score"><i class="fas fa-star"></i> {data.get('rating', 'N/A')}</span>
    </div>
    <div class="chat-card-body">
        <div class="chat-card-header">
            <div>
                <h3 class="chat-card-title">{clean_title} <span class="chat-card-year">({data.get('year', '')})</span></h3>
                <div class="chat-card-tags">{cat_badges}</div>
            </div>
            <button class="chat-watchlist-btn" onclick="addChatCardToWatchlist(this, '{mock_id}', '{safe_title}', '{data.get('year', '')}', '{data.get('rating', 'N/A')}', '{default_img}')" title="Add to Watchlist">
                <i class="fas fa-bookmark"></i> <span>Watchlist</span>
            </button>
        </div>
        <p class="chat-card-desc">{data.get('description', '')}</p>
        {f'<div class="chat-card-insight"><i class="fas fa-lightbulb"></i> <span>{insight_text}</span></div>' if insight_text else ''}
    </div>
</div>
"""
