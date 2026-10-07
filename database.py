"""
Database module for ChibiBytes application.
Standardized exclusively on PostgreSQL (Neon Cloud Database) with connection pooling.
SQLite has been completely removed to ensure seamless live cloud hosting.
"""

import os
import re
from flask import g
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash
from sqlalchemy import text
from models import db, User, Watchlist, Anime, Movie, Review, ChatMessage

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')


def get_db_uri():
    """
    Retrieve and normalize the PostgreSQL connection URI for SQLAlchemy.
    Falls back to a local SQLite database during automated test execution if DATABASE_URL is unset.
    Raises ValueError if DATABASE_URL is missing in non-test production/runtime environments.
    """
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        import sys
        if os.getenv('TESTING') or 'unittest' in sys.modules or 'pytest' in sys.modules:
            return 'sqlite:///test_local.db'
        raise ValueError(
            "CRITICAL: DATABASE_URL environment variable is missing. "
            "ChibiBytes is configured strictly for PostgreSQL cloud hosting (Neon). "
            "Please provide a valid PostgreSQL connection string in your .env or host configuration."
        )

    # Normalize postgres:// or postgresql:// to postgresql+psycopg2:// for SQLAlchemy 2.0+
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql+psycopg2://', 1)
    elif db_url.startswith('postgresql://') and not db_url.startswith('postgresql+psycopg2://'):
        db_url = db_url.replace('postgresql://', 'postgresql+psycopg2://', 1)
    return db_url


