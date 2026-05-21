import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Flask
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///database.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB upload limit
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")

    # OpenRouter API (LLM)
    OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
    # Using Mistral as default (free tier friendly)
    LLM_MODEL = os.environ.get("LLM_MODEL", "mistralai/mistral-7b-instruct:free")

    # Adzuna Job API
    ADZUNA_APP_ID = os.environ.get("ADZUNA_APP_ID", "")
    ADZUNA_APP_KEY = os.environ.get("ADZUNA_APP_KEY", "")
    ADZUNA_BASE_URL = "https://api.adzuna.com/v1/api/jobs"
    ADZUNA_COUNTRY = os.environ.get("ADZUNA_COUNTRY", "gb")  # gb, us, au, etc.