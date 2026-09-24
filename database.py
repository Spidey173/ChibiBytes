"""
Database module for ChibiBytes application.
Standardized on Flask-SQLAlchemy with native connection pooling and multi-dialect support
(SQLite for local development/testing, PostgreSQL for production/cloud).
Completely eliminates runtime regex parameter translation hacks.
"""

import os
import re
from flask import g
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash
from sqlalchemy import text
from models import db, User, Watchlist, Anime, Movie, Review, ChatMessage

load_dotenv()

DATABASE = 'ChibiBytes_users.db'
DATABASE_URL = os.getenv('DATABASE_URL')


def get_db_uri(custom_db_name=None):
    """Normalize database connection URI for SQLAlchemy across PostgreSQL and SQLite."""
    db_url = os.getenv('DATABASE_URL')
    if db_url:
        # Normalize postgres:// to postgresql+psycopg2:// for SQLAlchemy 2.0+
        if db_url.startswith('postgres://'):
            db_url = db_url.replace('postgres://', 'postgresql+psycopg2://', 1)
        elif db_url.startswith('postgresql://') and not db_url.startswith('postgresql+psycopg2://'):
            db_url = db_url.replace('postgresql://', 'postgresql+psycopg2://', 1)
        return db_url

    db_path = custom_db_name or DATABASE
    if os.path.isabs(db_path):
        return f"sqlite:///{db_path}"
    return f"sqlite:///{os.path.abspath(db_path)}"


def is_postgres():
    """Check if current environment is configured to use PostgreSQL."""
    return bool(os.getenv('DATABASE_URL'))


class RowWrapper:
    """Row wrapper that supports both tuple indexing row[0] and dictionary key access row['col']."""
    def __init__(self, data_dict, data_tuple=None):
        self._dict = dict(data_dict) if data_dict else {}
        self._tuple = tuple(data_tuple) if data_tuple is not None else tuple(self._dict.values())

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._tuple[key]
        return self._dict.get(key)

    def __contains__(self, key):
        return key in self._dict

    def keys(self):
        return self._dict.keys()

    def values(self):
        return self._dict.values()

    def items(self):
        return self._dict.items()

    def get(self, key, default=None):
        return self._dict.get(key, default)

    def __iter__(self):
        return iter(self._tuple)

    def __len__(self):
        return len(self._tuple)

    def __repr__(self):
        return repr(self._dict)


class CompatCursor:
    """
    Lightweight DB-API compatibility cursor delegating to the active DB-API connection.
    Preserves backward compatibility for legacy queries and test runners without string munging.
    """
    def __init__(self, raw_cursor):
        self._cursor = raw_cursor

    def execute(self, query, params=None):
        if params is not None:
            return self._cursor.execute(query, params)
        return self._cursor.execute(query)

    def _wrap_row(self, row):
        if row is None:
            return None
        if hasattr(self._cursor, 'description') and self._cursor.description:
            col_names = [d[0] for d in self._cursor.description]
            data_dict = {col: val for col, val in zip(col_names, row)}
            return RowWrapper(data_dict, row)
        return row

    def fetchone(self):
        row = self._cursor.fetchone()
        return self._wrap_row(row)

    def fetchall(self):
        rows = self._cursor.fetchall()
        return [self._wrap_row(r) for r in rows]

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def close(self):
        try:
            self._cursor.close()
        except Exception:
            pass


class CompatDB:
    """Backward-compatible DB adapter for code expecting db.cursor(), db.commit(), db.rollback()."""
    def __init__(self, session):
        self._session = session

    def cursor(self):
        raw_conn = self._session.connection().connection
        raw_cursor = raw_conn.cursor()
        return CompatCursor(raw_cursor)

    def commit(self):
        self._session.commit()

    def rollback(self):
        self._session.rollback()

    def close(self):
        self._session.remove()


def get_db():
    """Get active database interface."""
    return CompatDB(db.session)


def close_connection(exception=None):
    """Clean up SQLAlchemy session at the end of the request context."""
    db.session.remove()


def _seed_demo_accounts():
    """Ensure recruiter-friendly demo accounts (demo_admin & demo_user) exist."""
    try:
        demo_accounts = [
            ('demo_admin', generate_password_hash('Admin123!', method='pbkdf2:sha256'), 'demo.admin@chibibytes.com', 'admin'),
            ('demo_user', generate_password_hash('User123!', method='pbkdf2:sha256'), 'demo.user@chibibytes.com', 'user')
        ]
        for uname, pwd_hash, email, urole in demo_accounts:
            existing = User.query.filter_by(username=uname).first()
            if not existing:
                user = User(username=uname, password=pwd_hash, email=email, role=urole)
                db.session.add(user)
        db.session.commit()
    except Exception as ex:
        print(f"Demo accounts notice: {ex}")
        db.session.rollback()