def is_postgres():
    """Returns True if connected to PostgreSQL."""
    try:
        if db and hasattr(db, 'engine') and db.engine:
            return db.engine.dialect.name == 'postgresql'
    except Exception:
        pass
    db_url = os.getenv('DATABASE_URL', '')
    return db_url.startswith('postgres')


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
        "id": 101,
        "title": "A Silent Voice",
        "year": "2016",
        "rating": "9.0",
        "image": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20954-sYRfE5jQRtSB.jpg",
        "modalImage": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/20954-f30bHMXa5Qoe.jpg",
        "category": "Drama, School, Psychological, Romance, Featured",
        "description": "A former bully seeks redemption by befriending the deaf girl he once tormented in elementary school.",
        "insights": "Kyoto Animation's masterpiece exploring repentance, forgiveness, and human vulnerability with stunning aesthetic sensitivity.",
        "director": "Naoko Yamada",
        "duration": "129 min",
        "trailer_url": "https://www.youtube-nocookie.com/embed/nfK6UgLra7g",
        "trailer_youtube_id": "nfK6UgLra7g"
    },
    {
        "id": 102,
        "title": "Your Name",
        "year": "2016",
        "rating": "8.9",
        "image": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21519-SUo3ZQuCbYhJ.png",
        "modalImage": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/21519-1ayMXgNlmByb.jpg",
        "category": "Romance, Fantasy, Drama, Featured, Award",
        "description": "Two high school strangers find themselves inexplicably swapping bodies across space, time, and memory.",
        "insights": "Makoto Shinkai's world-renowned triumph exploring cosmic destiny, youth, and unforgettable emotional connection.",
        "director": "Makoto Shinkai",
        "duration": "106 min",
        "trailer_url": "https://www.youtube-nocookie.com/embed/xU47nhruN-Q",
        "trailer_youtube_id": "xU47nhruN-Q"
    },
    {
        "id": 103,
        "title": "Spirited Away",
        "year": "2001",
        "rating": "8.6",
        "image": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx199-sWefXJvXkDOb.jpg",
        "modalImage": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/199-Sm2RU5PSqw7T.jpg",
        "category": "Fantasy, Adventure, Ghibli, Award, Featured",
        "description": "A ten-year-old girl wanders into a spirit world bathhouse to save her parents who were transformed into pigs.",
        "insights": "Academy Award winner for Best Animated Feature, widely celebrated as one of the greatest cinematic achievements in history.",
        "director": "Hayao Miyazaki",
        "duration": "125 min",
        "trailer_url": "https://www.youtube-nocookie.com/embed/ByXuk9QqQkk",
        "trailer_youtube_id": "ByXuk9QqQkk"
    },
    {
        "id": 104,
        "title": "Demon Slayer: Mugen Train",
        "year": "2020",
        "rating": "8.2",
        "image": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx112151-1qlQwPB1RrJe.png",
        "modalImage": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx112151-1qlQwPB1RrJe.png",
        "category": "Action, Fantasy, Supernatural, Featured, New",
        "description": "Tanjiro and Flame Hashira Kyojuro Rengoku board a sinister train under the influence of Enmu to battle a formidable demon threat.",
        "insights": "The highest-grossing anime film of all time worldwide, renowned for spectacular Ufotable animation and heart-wrenching emotional climax.",
        "director": "Haruo Sotozaki",
        "duration": "117 min",
        "trailer_url": "https://www.youtube-nocookie.com/embed/ATJYac_dORw",
        "trailer_youtube_id": "ATJYac_dORw"
    },
    {
        "id": 105,
        "title": "Weathering With You",
        "year": "2019",
        "rating": "7.5",
        "image": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx106286-5COcpd0J9VbL.png",
        "modalImage": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/106286-3oKwiwjd7Wkm.jpg",
        "category": "Fantasy, Romance, Drama, Supernatural, Featured",
        "description": "A runaway high school boy in Tokyo meets a sunshine girl who possesses the mystical ability to stop rain and clear the sky.",
        "insights": "A visually breathtaking urban romance exploring youth, personal sacrifice, and humanity's relationship with climate and destiny.",
        "director": "Makoto Shinkai",
        "duration": "112 min",
        "trailer_url": "https://www.youtube-nocookie.com/embed/Q6iK6DjV_iE",
        "trailer_youtube_id": "Q6iK6DjV_iE"
    },
    {
        "id": 106,
        "title": "Howl's Moving Castle",
        "year": "2004",
        "rating": "8.8",
        "image": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx431-o8Lj3XkjHm2k.jpg",
        "modalImage": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/431-fLBlvTgdqLCz.jpg",
        "category": "Fantasy, Adventure, Ghibli, Romance, Award",
        "description": "After being cursed with an old woman's body by a spiteful witch, young milliner Sophie encounters wizard Howl and his walking castle.",
        "insights": "Miyazaki's anti-war fantasy romance celebrated for Joe Hisaishi's enchanting score and boundless visual imagination.",
        "director": "Hayao Miyazaki",
        "duration": "119 min",
        "trailer_url": "https://www.youtube-nocookie.com/embed/iwROgK94zcM",
        "trailer_youtube_id": "iwROgK94zcM"
    },
    {
        "id": 107,
        "title": "Princess Mononoke",
        "year": "1997",
        "rating": "8.9",
        "image": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx164-ySuGzCWVw2cL.jpg",
        "modalImage": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/164-Aj6MINy7VTfs.jpg",
        "category": "Action, Adventure, Ghibli, Fantasy, Classic",
        "description": "Stricken with a deadly demon curse, Prince Ashitaka journeys to western lands and finds himself caught between iron-working humans and the spirits of the sacred forest.",
        "insights": "A towering cinematic achievement presenting nuanced ecological conflict without clean villains or simple answers.",
        "director": "Hayao Miyazaki",
        "duration": "134 min",
        "trailer_url": "https://www.youtube-nocookie.com/embed/4OiMOHRDs14",
        "trailer_youtube_id": "4OiMOHRDs14"
    },
    {
        "id": 108,
        "title": "I Want to Eat Your Pancreas",
        "year": "2018",
        "rating": "8.6",
        "image": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx99750-pNyly9d3MEgV.jpg",
        "modalImage": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/99750-KPFW2Jv03b2B.jpg",
        "category": "Drama, Romance, School, Slice of Life",
        "description": "An aloof high school bookworm accidentally reads the secret diary of his vibrant classmate Sakura, discovering she is dying of pancreatic disease.",
        "insights": "An unforgettably tender tearjerker celebrating friendship, the fragility of existence, and finding joy in fleeting moments.",
        "director": "Shinichirou Ushijima",
        "duration": "108 min",
        "trailer_url": "https://www.youtube-nocookie.com/embed/MmoBvmJA9XI",
        "trailer_youtube_id": "MmoBvmJA9XI"
    },
    {
        "id": 109,
        "title": "Grave of the Fireflies",
        "year": "1988",
        "rating": "9.1",
        "image": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx578-vU6XcOlb1XFU.jpg",
        "modalImage": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/578.jpg",
        "category": "Drama, Historical, Ghibli, Award, Classic",
        "description": "Two orphaned Japanese siblings struggle to survive in the countryside during the harrowing final months of World War II.",
        "insights": "Widely cited as one of the most powerful anti-war statements ever put to film, executed with unflinching humanity.",
        "director": "Isao Takahata",
        "duration": "89 min",
        "trailer_url": "https://www.youtube-nocookie.com/embed/4vPeTSRd580",
        "trailer_youtube_id": "4vPeTSRd580"
    },
    {
        "id": 110,
        "title": "Kiki's Delivery Service",
        "year": "1989",
        "rating": "8.3",
        "image": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx512-UwP8X4BR8YoM.png",
        "modalImage": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/512-Ssp3EE2NdeoA.jpg",
        "category": "Adventure, Comedy, Ghibli, Fantasy, Slice of Life",
        "description": "A resourceful 13-year-old witch moves to a seaside town with her talking black cat Jiji to establish a flying courier service.",
        "insights": "A comforting coming-of-age classic about finding independence, overcoming burnout, and rediscovering one's passions.",
        "director": "Hayao Miyazaki",
        "duration": "103 min",
        "trailer_url": "https://www.youtube-nocookie.com/embed/4bG17OYs-GA",
        "trailer_youtube_id": "4bG17OYs-GA"
    },
    {
        "id": 111,
        "title": "Castle in the Sky",
        "year": "1986",
        "rating": "8.5",
        "image": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx513-yM7Dlt65N4Rl.jpg",
        "modalImage": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/513-3zMLMyA0qH5n.jpg",
        "category": "Adventure, Fantasy, Sci-Fi, Ghibli, Classic",
        "description": "Young orphan Pazu and floating girl Sheeta race against sky pirates and secret agents to uncover the mythical airborne island of Laputa.",
        "insights": "The pioneering steampunk fantasy that established Studio Ghibli's hallmark soaring adventure thrills and lush vistas.",
        "director": "Hayao Miyazaki",
        "duration": "124 min",
        "trailer_url": "https://www.youtube-nocookie.com/embed/8ykEy-yPBFc",
        "trailer_youtube_id": "8ykEy-yPBFc"
    },
    {
        "id": 112,
        "title": "The Boy and the Heron",
        "year": "2023",
        "rating": "8.4",
        "image": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx109979-BRHXpBkCw4oc.jpg",
        "modalImage": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/109979-eeUPfBXMEflG.jpg",
        "category": "Animation, Adventure, Drama, Ghibli, Fantasy, Award",
        "description": "During World War II, young Mahito ventures into a world shared by the living and the dead after discovering an abandoned tower guided by a mysterious grey heron.",
        "insights": "Academy Award winner for Best Animated Feature, Hayao Miyazaki's semi-autobiographical visual opus on grief and creation.",
        "director": "Hayao Miyazaki",
        "duration": "124 min",
        "trailer_url": "https://www.youtube-nocookie.com/embed/t5khm-VjEu4",
        "trailer_youtube_id": "t5khm-VjEu4"
    }
]

