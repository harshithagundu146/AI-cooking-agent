from flask import Blueprint, request, jsonify
import bcrypt, jwt, datetime, uuid
from config import Config
from db import get_db, get_memory_store

auth_bp = Blueprint('auth', __name__)

def _hash_pw(pw):
    return bcrypt.hashpw(pw.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def _check_pw(pw, hashed):
    return bcrypt.checkpw(pw.encode('utf-8'), hashed.encode('utf-8'))

def _make_token(user_id, username):
    payload = {
        'user_id': user_id,
        'username': username,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=Config.JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, Config.SECRET_KEY, algorithm='HS256')

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    if not username or not email or not password:
        return jsonify({"error": "All fields are required"}), 400

    db = get_db()
    if db is not None:
        if db.users.find_one({"$or": [{"username": username}, {"email": email}]}):
            return jsonify({"error": "User already exists"}), 409
        user_id = str(uuid.uuid4())
        db.users.insert_one({"user_id": user_id, "username": username, "email": email, "password": _hash_pw(password), "is_new": True})
    else:
        store = get_memory_store()
        if username in store["users"]:
            return jsonify({"error": "User already exists"}), 409
        user_id = str(uuid.uuid4())
        store["users"][username] = {"user_id": user_id, "username": username, "email": email, "password": _hash_pw(password), "is_new": True}

    token = _make_token(user_id, username)
    return jsonify({"token": token, "username": username, "user_id": user_id, "is_new": True}), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')

    db = get_db()
    if db is not None:
        user = db.users.find_one({"username": username})
    else:
        store = get_memory_store()
        user = store["users"].get(username)

    if not user or not _check_pw(password, user["password"]):
        return jsonify({"error": "Invalid credentials"}), 401

    token = _make_token(user["user_id"], username)
    is_new = user.get("is_new", False)
    return jsonify({"token": token, "username": username, "user_id": user["user_id"], "is_new": is_new}), 200