def _extract_js_objects(file_path, var_name):
    """Extract JS objects from template files for initial catalog seeding."""
    try:
        if not os.path.exists(file_path):
            return []
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        pattern = rf'const\s+{var_name}\s*=\s*\[(.*?)\]\s*;'
        match = re.search(pattern, content, re.DOTALL)
        if not match:
            pattern = rf'{var_name}\s*=\s*\[(.*?)\]'
            match = re.search(pattern, content, re.DOTALL)

        if not match:
            return []

        array_content = match.group(1)
        objects = []
        current_obj = []
        brace_count = 0
        in_string = False
        string_char = None
        escaped = False

        for char in array_content:
            if escaped:
                current_obj.append(char)
                escaped = False
                continue
            if char == '\\':
                current_obj.append(char)
                escaped = True
                continue
            if char in ('"', "'", '`'):
                if not in_string:
                    in_string = True
                    string_char = char
                elif string_char == char:
                    in_string = False
                    string_char = None
                current_obj.append(char)
                continue

            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        current_obj.append(char)
                        objects.append("".join(current_obj))
                        current_obj = []
                        continue

            if brace_count > 0:
                current_obj.append(char)

        parsed_data = []
        for obj_str in objects:
            def get_field_val(field_name):
                m_str = re.search(rf'(?:["\'`]?{field_name}["\'`]?)\s*:\s*(["\'`])(.*?)\1', obj_str, re.DOTALL)
                if m_str:
                    return m_str.group(2).strip()
                m_num = re.search(rf'(?:["\'`]?{field_name}["\'`]?)\s*:\s*(\d+\.?\d*)', obj_str)
                if m_num:
                    return m_num.group(1).strip()
                return ""

            item = {
                'id': int(get_field_val('id') or 0),
                'title': get_field_val('title'),
                'year': get_field_val('year'),
                'rating': get_field_val('rating'),
                'image': get_field_val('image'),
                'modalImage': get_field_val('modalImage'),
                'description': get_field_val('description'),
                'insights': get_field_val('insights'),
                'director': get_field_val('director'),
                'duration': get_field_val('duration'),
            }

            cat_match = re.search(r'(?:["\'`]?category["\'`]?)\s*:\s*\[(.*?)\]', obj_str, re.DOTALL)
            if cat_match:
                cats = re.findall(r'["\'`](.*?)["\'`]', cat_match.group(1))
                item['category'] = ",".join(cats)
            else:
                item['category'] = ""

            if item['title']:
                parsed_data.append(item)
        return parsed_data
    except Exception as ex:
        print(f"Error parsing templates: {ex}")
        return []