DEFAULT_ANIME = [
    {
        "id": 1,
        "mal_id": 21,
        "title": "One Piece",
        "year": "1999",
        "rating": "8.75",
        "mal_score": 8.75,
        "image": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21-ELSYx3yMPcKM.jpg",
        "modalImage": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/21-wf37VakJmZqs.jpg",
        "banner_image": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/21-wf37VakJmZqs.jpg",
        "category": "Popular, Adventure, Fantasy, Action, Shonen",
        "description": "Monkey D. Luffy sets out to become the King of the Pirates by finding the legendary treasure One Piece with his Straw Hat crew.",
        "insights": "One Piece is a monumental saga celebrated for rich world-building, emotional arcs, and decades-spanning development.",
        "studio": "Toei Animation",
        "episodes": "1000+ eps",
        "status": "Currently Airing",
        "trailer_url": "https://www.youtube-nocookie.com/embed/S8_YwFLCh4U",
        "trailer_youtube_id": "S8_YwFLCh4U",
        "source": "manual"
    },
    {
        "id": 2,
        "mal_id": 41467,
        "title": "Bleach",
        "year": "2004",
        "rating": "9.05",
        "mal_score": 9.05,
        "image": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx269-d2GmRkJbMopq.png",
        "modalImage": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/269-08ar2HJOUAuL.jpg",
        "banner_image": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/269-08ar2HJOUAuL.jpg",
        "category": "Action, Supernatural, Shonen, Popular, Top",
        "description": "Substitute Soul Reaper Ichigo Kurosaki enters the final catastrophic war as Yhwach and the Quincy Wandenreich assault the Soul Society.",
        "insights": "Studio Pierrot's pinnacle achievement featuring movie-grade animation and Tomohisa Taguchi's stylish direction.",
        "studio": "Studio Pierrot",
        "episodes": "52 eps",
        "status": "Currently Airing",
        "trailer_url": "https://www.youtube-nocookie.com/embed/e8YBesRKq_U",
        "trailer_youtube_id": "e8YBesRKq_U",
        "source": "manual"
    },
    {
        "id": 3,
        "mal_id": 40748,
        "title": "Jujutsu Kaisen",
        "year": "2020",
        "rating": "8.65",
        "mal_score": 8.65,
        "image": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx113415-LHBAeoZDIsnF.jpg",
        "modalImage": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/113415-jQBSkxWAAk83.jpg",
        "banner_image": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/113415-jQBSkxWAAk83.jpg",
        "category": "Popular, Top, New, Shonen, Action, Supernatural",
        "description": "High schooler Yuji Itadori swallows a cursed finger of the King of Curses, plunging him into the secret and lethal realm of Jujutsu Sorcerers.",
        "insights": "MAPPA elevates modern sh\u014dnen with dark curse lore, kinetic combat animation, and unforgettable sorcery choreography.",
        "studio": "MAPPA",
        "episodes": "47 eps",
        "status": "Finished",
        "trailer_url": "https://www.youtube-nocookie.com/embed/pkKu9hLT-t8",
        "trailer_youtube_id": "pkKu9hLT-t8",
        "source": "manual"
    },
    {
        "id": 4,
        "mal_id": 20,
        "title": "Naruto",
        "year": "2002",
        "rating": "8.30",
        "mal_score": 8.3,
        "image": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20-dE6UHbFFg1A5.jpg",
        "modalImage": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/20-HHxhPj5JD13a.jpg",
        "banner_image": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/20-HHxhPj5JD13a.jpg",
        "category": "Popular, Action, Ninja, Shonen, Adventure",
        "description": "Naruto Uzumaki seeks recognition from his peers and dreams of becoming the Hokage of the Hidden Leaf Village.",
        "insights": "Naruto's journey from outcast to legendary hero embodies the core of sh\u014dnen spirit with iconic ninjutsu battles.",
        "studio": "Studio Pierrot",
        "episodes": "220 eps",
        "status": "Finished",
        "trailer_url": "https://www.youtube-nocookie.com/embed/-G9BqkgZXRA",
        "trailer_youtube_id": "-G9BqkgZXRA",
        "source": "manual"
    },
    {
        "id": 5,
        "mal_id": 16498,
        "title": "Attack on Titan",
        "year": "2013",
        "rating": "9.10",
        "mal_score": 9.1,
        "image": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx16498-buvcRTBx4NSm.jpg",
        "modalImage": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/16498-8jpFCOcDmneX.jpg",
        "banner_image": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/16498-8jpFCOcDmneX.jpg",
        "category": "Popular, Top, Action, Fantasy, Drama, Mystery",
        "description": "Humanity fights for survival against giant humanoid Titans behind massive walls until Eren Yeager vows to destroy them all.",
        "insights": "A masterclass in narrative tension, geopolitical allegory, and unexpected plot reveals.",
        "studio": "WIT Studio / MAPPA",
        "episodes": "89 eps",
        "status": "Finished",
        "trailer_url": "https://www.youtube-nocookie.com/embed/MGRm4IzK1SQ",
        "trailer_youtube_id": "MGRm4IzK1SQ",
        "source": "manual"
    },
    {
        "id": 6,
        "mal_id": 38000,
        "title": "Demon Slayer: Kimetsu no Yaiba",
        "year": "2019",
        "rating": "8.70",
        "mal_score": 8.7,
        "image": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx101922-WBsBl0ClmgYL.jpg",
        "modalImage": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/101922-33MtJGsUSxga.jpg",
        "banner_image": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/101922-33MtJGsUSxga.jpg",
        "category": "Popular, Top, Action, Fantasy, Historical, Shonen",
        "description": "Tanjiro Kamado becomes a Demon Slayer to avenge his family and cure his sister Nezuko, who was turned into a demon.",
        "insights": "Ufotable's legendary animation quality and swordplay choreography established a new gold standard.",
        "studio": "Ufotable",
        "episodes": "55 eps",
        "status": "Finished",
        "trailer_url": "https://www.youtube-nocookie.com/embed/VQGCKyvzIM4",
        "trailer_youtube_id": "VQGCKyvzIM4",
        "source": "manual"
    },
    {
        "id": 7,
        "mal_id": 1535,
        "title": "Death Note",
        "year": "2006",
        "rating": "8.62",
        "mal_score": 8.62,
        "image": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx1535-kUgkcrfOrkUM.jpg",
        "modalImage": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/1535.jpg",
        "banner_image": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/1535.jpg",
        "category": "Top, Psychological, Supernatural, Thriller, Mystery",
        "description": "High school genius Light Yagami discovers a supernatural notebook that kills anyone whose name is written in it.",
        "insights": "The quintessential psychological duel between Light Yagami and the eccentric detective L.",
        "studio": "Madhouse",
        "episodes": "37 eps",
        "status": "Finished",
        "trailer_url": "https://www.youtube-nocookie.com/embed/NlJZ-YgAt-c",
        "trailer_youtube_id": "NlJZ-YgAt-c",
        "source": "manual"
    },
    {
        "id": 8,
        "mal_id": 44511,
        "title": "Chainsaw Man",
        "year": "2022",
        "rating": "8.50",
        "mal_score": 8.5,
        "image": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx127230-DdP4vAdssLoz.png",
        "modalImage": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/127230-o8IRwCGVr9KW.jpg",
        "banner_image": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/127230-o8IRwCGVr9KW.jpg",
        "category": "Popular, New, Action, Supernatural, Horror, Shonen",
        "description": "Denji lives in poverty until he merges with chainsaw devil Pochita, transforming into Chainsaw Man to hunt deadly devils.",
        "insights": "Tatsuki Fujimoto's unapologetic, chaotic vision brought to life by MAPPA with cinematic grandeur.",
        "studio": "MAPPA",
        "episodes": "12 eps",
        "status": "Finished",
        "trailer_url": "https://www.youtube-nocookie.com/embed/v4yLeNt-kCU",
        "trailer_youtube_id": "v4yLeNt-kCU",
        "source": "manual"
    },
    {
        "id": 9,
        "mal_id": 52991,
        "title": "Frieren: Beyond Journey's End",
        "year": "2023",
        "rating": "9.35",
        "mal_score": 9.35,
        "image": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx154587-qQTzQnEJJ3oB.jpg",
        "modalImage": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/154587-ivXNJ23SM1xB.jpg",
        "banner_image": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/154587-ivXNJ23SM1xB.jpg",
        "category": "Top, Fantasy, Adventure, Drama, Award",
        "description": "After defeating the Demon King, elven mage Frieren embarks on a centuries-long journey to reflect on human lives and bonds.",
        "insights": "Ranked #1 of all time on MyAnimeList, universally praised for emotional resonance and mesmerizing magical battles.",
        "studio": "Madhouse",
        "episodes": "28 eps",
        "status": "Finished",
        "trailer_url": "https://www.youtube-nocookie.com/embed/ZEkwCGJ3o7M",
        "trailer_youtube_id": "ZEkwCGJ3o7M",
        "source": "manual"
    },
    {
        "id": 10,
        "mal_id": 11061,
        "title": "Hunter x Hunter (2011)",
        "year": "2011",
        "rating": "9.04",
        "mal_score": 9.04,
        "image": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx11061-y5gsT1hoHuHw.png",
        "modalImage": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/11061-8WkkTZ6duKpq.jpg",
        "banner_image": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/11061-8WkkTZ6duKpq.jpg",
        "category": "Top, Popular, Adventure, Action, Fantasy, Shonen",
        "description": "Gon Freecss discovers his father is a world-famous Hunter and takes the perilous Hunter Exam alongside loyal comrades.",
        "insights": "Widely considered the pinnacle of battle shonen with intricate Nen combat systems and the legendary Chimera Ant arc.",
        "studio": "Madhouse",
        "episodes": "148 eps",
        "status": "Finished",
        "trailer_url": "https://www.youtube-nocookie.com/embed/d6kBeJjTGnY",
        "trailer_youtube_id": "d6kBeJjTGnY",
        "source": "manual"
    },
    {
        "id": 11,
        "mal_id": 31964,
        "title": "My Hero Academia",
        "year": "2016",
        "rating": "8.25",
        "mal_score": 8.25,
        "image": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21459-nYh85uj2Fuwr.jpg",
        "modalImage": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/21459-yeVkolGKdGUV.jpg",
        "banner_image": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/21459-yeVkolGKdGUV.jpg",
        "category": "Popular, Action, Superhero, Shonen, School",
        "description": "Quirkless Izuku Midoriya inherits the power of Symbol of Peace All Might to attend U.A. High School and become the greatest hero.",
        "insights": "High-octane superhero storytelling with memorable hero-villain dynamic conflicts and Studio Bones' fluid animation.",
        "studio": "Bones",
        "episodes": "150+ eps",
        "status": "Finished",
        "trailer_url": "https://www.youtube-nocookie.com/embed/D5fYOnwYkj4",
        "trailer_youtube_id": "D5fYOnwYkj4",
        "source": "manual"
    },
    {
        "id": 12,
        "mal_id": 42310,
        "title": "Cyberpunk: Edgerunners",
        "year": "2022",
        "rating": "8.60",
        "mal_score": 8.6,
        "image": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx120377-ayZPoxiWt4Li.jpg",
        "modalImage": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx120377-ayZPoxiWt4Li.jpg",
        "banner_image": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/120377-c15oLS8CA31s.jpg",
        "category": "Top, Action, Sci-Fi, Cyberpunk, Drama",
        "description": "A street kid in futuristic Night City loses everything and becomes an edgerunner mercenary in a high-tech corporate dystopia.",
        "insights": "Studio Trigger's adrenaline-fueled visual triumph featuring blistering color direction and a tragic, unforgettable romance.",
        "studio": "Studio Trigger",
        "episodes": "10 eps",
        "status": "Finished",
        "trailer_url": "https://www.youtube-nocookie.com/embed/JtqIas3bYhg",
        "trailer_youtube_id": "JtqIas3bYhg",
        "source": "manual"
    },
    {
        "id": 13,
        "mal_id": 30,
        "title": "Neon Genesis Evangelion",
        "year": "1995",
        "rating": "8.35",
        "mal_score": 8.35,
        "image": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx30-AI1zr74Dh4ye.jpg",
        "modalImage": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/30-gEMoHHIqxDgN.jpg",
        "banner_image": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/30-gEMoHHIqxDgN.jpg",
        "category": "Top, Sci-Fi, Mecha, Psychological, Drama, Classic",
        "description": "Shinji Ikari pilots giant biomechanical Evangelion Unit-01 against mysterious Angels in a post-apocalyptic Tokyo-3.",
        "insights": "Hideaki Anno's legendary psychological masterpiece that deconstructed the mecha genre and redefined television anime.",
        "studio": "Gainax",
        "episodes": "26 eps",
        "status": "Finished",
        "trailer_url": "https://www.youtube-nocookie.com/embed/13nSISwxrY4",
        "trailer_youtube_id": "13nSISwxrY4",
        "source": "manual"
    },
    {
        "id": 14,
        "mal_id": 50265,
        "title": "Spy x Family",
        "year": "2022",
        "rating": "8.52",
        "mal_score": 8.52,
        "image": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx140960-Kb6R5nYQfjmP.jpg",
        "modalImage": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/140960-Z7xSvkRxHKfj.jpg",
        "banner_image": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/140960-Z7xSvkRxHKfj.jpg",
        "category": "Popular, Comedy, Action, Slice of Life, Shonen",
        "description": "Master spy Twilight creates a faux family with telepathic daughter Anya and assassin wife Yor, unaware of each other's secrets.",
        "insights": "Charm, warmth, and witty undercover espionage wrapped in hilarious family dynamics that captivated global audiences.",
        "studio": "Wit Studio / CloverWorks",
        "episodes": "25 eps",
        "status": "Finished",
        "trailer_url": "https://www.youtube-nocookie.com/embed/ofXigq9aIpo",
        "trailer_youtube_id": "ofXigq9aIpo",
        "source": "manual"
    },
    {
        "id": 15,
        "mal_id": 22319,
        "title": "Tokyo Ghoul",
        "year": "2014",
        "rating": "7.80",
        "mal_score": 7.8,
        "image": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/medium/b20605-k665mVkSug8D.jpg",
        "modalImage": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/20605-RCJ7M71zLmrh.jpg",
        "banner_image": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/20605-RCJ7M71zLmrh.jpg",
        "category": "Popular, Action, Horror, Supernatural, Psychological",
        "description": "Ken Kaneki survives a vicious ghoul attack and undergoes surgery that turns him into the first half-human, half-ghoul hybrid.",
        "insights": "A dark, intense exploration of humanity, monstrosity, and survival anchored by the unforgettable anthem 'Unravel'.",
        "studio": "Studio Pierrot",
        "episodes": "12 eps",
        "status": "Finished",
        "trailer_url": "https://www.youtube-nocookie.com/embed/7aMOurgDB-o",
        "trailer_youtube_id": "7aMOurgDB-o",
        "source": "manual"
    },
    {
        "id": 16,
        "mal_id": 1,
        "title": "Cowboy Bebop",
        "year": "1998",
        "rating": "8.75",
        "mal_score": 8.75,
        "image": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx1-GCsPm7waJ4kS.png",
        "modalImage": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/1-OquNCNB6srGe.jpg",
        "banner_image": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/1-OquNCNB6srGe.jpg",
        "category": "Top, Sci-Fi, Space Western, Action, Classic",
        "description": "Spike Spiegel and bounty hunter Jet Black drift across space aboard the Bebop, tackling high-stakes bounties while facing past demons.",
        "insights": "Shinichiro Watanabe's timeless jazz-infused neo-noir that set an immortal bar for style, choreography, and atmosphere.",
        "studio": "Sunrise",
        "episodes": "26 eps",
        "status": "Finished",
        "trailer_url": "https://www.youtube-nocookie.com/embed/EL-D9LrFJd4",
        "trailer_youtube_id": "EL-D9LrFJd4",
        "source": "manual"
    },
    {
        "id": 17,
        "mal_id": 30276,
        "title": "One Punch Man",
        "year": "2015",
        "rating": "8.50",
        "mal_score": 8.5,
        "image": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21087-B5DHjqZ3kW4b.jpg",
        "modalImage": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/21087-sHb9zUZFsHe1.jpg",
        "banner_image": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/21087-sHb9zUZFsHe1.jpg",
        "category": "Popular, Action, Comedy, Superhero, Parody",
        "description": "Saitama has trained so hard his hair fell out and he can defeat any adversary with a single punch, seeking a worthy opponent.",
        "insights": "Shingo Natsume and Madhouse created one of the greatest animation showcases in television history.",
        "studio": "Madhouse",
        "episodes": "12 eps",
        "status": "Finished",
        "trailer_url": "https://www.youtube-nocookie.com/embed/Poo5lqoWSGw",
        "trailer_youtube_id": "Poo5lqoWSGw",
        "source": "manual"
    },
    {
        "id": 18,
        "mal_id": 20583,
        "title": "Haikyuu!!",
        "year": "2014",
        "rating": "8.45",
        "mal_score": 8.45,
        "image": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20464-ooZUyBe4ptp9.png",
        "modalImage": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20464-ooZUyBe4ptp9.png",
        "banner_image": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/20464-PpYjO9cPN1gs.jpg",
        "category": "Popular, Top, Sports, School, Drama, Shonen",
        "description": "Determined short spiker Shoyo Hinata unites with genius rival setter Tobio Kageyama to propel Karasuno High back to Nationals.",
        "insights": "Heart-pounding sports drama celebrated for exceptional animation, intense rallies, and profound character growth.",
        "studio": "Production I.G",
        "episodes": "85 eps",
        "status": "Finished",
        "trailer_url": "https://www.youtube-nocookie.com/embed/JOGp2c7-cKc",
        "trailer_youtube_id": "JOGp2c7-cKc",
        "source": "manual"
    },
    {
        "id": 19,
        "mal_id": 11757,
        "title": "Sword Art Online",
        "year": "2012",
        "rating": "7.20",
        "mal_score": 7.2,
        "image": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx11757-SxYDUzdr9rh2.jpg",
        "modalImage": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/11757-TlEEV9weG4Ag.jpg",
        "banner_image": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/11757-TlEEV9weG4Ag.jpg",
        "category": "Popular, Action, Adventure, Fantasy, Romance, Sci-Fi",
        "description": "Players trapped in a deadly virtual reality MMORPG where game over means death in the real world fight through 100 castle floors.",
        "insights": "The global cultural phenomenon that propelled the virtual world and isekai subgenres into worldwide mainstream popularity.",
        "studio": "A-1 Pictures",
        "episodes": "25 eps",
        "status": "Finished",
        "trailer_url": "https://www.youtube-nocookie.com/embed/6ohYYtxfDCg",
        "trailer_youtube_id": "6ohYYtxfDCg",
        "source": "manual"
    },
    {
        "id": 20,
        "mal_id": 5114,
        "title": "Fullmetal Alchemist: Brotherhood",
        "year": "2009",
        "rating": "9.10",
        "mal_score": 9.1,
        "image": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx5114-nSWCgQlmOMtj.jpg",
        "modalImage": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/5114-q0V5URebphSG.jpg",
        "banner_image": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/5114-q0V5URebphSG.jpg",
        "category": "Action, Adventure, Drama, Fantasy, Shonen, Classic, Top",
        "description": "After a failed alchemical ritual costs Edward an arm and a leg and binds Alphonse's soul to a suit of armor, the Elric brothers seek the Philosopher's Stone.",
        "insights": "Consistently ranked as the #1 anime of all time on MyAnimeList, celebrated for flawless pacing and character development.",
        "studio": "Bones",
        "episodes": "64 eps",
        "status": "Finished",
        "trailer_url": "https://www.youtube-nocookie.com/embed/--IcmZkvL0Q",
        "trailer_youtube_id": "--IcmZkvL0Q",
        "source": "manual"
    }
]


