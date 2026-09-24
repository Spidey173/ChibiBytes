"""
SQLAlchemy models for ChibiBytes application.
Replaces raw SQL cursor operations with declarative, dialect-agnostic models.
"""

from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def utc_now():
    return datetime.now(timezone.utc)


class User(db.Model):
    """User account model for authentication, roles, and profile."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    role = db.Column(db.String(50), default='user')
    avatar_url = db.Column(db.Text, default='')
    bio = db.Column(db.String(255), default='')
    created_at = db.Column(db.DateTime, default=utc_now)

    # Cascade delete related entries when a user is deleted
    watchlist_items = db.relationship('Watchlist', backref='user', cascade='all, delete-orphan', lazy=True)
    reviews = db.relationship('Review', backref='user', cascade='all, delete-orphan', lazy=True)
    chat_messages = db.relationship('ChatMessage', backref='user', cascade='all, delete-orphan', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'avatar_url': self.avatar_url,
            'bio': self.bio,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else ''
        }


class Watchlist(db.Model):
    """User watchlist model with rich metadata and favorite status."""
    __tablename__ = 'watchlist'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    anime_id = db.Column(db.Integer, nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    year = db.Column(db.String(50), default='')
    rating = db.Column(db.String(50), default='')
    image = db.Column(db.Text, default='')
    category = db.Column(db.Text, default='')
    description = db.Column(db.Text, default='')
    episodes = db.Column(db.String(50), default='')
    media_type = db.Column(db.String(20), default='anime')
    is_favorite = db.Column(db.Boolean, default=False)
    added_at = db.Column(db.DateTime, default=utc_now)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'anime_id', name='uq_watchlist_user_anime'),
        db.Index('idx_watchlist_user_added', 'user_id', added_at.desc()),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'anime_id': self.anime_id,
            'title': self.title,
            'year': self.year,
            'rating': self.rating,
            'image': self.image,
            'category': self.category,
            'description': self.description,
            'episodes': self.episodes,
            'media_type': self.media_type,
            'is_favorite': self.is_favorite,
            'added_at': self.added_at.isoformat() if self.added_at else ''
        }


class Anime(db.Model):
    """Anime catalog model."""
    __tablename__ = 'anime'

    id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    title = db.Column(db.String(255), nullable=False, index=True)
    year = db.Column(db.String(50), default='')
    rating = db.Column(db.String(50), default='')
    image = db.Column(db.Text, nullable=False)
    modalImage = db.Column('modalimage', db.Text, nullable=False)
    category = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=False)
    insights = db.Column(db.Text, nullable=False)
    episodes = db.Column(db.String(50), default='')
    status = db.Column(db.String(50), default='Finished')
    studio = db.Column(db.String(100), default='')
    japanese_title = db.Column(db.String(255), default='')
    main_characters = db.Column(db.Text, default='')

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'year': self.year,
            'rating': self.rating,
            'image': self.image,
            'modalImage': self.modalImage,
            'category': self.category,
            'description': self.description,
            'insights': self.insights,
            'episodes': self.episodes,
            'status': self.status,
            'studio': self.studio,
            'japanese_title': self.japanese_title,
            'main_characters': self.main_characters
        }


class Movie(db.Model):
    """Movie catalog model."""
    __tablename__ = 'movies'

    id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    title = db.Column(db.String(255), nullable=False, index=True)
    year = db.Column(db.String(50), default='')
    rating = db.Column(db.String(50), default='')
    image = db.Column(db.Text, nullable=False)
    modalImage = db.Column('modalimage', db.Text, nullable=False)
    category = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=False)
    insights = db.Column(db.Text, nullable=False)
    director = db.Column(db.String(255), nullable=False, default='')
    duration = db.Column(db.String(50), nullable=False, default='')
    japanese_title = db.Column(db.String(255), default='')
    main_characters = db.Column(db.Text, default='')

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'year': self.year,
            'rating': self.rating,
            'image': self.image,
            'modalImage': self.modalImage,
            'category': self.category,
            'description': self.description,
            'insights': self.insights,
            'director': self.director,
            'duration': self.duration,
            'japanese_title': self.japanese_title,
            'main_characters': self.main_characters
        }


class Review(db.Model):
    """User reviews model for anime and movies."""
    __tablename__ = 'reviews'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    anime_id = db.Column(db.Integer, nullable=False, index=True)
    media_type = db.Column(db.String(20), default='anime')
    score = db.Column(db.Numeric(3, 1), nullable=False)
    comment = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=utc_now)

    def to_dict(self):
        return {
            'id': self.id,
            'score': float(self.score),
            'comment': self.comment or '',
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else '',
            'username': self.user.username if self.user else '',
            'avatar_url': self.user.avatar_url if self.user else ''
        }


class ChatMessage(db.Model):
    """Persistent chat message history model."""
    __tablename__ = 'chat_messages'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now)

    def to_dict(self):
        return {
            'id': self.id,
            'role': self.role,
            'content': self.content,
            'created_at': self.created_at.isoformat() if self.created_at else ''
        }
