import os
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("LLM_API_KEY") or os.getenv("OPENROUTER_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME") or os.getenv("LLM_MODEL")
LLM_BASE_URL = os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL")
LLM_PROVIDER = os.getenv("LLM_PROVIDER") or "openrouter"
WAKE_WORD = os.getenv("WAKE_WORD")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")