def _migrate_anime_columns():
    """Ensure newly added columns exist in anime table using fast native SQL."""
    if not is_postgres():
        return
    try:
        with db.engine.begin() as conn:
            conn.execute(text("""
                ALTER TABLE anime ADD COLUMN IF NOT EXISTS mal_id INTEGER;
                ALTER TABLE anime ADD COLUMN IF NOT EXISTS mal_score FLOAT DEFAULT 0.0;
                ALTER TABLE anime ADD COLUMN IF NOT EXISTS banner_image TEXT DEFAULT '';
                ALTER TABLE anime ADD COLUMN IF NOT EXISTS trailer_url TEXT DEFAULT '';
                ALTER TABLE anime ADD COLUMN IF NOT EXISTS trailer_youtube_id VARCHAR(50) DEFAULT '';
                ALTER TABLE anime ADD COLUMN IF NOT EXISTS source VARCHAR(20) DEFAULT 'manual';
                ALTER TABLE anime ADD COLUMN IF NOT EXISTS fetched_at TIMESTAMP;
            """))
    except Exception as ex:
        print(f"Anime columns migration note: {ex}")


def _migrate_movie_columns():
    """Ensure newly added columns exist in movies table using fast native SQL."""
    if not is_postgres():
        return
    try:
        with db.engine.begin() as conn:
            conn.execute(text("""
                ALTER TABLE movies ADD COLUMN IF NOT EXISTS trailer_url TEXT DEFAULT '';
                ALTER TABLE movies ADD COLUMN IF NOT EXISTS trailer_youtube_id VARCHAR(50) DEFAULT '';
            """))
    except Exception as ex:
        print(f"Movie columns migration note: {ex}")


