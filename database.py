"""
Database module for ChibiBytes application.
Handles database initialization and connection management for both
Neon PostgreSQL (Cloud) and SQLite3 (Local fallback).
"""

import os
import sqlite3
import re
from flask import g
from dotenv import load_dotenv

load_dotenv()

DATABASE = 'ChibiBytes_users.db'
DATABASE_URL = os.getenv('DATABASE_URL')


class PostgresCursorWrapper:
    """Wrapper for psycopg2 cursor to normalize parameter syntax ('?' -> '%s')."""

    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, query, params=None):
        if params is None:
            params = ()
        # Convert ? placeholders to %s for psycopg2
        pg_query = query.replace('?', '%s')
        # Convert INSERT OR REPLACE INTO for Postgres
        if 'INSERT OR REPLACE INTO' in pg_query.upper():
            pg_query = pg_query.replace('INSERT OR REPLACE INTO', 'INSERT INTO', 1)
            # Append ON CONFLICT (id) DO NOTHING if id column is specified
            if ' (id,' in pg_query or ' (id)' in pg_query:
                pg_query += ' ON CONFLICT (id) DO NOTHING'
            elif 'ON CONFLICT' not in pg_query.upper():
                pg_query += ' ON CONFLICT DO NOTHING'

        if params:
            return self._cursor.execute(pg_query, params)
        return self._cursor.execute(pg_query)

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    @property
    def rowcount(self):
        return self._cursor.rowcount


class PostgresConnWrapper:
    """Wrapper for psycopg2 connection."""

    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        import psycopg2.extras
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        return PostgresCursorWrapper(cur)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


_pg_pool = None

def get_pg_pool():
    global _pg_pool
    db_url = os.getenv('DATABASE_URL')
    if db_url and _pg_pool is None:
        try:
            import psycopg2.pool
            _pg_pool = psycopg2.pool.ThreadedConnectionPool(1, 10, db_url)
        except Exception as e:
            print(f"Error creating PG pool: {e}")
    return _pg_pool


def is_postgres():
    """Check if current connection is using PostgreSQL."""
    return bool(os.getenv('DATABASE_URL'))


def get_db():
    """
    Get database connection (Neon PostgreSQL connection pool if DATABASE_URL is set, else SQLite3).
    """
    db = getattr(g, '_database', None)
    if db is None:
        db_url = os.getenv('DATABASE_URL')
        if db_url:
            pool = get_pg_pool()
            if pool:
                conn = pool.getconn()
                g._pg_conn = conn
                db = g._database = PostgresConnWrapper(conn)
            else:
                import psycopg2
                conn = psycopg2.connect(db_url)
                db = g._database = PostgresConnWrapper(conn)
        else:
            conn = sqlite3.connect(DATABASE)
            conn.row_factory = sqlite3.Row
            db = g._database = conn
    return db


def close_connection(exception=None):
    """Return PostgreSQL connection to pool or close SQLite connection on app context teardown."""
    db = getattr(g, '_database', None)
    if db is not None:
        pg_conn = getattr(g, '_pg_conn', None)
        if pg_conn:
            try:
                if not pg_conn.closed:
                    pg_conn.rollback()  # Reset transaction state before returning to pool
            except Exception:
                pass
            pool = get_pg_pool()
            if pool:
                try:
                    pool.putconn(pg_conn)
                except Exception:
                    pass
            g._pg_conn = None
            g._database = None
        else:
            try:
                db.close()
            except Exception:
                pass
            g._database = None


_is_db_initialized = False


def _seed_demo_accounts(cursor, db):
    """Ensure recruiter-friendly demo accounts (demo_admin & demo_user) exist."""
    try:
        from werkzeug.security import generate_password_hash
        demo_accounts = [
            ('demo_admin', generate_password_hash('Admin123!', method='pbkdf2:sha256'), 'demo.admin@chibibytes.com', 'admin'),
            ('demo_user', generate_password_hash('User123!', method='pbkdf2:sha256'), 'demo.user@chibibytes.com', 'user')
        ]
        for uname, pwd_hash, email, urole in demo_accounts:
            cursor.execute('SELECT id FROM users WHERE username = ?', (uname,))
            if not cursor.fetchone():
                cursor.execute('''
                    INSERT INTO users (username, password, email, role)
                    VALUES (?, ?, ?, ?)
                ''', (uname, pwd_hash, email, urole))
        db.commit()
    except Exception as ex:
        print(f"Demo accounts notice: {ex}")
        try:
            db.rollback()
        except Exception:
            pass