DEFAULT_MOVIES = [
    {
        "id": 101, "title": "A Silent Voice", "year": "2016", "rating": "9.0",
        "image": "https://i.pinimg.com/1200x/93/95/d4/9395d445ecbd3f13094ae8b10c0b3aeb.jpg",
        "modalImage": "https://i.pinimg.com/1200x/82/7f/f9/827ff9cd3db798ee43ee68dcca56cf29.jpg",
        "category": "Drama, School, Psychological, Romance, Featured",
        "description": "A former bully seeks redemption by befriending the deaf girl he once tormented.",
        "insights": "A profoundly human story tackling bullying, guilt, and healing with elegance and depth.",
        "director": "Naoko Yamada", "duration": "129 min"
    },
    {
        "id": 102, "title": "Your Name", "year": "2016", "rating": "8.9",
        "image": "https://i.pinimg.com/1200x/75/a9/32/75a93259685a73e4db9a0ff39ef2a2c6.jpg",
        "modalImage": "https://i.pinimg.com/1200x/75/a9/32/75a93259685a73e4db9a0ff39ef2a2c6.jpg",
        "category": "Romance, Fantasy, Drama, Featured, Award",
        "description": "Two high school strangers find themselves inexplicably swapping bodies across space and time.",
        "insights": "Makoto Shinkai's world-renowned masterpiece exploring destiny, memory, and profound emotional connection.",
        "director": "Makoto Shinkai", "duration": "106 min"
    },
    {
        "id": 103, "title": "Spirited Away", "year": "2001", "rating": "8.6",
        "image": "https://i.pinimg.com/736x/95/95/95/95959595959595959595959595959595.jpg",
        "modalImage": "https://i.pinimg.com/1200x/75/a9/32/75a93259685a73e4db9a0ff39ef2a2c6.jpg",
        "category": "Fantasy, Adventure, Ghibli, Award, Featured",
        "description": "A ten-year-old girl wanders into a spirit world bathhouse to save her parents.",
        "insights": "Academy Award winner for Best Animated Feature, widely considered one of the greatest films ever made.",
        "director": "Hayao Miyazaki", "duration": "125 min"
    },
    {
        "id": 104, "title": "Demon Slayer: Mugen Train", "year": "2020", "rating": "8.2",
        "image": "https://i.pinimg.com/736x/43/fa/bb/43fabbcfb5fef9a3e21508db86cbefb4.jpg",
        "modalImage": "https://i.pinimg.com/1200x/19/22/e1/1922e11894d01b1e3260c6d2d47781a9.jpg",
        "category": "Action, Fantasy, Supernatural, Featured, New",
        "description": "Tanjiro and Flame Hashira Rengoku board a sinister train to battle a powerful demon.",
        "insights": "The highest-grossing anime film of all time worldwide, renowned for spectacular Ufotable animation.",
        "director": "Haruo Sotozaki", "duration": "117 min"
    },
    {
        "id": 105, "title": "Weathering With You", "year": "2019", "rating": "7.5",
        "image": "https://i.pinimg.com/736x/de/4e/01/de4e0140ecdce63e20abb54720d397e4.jpg",
        "modalImage": "https://i.pinimg.com/736x/e6/7a/10/e67a10863ace14b5a7fc2edb5db38158.jpg",
        "category": "Fantasy, Romance, Drama, Supernatural, Featured",
        "description": "A runaway boy meets a girl who can control the weather in Tokyo.",
        "insights": "A visually breathtaking urban romance exploring youth, sacrifice, and nature.",
        "director": "Makoto Shinkai", "duration": "112 min"
    }
]

DEFAULT_ANIME = [
    {
        "id": 1, "title": "One Piece", "year": "1999", "rating": "8.75",
        "image": "https://i.pinimg.com/736x/65/e9/a6/65e9a662394181e7ac4632cf202c2671.jpg",
        "modalImage": "https://i.pinimg.com/1200x/89/13/be/8913be5f2ffacb07c34168c4abc776c0.jpg",
        "category": "Popular, Adventure, Fantasy, Action, Shonen",
        "description": "Monkey D. Luffy sets out to become the King of the Pirates by finding the legendary treasure One Piece.",
        "insights": "One Piece is a monumental saga known for rich world-building, emotional arcs, and decades-spanning development."
    },
    {
        "id": 2, "title": "Bleach", "year": "2004", "rating": "8.20",
        "image": "https://i.pinimg.com/1200x/64/68/f4/6468f4516814b2bd80aca8477f017b1f.jpg",
        "modalImage": "https://i.pinimg.com/1200x/40/d4/19/40d4197c896425fbf04be9df708747d5.jpg",
        "category": "Action, Supernatural, Shonen, Popular",
        "description": "Ichigo Kurosaki becomes a Soul Reaper to protect the living from evil spirits.",
        "insights": "Bleach captivates with kinetic swordplay, zanpakutō abilities, and soul-reaping mythology."
    },
    {
        "id": 3, "title": "Jujutsu Kaisen", "year": "2020", "rating": "8.60",
        "image": "https://i.pinimg.com/736x/b4/48/c2/b448c215859a528035f64b10d992d968.jpg",
        "modalImage": "https://i.pinimg.com/1200x/9b/38/0e/9b380e1eb89577504cef7d4d61768904.jpg",
        "category": "Popular, Top, New, Shonen, Action, Supernatural",
        "description": "A boy swallows a cursed talisman and becomes entangled in the world of sorcerers and curses.",
        "insights": "Jujutsu Kaisen elevates modern shōnen with dark curse lore and astounding MAPPA animation."
    },
    {
        "id": 4, "title": "Naruto", "year": "2002", "rating": "8.30",
        "image": "https://i.pinimg.com/736x/21/df/b4/21dfb47bb1e7d8ceaa8b2b7379d28e7e.jpg",
        "modalImage": "https://i.pinimg.com/1200x/18/85/6f/18856fe8a804bd91b359f13e71fb3313.jpg",
        "category": "Popular, Action, Ninja, Shonen, Adventure",
        "description": "Naruto Uzumaki seeks recognition from his peers and dreams of becoming the Hokage.",
        "insights": "Naruto's journey from outcast to hero embodies the core of shōnen spirit with iconic ninjutsu battles."
    },
    {
        "id": 5, "title": "Attack on Titan", "year": "2013", "rating": "9.00",
        "image": "https://i.pinimg.com/736x/e4/c7/23/e4c723f5bdf8e9dbf4eb4d0ae25cfa99.jpg",
        "modalImage": "https://i.pinimg.com/1200x/b2/24/ce/b224ce3497fd7bf791338fe943bebe2d.jpg",
        "category": "Popular, Top, Action, Fantasy, Drama",
        "description": "Humanity fights for survival against giant humanoid Titans behind massive walls.",
        "insights": "A masterclass in narrative tension, geopolitical allegory, and unexpected plot reveals."
    }
]