def _migrate_watchlist_constraints():
    """Migrate watchlist unique constraint to include media_type for movie/anime coexistence."""
    if not is_postgres():
        return
    try:
        with db.engine.begin() as conn:
            conn.execute(text("""
                ALTER TABLE watchlist DROP CONSTRAINT IF EXISTS uq_watchlist_user_anime;
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint WHERE conname = 'uq_watchlist_user_anime_type'
                    ) THEN
                        ALTER TABLE watchlist ADD CONSTRAINT uq_watchlist_user_anime_type UNIQUE (user_id, anime_id, media_type);
                    END IF;
                END $$;
            """))
    except Exception as ex:
        print(f"Watchlist constraints migration note: {ex}")


def init_db(app):
    """
    Initialize Flask-SQLAlchemy with connection pooling, create tables, and seed initial data.
    Uses fast initialization bypass if the database is already provisioned to prevent 25s+ cold boot lag.
    """
    uri = get_db_uri()
    app.config['SQLALCHEMY_DATABASE_URI'] = uri
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    if uri.startswith('sqlite'):
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_pre_ping': True
        }
    else:
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
        # Fast check: If tables and anime already exist, skip redundant 25s startup migrations
        is_initialized = False
        if not os.getenv('FORCE_MIGRATE'):
            try:
                with db.engine.connect() as conn:
                    is_initialized = conn.execute(text("SELECT 1 FROM anime LIMIT 1")).scalar() is not None
            except Exception:
                is_initialized = False

        if not is_initialized or os.getenv('FORCE_MIGRATE') == '1':
            for attempt in range(3):
                try:
                    db.create_all()
                    _migrate_anime_columns()
                    _migrate_movie_columns()
                    _migrate_watchlist_constraints()
                    _seed_demo_accounts()
                    break
                except Exception as e:
                    if attempt == 2:
                        raise
                    import time
                    time.sleep(1.5)

            # Seed default anime catalog if empty
            if Anime.query.count() == 0:
                print(f"Catalog is empty. Seeding initial {len(DEFAULT_ANIME)} anime titles into database...")
                for a in DEFAULT_ANIME:
                    existing = db.session.get(Anime, a['id'])
                    if not existing:
                        existing = Anime.query.filter(Anime.title.ilike(a['title'])).first()

                    if not existing:
                        anime = Anime(
                            id=a['id'],
                            mal_id=a.get('mal_id'),
                            title=a['title'],
                            year=a.get('year', ''),
                            rating=a.get('rating', ''),
                            mal_score=float(a.get('mal_score', 0) or 0),
                            image=a.get('image', ''),
                            modalImage=a.get('modalImage', a.get('image', '')),
                            banner_image=a.get('banner_image', a.get('modalImage', a.get('image', ''))),
                            category=a.get('category', ''),
                            description=a.get('description', ''),
                            insights=a.get('insights', ''),
                            episodes=a.get('episodes', ''),
                            status=a.get('status', 'Finished'),
                            studio=a.get('studio', ''),
                            japanese_title=a.get('japanese_title', ''),
                            main_characters=a.get('main_characters', ''),
                            trailer_url=a.get('trailer_url', ''),
                            trailer_youtube_id=a.get('trailer_youtube_id', ''),
                            source=a.get('source', 'manual')
                        )
                        db.session.add(anime)
                db.session.commit()

            # Seed default movies catalog if empty
            if Movie.query.count() == 0:
                print(f"Movie catalog is empty. Seeding initial {len(DEFAULT_MOVIES)} movies into database...")
                for m in DEFAULT_MOVIES:
                    existing = db.session.get(Movie, m['id'])
                    if not existing:
                        existing = Movie.query.filter(Movie.title.ilike(m['title'])).first()

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
                            main_characters=m.get('main_characters', ''),
                            trailer_url=m.get('trailer_url', ''),
                            trailer_youtube_id=m.get('trailer_youtube_id', '')
                        )
                        db.session.add(movie)
                db.session.commit()

            # Sync sequences in PostgreSQL if applicable
            if is_postgres():
                try:
                    with db.engine.begin() as conn:
                        conn.execute(text("SELECT setval(pg_get_serial_sequence('anime', 'id'), coalesce(max(id), 1)) FROM anime;"))
                        conn.execute(text("SELECT setval(pg_get_serial_sequence('movies', 'id'), coalesce(max(id), 1)) FROM movies;"))
                except Exception as seq_ex:
                    print(f"Sequence sync note: {seq_ex}")
