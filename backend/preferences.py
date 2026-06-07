from flask import Blueprint, request, jsonify
from db import get_db, get_memory_store

preferences_bp = Blueprint('preferences', __name__)

@preferences_bp.route('/save', methods=['POST'])
def save_preferences():
    data = request.get_json()
    user_id = data.get('user_id')
    prefs = {
        "user_id": user_id,
        "food_category": data.get("food_category"),
        "spice_preference": data.get("spice_preference"),
        "cuisine_preference": data.get("cuisine_preference"),
        "health_preference": data.get("health_preference"),
        "allergies": data.get("allergies", []),
        "taste_preference": data.get("taste_preference")
    }
    db = get_db()
    if db is not None:
        db.preferences.update_one({"user_id": user_id}, {"$set": prefs}, upsert=True)
        db.users.update_one({"user_id": user_id}, {"$set": {"is_new": False}})
    else:
        store = get_memory_store()
        store["preferences"][user_id] = prefs
        for u in store["users"].values():
            if u["user_id"] == user_id:
                u["is_new"] = False
    return jsonify({"message": "Preferences saved"}), 200

@preferences_bp.route('/get/<user_id>', methods=['GET'])
def get_preferences(user_id):
    db = get_db()
    if db is not None:
        prefs = db.preferences.find_one({"user_id": user_id}, {"_id": 0})
    else:
        store = get_memory_store()
        prefs = store["preferences"].get(user_id)
    if not prefs:
        return jsonify({"error": "No preferences found"}), 404
    return jsonify(prefs), 200
