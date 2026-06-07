from pymongo import MongoClient
from config import Config
import json, os

_client = None
_db = None

def get_db():
    global _client, _db
    if _db is None:
        try:
            _client = MongoClient(Config.MONGO_URI, serverSelectionTimeoutMS=3000)
            _client.server_info()
            _db = _client[Config.DB_NAME]
        except Exception:
            _db = None
    return _db

def init_db():
    db = get_db()
    if db is None:
        print("WARNING: MongoDB not available. Using in-memory fallback.")
        return
    if db.recipes.count_documents({}) == 0:
        seed_file = os.path.join(os.path.dirname(__file__), 'seed_recipes.json')
        if os.path.exists(seed_file):
            with open(seed_file, 'r') as f:
                recipes = json.load(f)
            db.recipes.insert_many(recipes)
            print(f"Seeded {len(recipes)} recipes.")

# In-memory fallback storage
_memory_store = {"users": {}, "preferences": {}, "recipes": [], "chat_history": {}, "favorites": {}}

def get_memory_store():
    return _memory_store
