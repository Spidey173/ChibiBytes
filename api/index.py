import os
import sys

# Ensure parent directory is in Python module search path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

# Vercel serverless function entrypoint
app = app
