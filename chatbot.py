"""
Chatbot module for ChibiBytes - AI Anime Assistant
Uses Google GenAI SDK (new version) with fallback.
"""

import os
import re
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

def get_conversation_history():
    user_id = session.get('user_id')
    if user_id:
        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute('''
                SELECT role, content FROM chat_messages
                WHERE user_id = ?
                ORDER BY id ASC
                LIMIT 20
            ''', (user_id,))
            rows = cursor.fetchall()
            if rows:
                return [{'role': r['role'] if isinstance(r, dict) else r[0],
                         'content': r['content'] if isinstance(r, dict) else r[1]} for r in rows]
        except Exception:
            pass

    if 'chat_history' not in session:
        session['chat_history'] = []
    return session['chat_history']

def add_to_history(role, content):
    user_id = session.get('user_id')
    if user_id:
        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute('''
                INSERT INTO chat_messages (user_id, role, content)
                VALUES (?, ?, ?)
            ''', (user_id, role, content))
            db.commit()
        except Exception:
            pass

    history = session.get('chat_history', [])
    history.append({'role': role, 'content': content})
    if len(history) > 10:
        history = history[-10:]
    session['chat_history'] = history

def clear_history():
    user_id = session.get('user_id')
    if user_id:
        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute('DELETE FROM chat_messages WHERE user_id = ?', (user_id,))
            db.commit()
        except Exception:
            pass
    session.pop('chat_history', None)

def detect_intent(message):
    """Detect if user is asking for anime/movie info, genres, recommendations, or top-rated lists."""
    msg_lower = message.lower().strip()
    
    # Remove trailing punctuation
    msg_clean = msg_lower.rstrip('?!.').strip()

    # Movies intent (e.g. "Top rated movies", "best movies", "movies list", "movie night")
    if any(k in msg_clean for k in ['movie', 'movies', 'film', 'cinema']):
        return {'intent': 'movies', 'query': msg_clean}

    # Character intent patterns
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
            if title:
                return {'intent': 'character_info', 'title': title}

    # Movies intent (e.g. "Top rated movies", "best movies", "movies list", "movie night")
    if any(k in msg_clean for k in ['movie', 'movies', 'film', 'cinema']):
        return {'intent': 'movies', 'query': msg_clean}

    # Genre intents (e.g. "Best action anime", "Romance anime", "shonen", "comedy", "fantasy")
    genres = ['action', 'shonen', 'romance', 'comedy', 'fantasy', 'drama', 'sci-fi', 'scifi', 'thriller', 'adventure', 'supernatural', 'slice of life', 'sports', 'mystery', 'horror']
    for g in genres:
        if g in msg_clean:
            return {'intent': 'genre', 'genre': g, 'query': msg_clean}

    # Top rated / best intents
    if any(k in msg_clean for k in ['top rated', 'highest rated', 'best anime', 'top anime', 'popular']):
        return {'intent': 'top_rated', 'query': msg_clean}

    # Anime info patterns
    info_patterns = [
        r'(?:tell me about|info about|details? (?:of|about)|what is|summary of) (.+)',
        r'(.+) (?:anime )?(?:info|details|summary)',
        r'describe (.+)'
    ]
    for pattern in info_patterns:
        match = re.search(pattern, msg_lower)
        if match:
            title = match.group(1).strip().strip('"\'').rstrip('?!.').strip()
            if title:
                return {'intent': 'anime_info', 'title': title}

    # Simple standalone title question (e.g., "Naruto?" or "One Piece")
    if len(msg_clean.split()) <= 4 and not any(x in msg_clean for x in ['add', 'watchlist', 'help', 'recommend']):
        db = get_db()
        cursor = db.cursor()
        
        # Check anime table
        cursor.execute('SELECT id FROM anime WHERE LOWER(title) = ? OR LOWER(title) LIKE ?', (msg_clean, f'%{msg_clean}%'))
        if cursor.fetchone():
            return {'intent': 'anime_info', 'title': msg_clean}
            
        # Check movies table
        cursor.execute('SELECT id FROM movies WHERE LOWER(title) = ? OR LOWER(title) LIKE ?', (msg_clean, f'%{msg_clean}%'))
        if cursor.fetchone():
            return {'intent': 'anime_info', 'title': msg_clean}

    # Help intents
    if 'help' in msg_clean or 'what can you do' in msg_clean:
        return {'intent': 'help'}
        
    # Recommendation intents
    if 'recommend' in msg_clean or 'suggest' in msg_clean:
        return {'intent': 'recommend'}

    return {'intent': 'general', 'title': msg_clean}