def init_db(app):
    """
    Initialize Flask-SQLAlchemy with the configured engine, create tables, and seed initial data.
    """
    uri = get_db_uri(DATABASE)
    app.config['SQLALCHEMY_DATABASE_URI'] = uri
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    if is_postgres():
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_size': 10,
            'max_overflow': 20,
            'pool_pre_ping': True,
            'pool_recycle': 300
        }

    # Bind SQLAlchemy to app if not already initialized
    if 'sqlalchemy' not in app.extensions:
        db.init_app(app)
    else:
        sa = app.extensions['sqlalchemy']
        options = sa._engine_options.copy()
        options['url'] = uri
        sa._apply_driver_defaults(options, app)
        if app in sa._app_engines and None in sa._app_engines[app]:
            try:
                sa._app_engines[app][None].dispose()
            except Exception:
                pass
        sa._app_engines.setdefault(app, {})[None] = sa._make_engine(None, options, app)

    with app.app_context():
        # Fast create tables via SQLAlchemy metadata
        db.create_all()

        # Seed recruiter demo accounts
        _seed_demo_accounts()

        # Seed initial anime catalog if empty
        if Anime.query.count() == 0:
            print("Seeding anime data into database...")
            base_dir = os.path.dirname(os.path.abspath(__file__))
            anime_items = _extract_js_objects(os.path.join(base_dir, 'templates/anime.html'), 'animeData')
            if not anime_items:
                anime_items = DEFAULT_ANIME

            for a in anime_items:
                existing = db.session.get(Anime, a['id'])
                if not existing:
                    anime = Anime(
                        id=a['id'],
                        title=a['title'],
                        year=a.get('year', ''),
                        rating=a.get('rating', ''),
                        image=a.get('image', ''),
                        modalImage=a.get('modalImage', a.get('image', '')),
                        category=a.get('category', ''),
                        description=a.get('description', ''),
                        insights=a.get('insights', ''),
                        episodes=a.get('episodes', ''),
                        status=a.get('status', 'Finished'),
                        studio=a.get('studio', ''),
                        japanese_title=a.get('japanese_title', ''),
                        main_characters=a.get('main_characters', '')
                    )
                    db.session.add(anime)
            db.session.commit()
            print(f"Seeded {len(anime_items)} anime titles.")

        # Seed initial movies catalog if empty
        if Movie.query.count() == 0:
            print("Seeding movies data into database...")
            base_dir = os.path.dirname(os.path.abspath(__file__))
            movie_items = _extract_js_objects(os.path.join(base_dir, 'templates/movies.html'), 'moviesData')
            if not movie_items:
                movie_items = DEFAULT_MOVIES

            for m in movie_items:
                existing = db.session.get(Movie, m['id'])
                if not existing:
                    movie = Movie(
                        id=m['id'],
                        title=m['title'],
                        year=m.get('year', ''),
                        rating=m.get('rating', ''),
                        image=m.get('image', ''),
                        modalImage=m.get('modalImage', m.get('image', '')),
                        category=m.get('category', ''),
                        description=m.get('description', ''),
                        insights=m.get('insights', ''),
                        director=m.get('director', 'Unknown'),
                        duration=m.get('duration', '120 min'),
                        japanese_title=m.get('japanese_title', ''),
                        main_characters=m.get('main_characters', '')
                    )
                    db.session.add(movie)
            db.session.commit()
            print(f"Seeded {len(movie_items)} movies.")
