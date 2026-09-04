import unittest
import os
import sqlite3
from app import app
from database import get_db

class ChibiBytesTestCase(unittest.TestCase):
    def setUp(self):
        """Set up a temporary test database and clean client context before each test."""
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        
        # Ensure tests run against local SQLite database
        import database
        self.original_db_url = os.environ.pop('DATABASE_URL', None)
        self.original_db_const = database.DATABASE
        self.db_path = 'test_ChibiBytes_users.db'
        database.DATABASE = self.db_path
        
        # Clean any leftover test DB
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except PermissionError:
                pass
            
        self.app = app.test_client()
        
        # Initialize test database tables
        with app.app_context():
            from database import init_db
            init_db(app)

    def tearDown(self):
        """Remove test database after test finishes."""
        import database
        database.DATABASE = self.original_db_const
        if self.original_db_url:
            os.environ['DATABASE_URL'] = self.original_db_url
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except PermissionError:
                pass

    def test_database_seeding(self):
        """Test if the database tables are auto-seeded with titles from template htmls on initialization."""
        with app.app_context():
            db = get_db()
            cursor = db.cursor()
            cursor.execute("SELECT COUNT(*) FROM anime")
            anime_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM movies")
            movies_count = cursor.fetchone()[0]
            
            self.assertTrue(anime_count > 0, "Anime table was not seeded.")
            self.assertTrue(movies_count > 0, "Movies table was not seeded.")

    def test_user_signup_and_login(self):
        """Test user registration flow and login validation."""
        # 1. Signup a test user
        response = self.app.post('/signup', data=dict(
            username='testotaku',
            email='test@chibibytes.com',
            password='Password123',
            confirm_password='Password123'
        ), follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        
        # Verify user is in SQLite database
        with app.app_context():
            db = get_db()
            cursor = db.cursor()
            cursor.execute("SELECT username FROM users WHERE username = 'testotaku'")
            user = cursor.fetchone()
            self.assertIsNotNone(user, "User was not created in the database.")
            
        # 2. Log in with correct credentials
        response = self.app.post('/login', data=dict(
            username='testotaku',
            password='Password123'
        ), follow_redirects=True)
        self.assertIn(b'testotaku', response.data) # Username should appear in internal pages
        
        # 3. Log in with wrong credentials
        response = self.app.post('/login', data=dict(
            username='testotaku',
            password='WrongPassword'
        ), follow_redirects=False)
        self.assertIn(b'Invalid username or password', response.data)

    def test_chatbot_database_search(self):
        """Test that chatbot successfully fetches and formats matches from the SQLite database."""
        # Simulate log in session so user has access to chat
        with self.app.session_transaction() as sess:
            sess['user_id'] = 999
            sess['username'] = 'testotaku'
            
        # Query about Naruto
        response = self.app.post('/api/chat', json=dict(
            message="Tell me about Naruto"
        ))
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertIn("Naruto", data['response'])
        self.assertIn("https://", data['response']) # Ensure rich card/image URL is included

if __name__ == '__main__':
    unittest.main()
