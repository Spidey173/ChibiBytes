import unittest
import os
import json
from app import app
from database import get_db, init_db, db
from models import User, Watchlist, Anime, Movie, Review, ChatMessage

class ChibiBytesTestCase(unittest.TestCase):
    def setUp(self):
        """Set up a temporary test database and clean client context before each test."""
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        
        # Ensure tests run against isolated local SQLite database
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
        
        # Initialize test database tables and seed
        with app.app_context():
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
            anime_count = Anime.query.count()
            movies_count = Movie.query.count()
            
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
            user = User.query.filter_by(username='testotaku').first()
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

    def test_user_signup_validation(self):
        """Test password mismatch and duplicate user rejection."""
        # Password mismatch
        response = self.app.post('/signup', data=dict(
            username='mismatch_user',
            email='mismatch@chibibytes.com',
            password='Password123',
            confirm_password='DifferentPassword'
        ), follow_redirects=True)
        self.assertIn(b'Passwords do not match', response.data)

        # Create user
        self.app.post('/signup', data=dict(
            username='duplicate_check',
            email='dup@chibibytes.com',
            password='Password123',
            confirm_password='Password123'
        ), follow_redirects=True)

        # Attempt duplicate registration with same username
        response = self.app.post('/signup', data=dict(
            username='duplicate_check',
            email='another@chibibytes.com',
            password='Password123',
            confirm_password='Password123'
        ), follow_redirects=True)
        self.assertIn(b'Username or email already exists', response.data)

    def test_watchlist_operations(self):
        """Test adding, querying, toggling favorite, and deleting watchlist items."""
        # Create user & set session
        with app.app_context():
            user = User(username='watchlist_fan', email='wf@chibibytes.com', password='hash', role='user')
            db.session.add(user)
            db.session.commit()
            user_id = user.id

        with self.app.session_transaction() as sess:
            sess['user_id'] = user_id
            sess['username'] = 'watchlist_fan'
            sess['role'] = 'user'

        # 1. Add item to watchlist (auto-enriches category and description from Naruto)
        add_res = self.app.post('/add_to_watchlist', json=dict(
            anime_id=4,
            title='Naruto'
        ))
        self.assertEqual(add_res.status_code, 200)
        self.assertTrue(add_res.get_json()['success'])

        # 2. Verify watchlist has item with enriched data
        with app.app_context():
            item = Watchlist.query.filter_by(user_id=user_id, anime_id=4).first()
            self.assertIsNotNone(item)
            self.assertEqual(item.title, 'Naruto')
            self.assertIn('Ninja', item.category)
            item_id = item.id

        # 3. Toggle favorite
        fav_res = self.app.post(f'/toggle_favorite/{item_id}')
        self.assertEqual(fav_res.status_code, 200)
        self.assertTrue(fav_res.get_json()['is_favorite'])

        # 4. Remove item
        del_res = self.app.delete(f'/remove_from_watchlist/{item_id}')
        self.assertEqual(del_res.status_code, 200)
        self.assertTrue(del_res.get_json()['success'])

        with app.app_context():
            self.assertIsNone(Watchlist.query.filter_by(id=item_id).first())

    def test_admin_access_control(self):
        """Verify role-based access control for administrative endpoints."""
        # Unauthenticated request to /admin redirects to login
        res = self.app.get('/admin', follow_redirects=False)
        self.assertEqual(res.status_code, 302)

        # Standard user request to /api/admin/stats is forbidden (403)
        with self.app.session_transaction() as sess:
            sess['user_id'] = 1001
            sess['username'] = 'regular_user'
            sess['role'] = 'user'

        res = self.app.get('/api/admin/stats')
        self.assertEqual(res.status_code, 403)

        # Admin user request succeeds
        with self.app.session_transaction() as sess:
            sess['user_id'] = 1002
            sess['username'] = 'boss_admin'
            sess['role'] = 'admin'

        res = self.app.get('/api/admin/stats')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('total_users', data['stats'])

    def test_user_cascade_delete(self):
        """Verify that deleting a user removes associated watchlist and chat records via SQLAlchemy cascade."""
        with app.app_context():
            user = User(username='cascade_user', email='cascade@chibibytes.com', password='hash', role='user')
            db.session.add(user)
            db.session.commit()
            uid = user.id

            wl = Watchlist(user_id=uid, anime_id=1, title='One Piece')
            chat = ChatMessage(user_id=uid, role='user', content='Hello Chibi')
            db.session.add_all([wl, chat])
            db.session.commit()

            # Act as admin to delete user
            admin_user = User(username='superadmin', email='sa@chibibytes.com', password='hash', role='admin')
            db.session.add(admin_user)
            db.session.commit()
            admin_id = admin_user.id

        with self.app.session_transaction() as sess:
            sess['user_id'] = admin_id
            sess['username'] = 'superadmin'
            sess['role'] = 'admin'

        del_res = self.app.delete(f'/api/admin/users/{uid}')
        self.assertEqual(del_res.status_code, 200)

        with app.app_context():
            self.assertIsNone(db.session.get(User, uid))
            self.assertEqual(Watchlist.query.filter_by(user_id=uid).count(), 0)
            self.assertEqual(ChatMessage.query.filter_by(user_id=uid).count(), 0)

    def test_community_reviews_api(self):
        """Test submitting and retrieving community reviews."""
        with app.app_context():
            reviewer = User(username='critic_otaku', email='critic@chibibytes.com', password='hash', role='user')
            db.session.add(reviewer)
            db.session.commit()
            r_id = reviewer.id

        with self.app.session_transaction() as sess:
            sess['user_id'] = r_id
            sess['username'] = 'critic_otaku'
            sess['role'] = 'user'

        # Submit review
        post_res = self.app.post('/api/reviews', json=dict(
            anime_id=1,
            score=9.5,
            comment='Masterpiece of worldbuilding!'
        ))
        self.assertEqual(post_res.status_code, 200)
        self.assertTrue(post_res.get_json()['success'])

        # Retrieve reviews
        get_res = self.app.get('/api/reviews?anime_id=1')
        self.assertEqual(get_res.status_code, 200)
        reviews = get_res.get_json()
        self.assertTrue(len(reviews) >= 1)
        self.assertEqual(reviews[0]['username'], 'critic_otaku')

    def test_chatbot_database_search(self):
        """Test that chatbot successfully fetches and formats matches from the SQLite database."""
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