def process_anime_info(title, character_focus=False):
    """Fetch anime or movie details from database and return a formatted string with rich HTML card including main characters."""
    db = get_db()
    cursor = db.cursor()
    
    # Try searching anime table first
    cursor.execute('''
        SELECT id, title, year, rating, image, category, description, insights, studio, episodes, japanese_title, main_characters
        FROM anime
        WHERE LOWER(title) LIKE ?
        LIMIT 1
    ''', (f'%{title.lower()}%',))
    item = cursor.fetchone()
    
    # If not found in anime, try movies table
    if not item:
        cursor.execute('''
            SELECT id, title, year, rating, image, category, description, insights, director, duration, japanese_title, main_characters
            FROM movies
            WHERE LOWER(title) LIKE ?
            LIMIT 1
        ''', (f'%{title.lower()}%',))
        item = cursor.fetchone()

    if not item:
        return None
    a = dict(item)
    
    categories_list = [c.strip() for c in a['category'].split(',')] if a.get('category') else []
    cat_badges = ''.join([f'<span class="chat-card-tag">{c}</span>' for c in categories_list[:3]])
    
    safe_title = a['title'].replace("'", "\\'").replace('"', '&quot;')
    safe_img = a['image'].replace("'", "\\'")
    chars_text = a.get('main_characters', '')
    studio_text = a.get('studio', '') or a.get('director', '')
    episodes_text = a.get('episodes', '') or a.get('duration', '')

    chars_html = f'<div class="chat-card-characters"><i class="fas fa-users"></i> <strong>Main Characters:</strong> {chars_text}</div>' if chars_text else ''
    meta_extra = f'<span class="chat-card-tag"><i class="fas fa-video"></i> {studio_text}</span>' if studio_text else ''
    eps_extra = f'<span class="chat-card-tag"><i class="fas fa-clock"></i> {episodes_text}</span>' if episodes_text else ''

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
            <button class="chat-watchlist-btn" onclick="addChatCardToWatchlist(this, '{a['id']}', '{safe_title}', '{a['year']}', '{a['rating']}', '{safe_img}')" title="Add to Watchlist">
                <i class="fas fa-bookmark"></i> <span>Watchlist</span>
            </button>
        </div>
        <p class="chat-card-desc">{a['description']}</p>
        {chars_html}
        {f'<div class="chat-card-insight"><i class="fas fa-lightbulb"></i> <span>{a["insights"]}</span></div>' if a.get('insights') else ''}
    </div>
</div>
"""

def call_gemini(user_message):
    """Send user message to Gemini with conversation history and database context."""
    system_instruction = """You are Chibi, a friendly anime assistant for the ChibiBytes platform.
You help users discover anime, answer questions about characters, plot, and insights.
Keep responses concise, warm, and use emojis occasionally."""

    # Search for canonical anime & character context from our database
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT title, main_characters, description, insights FROM anime")
        rows = cursor.fetchall()
        for r in rows:
            t = r['title'] if isinstance(r, dict) else r[0]
            if t.lower() in user_message.lower():
                chars = r['main_characters'] if isinstance(r, dict) else r[1]
                desc = r['description'] if isinstance(r, dict) else r[2]
                system_instruction += f"\n[Canon Database Context for {t}]: Characters: {chars}. Synopsis: {desc}."
                break
    except Exception:
        pass

    history = get_conversation_history()

    # Build contents for Gemini
    contents = []
    for msg in history[:-1]:
        role = "user" if msg['role'] == 'user' else "model"
        contents.append(types.Content(role=role, parts=[types.Part(text=msg['content'])]))
    contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))

    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=0.7,
        max_output_tokens=500,
    )

    if not os.getenv('GEMINI_API_KEY'):
        return (
            "I'm having trouble connecting to my AI brain right now. "
            "But I can still help! Try asking about an anime in my database like 'Naruto' or 'One Piece'."
        )

    model_name = get_working_model()
    try:
        response = get_client().models.generate_content(
            model=model_name,
            contents=contents,
            config=config,
        )
        return response.text.strip()
    except Exception as e:
        print(f"Gemini error: {e}")
        return (
            "I'm having trouble connecting to my AI brain right now. "
            "But I can still help! Try asking about an anime in my database like 'Naruto' or 'One Piece'."
        )
        print(f"Gemini error: {e}")
        return (
            "I'm having trouble connecting to my AI brain right now. "
            "But I can still help! Try asking about an anime in my database like 'Naruto' or 'One Piece'."
        )

def get_smart_suggestions(response_text, original_message=""):
    """Ask Gemini to generate 2 relevant, short follow-up questions/suggestions based on the response."""
    if not os.getenv('GEMINI_API_KEY') or not response_text:
        return ["Recommend an anime", "What can you do?"]
        
    prompt = f"""Based on this assistant response:
"{response_text}"
Generate exactly 2 short follow-up buttons (under 30 characters each) that a user would likely click next.
Return ONLY the 2 items separated by a newline. Do not include numbers, bullets, quotes, or introductory text.
Example output format:
Who are the main characters?
Recommend similar anime"""

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
        if len(suggestions) < 2:
            suggestions.append("Recommend an anime")
        return suggestions
    except Exception as e:
        print(f"Error generating suggestions: {e}")
        return ["Recommend similar anime", "Recommend an anime"]

def get_anime_card_via_gemini(title):
    """Query Gemini for structured details of an anime and return the exact same rich HTML card."""
    if not os.getenv('GEMINI_API_KEY'):
        return None
        
    prompt = f"""Search details for the anime or movie titled: "{title}".
Provide the details in JSON format with the following keys:
- "title": Clean title name
- "year": Year of release
- "rating": Rating (e.g. 8.2)
- "category": Genres separated by comma (e.g. Action, Fantasy)
- "description": A concise, engaging 2-sentence description
- "insights": A short, interesting AI insight/fun fact (under 15 words)

Ensure the response is valid JSON only. Do not include markdown codeblocks or any additional text."""

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
        
        import json
        data = json.loads(response.text.strip())
        
        clean_title = data.get('title', title)
        safe_title = clean_title.replace("'", "\\'").replace('"', '&quot;')
        categories_list = [c.strip() for c in data.get('category', '').split(',')] if data.get('category') else []
        cat_badges = ''.join([f'<span class="chat-card-tag">{c}</span>' for c in categories_list[:3]])
        
        mock_id = abs(hash(clean_title)) % 900000 + 100000
        default_img = "https://images.unsplash.com/photo-1607604276583-eef5d076aa5f?w=400&q=80"
        
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
        {f'<div class="chat-card-insight"><i class="fas fa-lightbulb"></i> <span>{data.get("insights")}</span></div>' if data.get('insights') else ''}
    </div>
</div>
"""
    except Exception as e:
        print(f"Error fetching structured card: {e}")
        return None