def init_db(app):
    """
    Initialize database with tables, schema migrations, and seed data.
    Uses fast-path table existence check to avoid redundant round trips on server boot.
    """
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        use_pg = is_postgres()

        if use_pg:
            # Fast-path check for Neon PostgreSQL: if anime table already exists, skip slow DDL migrations
            try:
                cursor.execute("SELECT 1 FROM information_schema.tables WHERE table_name = 'anime'")
                if cursor.fetchone():
                    _seed_demo_accounts(cursor, db)
                    return
            except Exception:
                pass

            # PostgreSQL schema
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(255) UNIQUE NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    role VARCHAR(50) DEFAULT 'user',
                    avatar_url TEXT DEFAULT '',
                    bio VARCHAR(255) DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS watchlist (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    anime_id INTEGER NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    year VARCHAR(50),
                    rating VARCHAR(50),
                    image TEXT,
                    category TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    episodes VARCHAR(50) DEFAULT '',
                    media_type VARCHAR(20) DEFAULT 'anime',
                    is_favorite BOOLEAN DEFAULT FALSE,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            ''')
            cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_watchlist_user_anime ON watchlist (user_id, anime_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_watchlist_user_added ON watchlist (user_id, added_at DESC)')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS anime (
                    id INTEGER PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    year VARCHAR(50),
                    rating VARCHAR(50),
                    image TEXT NOT NULL,
                    modalImage TEXT NOT NULL,
                    category TEXT NOT NULL,
                    description TEXT NOT NULL,
                    insights TEXT NOT NULL,
                    episodes VARCHAR(50) DEFAULT '',
                    status VARCHAR(50) DEFAULT 'Finished',
                    studio VARCHAR(100) DEFAULT '',
                    japanese_title VARCHAR(255) DEFAULT '',
                    main_characters TEXT DEFAULT ''
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS movies (
                    id INTEGER PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    year VARCHAR(50),
                    rating VARCHAR(50),
                    image TEXT NOT NULL,
                    modalImage TEXT NOT NULL,
                    category TEXT NOT NULL,
                    description TEXT NOT NULL,
                    insights TEXT NOT NULL,
                    director VARCHAR(255) NOT NULL,
                    duration VARCHAR(50) NOT NULL,
                    japanese_title VARCHAR(255) DEFAULT '',
                    main_characters TEXT DEFAULT ''
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reviews (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    anime_id INTEGER NOT NULL,
                    media_type VARCHAR(20) DEFAULT 'anime',
                    score NUMERIC(3, 1) NOT NULL,
                    comment TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    role VARCHAR(20) NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Optional Postgres Trigram extension for fast fuzzy search
            try:
                cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_anime_title_trgm ON anime USING gin (title gin_trgm_ops)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_movies_title_trgm ON movies USING gin (title gin_trgm_ops)")
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass

        else:
            # SQLite schema
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    role TEXT DEFAULT 'user',
                    avatar_url TEXT DEFAULT '',
                    bio TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS watchlist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    anime_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    year TEXT,
                    rating TEXT,
                    image TEXT,
                    category TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    episodes TEXT DEFAULT '',
                    media_type TEXT DEFAULT 'anime',
                    is_favorite INTEGER DEFAULT 0,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS anime (
                    id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    year TEXT,
                    rating TEXT,
                    image TEXT NOT NULL,
                    modalImage TEXT NOT NULL,
                    category TEXT NOT NULL,
                    description TEXT NOT NULL,
                    insights TEXT NOT NULL,
                    episodes TEXT DEFAULT '',
                    status TEXT DEFAULT 'Finished',
                    studio TEXT DEFAULT '',
                    japanese_title TEXT DEFAULT '',
                    main_characters TEXT DEFAULT ''
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS movies (
                    id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    year TEXT,
                    rating TEXT,
                    image TEXT NOT NULL,
                    modalImage TEXT NOT NULL,
                    category TEXT NOT NULL,
                    description TEXT NOT NULL,
                    insights TEXT NOT NULL,
                    director TEXT NOT NULL,
                    duration TEXT NOT NULL,
                    japanese_title TEXT DEFAULT '',
                    main_characters TEXT DEFAULT ''
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    anime_id INTEGER NOT NULL,
                    media_type TEXT DEFAULT 'anime',
                    score REAL NOT NULL,
                    comment TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')

        # Safe schema migrations for existing databases (Postgres and SQLite)
        if use_pg:
            # Clean up deprecated trailer_url column
            try:
                cursor.execute("ALTER TABLE anime DROP COLUMN IF EXISTS trailer_url")
                cursor.execute("ALTER TABLE movies DROP COLUMN IF EXISTS trailer_url")
                db.commit()
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass

            pg_cols = [
                ("users", "role", "VARCHAR(50) DEFAULT 'user'"),
                ("users", "avatar_url", "TEXT DEFAULT ''"),
                ("users", "bio", "VARCHAR(255) DEFAULT ''"),
                ("watchlist", "is_favorite", "BOOLEAN DEFAULT FALSE"),
                ("watchlist", "category", "TEXT DEFAULT ''"),
                ("watchlist", "description", "TEXT DEFAULT ''"),
                ("watchlist", "episodes", "VARCHAR(50) DEFAULT ''"),
                ("watchlist", "media_type", "VARCHAR(20) DEFAULT 'anime'"),
                ("anime", "episodes", "VARCHAR(50) DEFAULT ''"),
                ("anime", "status", "VARCHAR(50) DEFAULT 'Finished'"),
                ("anime", "studio", "VARCHAR(100) DEFAULT ''"),
                ("anime", "japanese_title", "VARCHAR(255) DEFAULT ''"),
                ("anime", "main_characters", "TEXT DEFAULT ''"),
                ("movies", "japanese_title", "VARCHAR(255) DEFAULT ''"),
                ("movies", "main_characters", "TEXT DEFAULT ''"),
            ]
            for tbl, col, col_def in pg_cols:
                try:
                    cursor.execute(f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS {col} {col_def}")
                    db.commit()
                except Exception:
                    try:
                        db.rollback()
                    except Exception:
                        pass
        else:
            sqlite_cols = [
                ("users", "role", "TEXT DEFAULT 'user'"),
                ("users", "avatar_url", "TEXT DEFAULT ''"),
                ("users", "bio", "TEXT DEFAULT ''"),
                ("watchlist", "is_favorite", "INTEGER DEFAULT 0"),
                ("watchlist", "category", "TEXT DEFAULT ''"),
                ("watchlist", "description", "TEXT DEFAULT ''"),
                ("watchlist", "episodes", "TEXT DEFAULT ''"),
                ("watchlist", "media_type", "TEXT DEFAULT 'anime'"),
                ("anime", "episodes", "TEXT DEFAULT ''"),
                ("anime", "status", "TEXT DEFAULT 'Finished'"),
                ("anime", "studio", "TEXT DEFAULT ''"),
                ("anime", "japanese_title", "TEXT DEFAULT ''"),
                ("anime", "main_characters", "TEXT DEFAULT ''"),
                ("movies", "japanese_title", "TEXT DEFAULT ''"),
                ("movies", "main_characters", "TEXT DEFAULT ''"),
            ]
            for tbl, col, col_def in sqlite_cols:
                try:
                    cursor.execute(f"PRAGMA table_info({tbl})")
                    cols = [row[1] if isinstance(row, (list, tuple)) else row['name'] for row in cursor.fetchall()]
                    if col not in cols:
                        cursor.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {col_def}")
                        db.commit()
                except Exception:
                    try:
                        db.rollback()
                    except Exception:
                        pass

        # Backfill existing watchlist items with category, description, and media_type from catalog
        try:
            if use_pg:
                cursor.execute('''
                    UPDATE watchlist w
                    SET category = COALESCE(NULLIF(w.category, ''), a.category, ''),
                        description = COALESCE(NULLIF(w.description, ''), a.description, '')
                    FROM anime a
                    WHERE w.anime_id = a.id AND (w.category IS NULL OR w.category = '');
                ''')
                cursor.execute('''
                    UPDATE watchlist w
                    SET category = COALESCE(NULLIF(w.category, ''), m.category, ''),
                        description = COALESCE(NULLIF(w.description, ''), m.description, ''),
                        episodes = COALESCE(NULLIF(w.episodes, ''), m.duration, ''),
                        media_type = 'movie'
                    FROM movies m
                    WHERE w.anime_id = m.id AND (w.category IS NULL OR w.category = '');
                ''')
            else:
                cursor.execute('''
                    UPDATE watchlist
                    SET category = (SELECT category FROM anime WHERE anime.id = watchlist.anime_id),
                        description = (SELECT description FROM anime WHERE anime.id = watchlist.anime_id)
                    WHERE (category IS NULL OR category = '') AND EXISTS (SELECT 1 FROM anime WHERE anime.id = watchlist.anime_id);
                ''')
                cursor.execute('''
                    UPDATE watchlist
                    SET category = (SELECT category FROM movies WHERE movies.id = watchlist.anime_id),
                        description = (SELECT description FROM movies WHERE movies.id = watchlist.anime_id),
                        episodes = (SELECT duration FROM movies WHERE movies.id = watchlist.anime_id),
                        media_type = 'movie'
                    WHERE (category IS NULL OR category = '') AND EXISTS (SELECT 1 FROM movies WHERE movies.id = watchlist.anime_id);
                ''')
            db.commit()
        except Exception as e:
            print(f"Watchlist backfill note: {e}")
            try:
                db.rollback()
            except Exception:
                pass

        # Seed recruiter-friendly demo accounts (demo_admin & demo_user)
        try:
            from werkzeug.security import generate_password_hash
            demo_accounts = [
                ('demo_admin', generate_password_hash('Admin123!', method='pbkdf2:sha256'), 'demo.admin@chibibytes.com', 'admin'),
                ('demo_user', generate_password_hash('User123!', method='pbkdf2:sha256'), 'demo.user@chibibytes.com', 'user')
            ]
            for uname, pwd_hash, email, urole in demo_accounts:
                cursor.execute('SELECT id FROM users WHERE username = ?', (uname,))
                if not cursor.fetchone():
                    cursor.execute('''
                        INSERT INTO users (username, password, email, role)
                        VALUES (?, ?, ?, ?)
                    ''', (uname, pwd_hash, email, urole))
            db.commit()
        except Exception as ex:
            print(f"Demo accounts notice: {ex}")
            try:
                db.rollback()
            except Exception:
                pass

        # Seed data if tables are empty
        cursor.execute("SELECT COUNT(*) FROM anime")
        row = cursor.fetchone()
        anime_count = list(row.values())[0] if isinstance(row, dict) else row[0]

        cursor.execute("SELECT COUNT(*) FROM movies")
        row = cursor.fetchone()
        movies_count = list(row.values())[0] if isinstance(row, dict) else row[0]

        if anime_count == 0 or movies_count == 0:
            def extract_js_objects(file_path, var_name):
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
                        item = {}

                        def get_field_val(field_name):
                            m_str = re.search(rf'(?:["\'`]?{field_name}["\'`]?)\s*:\s*(["\'`])(.*?)\1', obj_str, re.DOTALL)
                            if m_str:
                                return m_str.group(2).strip()
                            m_num = re.search(rf'(?:["\'`]?{field_name}["\'`]?)\s*:\s*(\d+\.?\d*)', obj_str)
                            if m_num:
                                return m_num.group(1).strip()
                            return ""

                        item['id'] = int(get_field_val('id') or 0)
                        item['title'] = get_field_val('title')
                        item['year'] = get_field_val('year')
                        item['rating'] = get_field_val('rating')
                        item['image'] = get_field_val('image')
                        item['modalImage'] = get_field_val('modalImage')
                        item['description'] = get_field_val('description')
                        item['insights'] = get_field_val('insights')

                        cat_match = re.search(r'(?:["\'`]?category["\'`]?)\s*:\s*\[(.*?)\]', obj_str, re.DOTALL)
                        if cat_match:
                            cats = re.findall(r'["\'`](.*?)["\'`]', cat_match.group(1))
                            item['category'] = ",".join(cats)
                        else:
                            item['category'] = ""

                        item['director'] = get_field_val('director')
                        item['duration'] = get_field_val('duration')

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

            base_dir = os.path.dirname(os.path.abspath(__file__))

            if anime_count == 0:
                print("Seeding anime data into database...")
                anime_items = extract_js_objects(os.path.join(base_dir, 'templates/anime.html'), 'animeData')
                if not anime_items:
                    anime_items = DEFAULT_ANIME

                for a in anime_items:
                    cursor.execute('''
                        INSERT INTO anime (id, title, year, rating, image, modalImage, category, description, insights)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT (id) DO NOTHING
                    ''', (a['id'], a['title'], a['year'], a['rating'], a['image'], a['modalImage'], a['category'], a['description'], a['insights']))
                print(f"Seeded {len(anime_items)} anime titles.")

            if movies_count == 0:
                print("Seeding movies data into database...")
                movie_items = extract_js_objects(os.path.join(base_dir, 'templates/movies.html'), 'moviesData')
                if not movie_items:
                    movie_items = DEFAULT_MOVIES

                for m in movie_items:
                    cursor.execute('''
                        INSERT INTO movies (id, title, year, rating, image, modalImage, category, description, insights, director, duration)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT (id) DO NOTHING
                    ''', (m['id'], m['title'], m['year'], m['rating'], m['image'], m['modalImage'], m['category'], m['description'], m['insights'], m['director'], m['duration']))
                print(f"Seeded {len(movie_items)} movies.")

            db.commit()

