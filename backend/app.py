from flask import Flask, request, jsonify
from flask_cors import CORS
from config import Config
from db import get_db, init_db
from auth import auth_bp
from recipes import recipes_bp
from chatbot import chatbot_bp
from preferences import preferences_bp

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)
app.config.from_object(Config)

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(recipes_bp, url_prefix='/api/recipes')
app.register_blueprint(chatbot_bp, url_prefix='/api/chatbot')
app.register_blueprint(preferences_bp, url_prefix='/api/preferences')

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/api/health')
def health():
    return jsonify({"status": "ok"})

import os

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
