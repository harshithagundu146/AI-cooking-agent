import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'ai-cooking-agent-secret-key-2026')
    MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')
    DB_NAME = 'ai_cooking_agent'
    JWT_EXPIRATION_HOURS = 24
