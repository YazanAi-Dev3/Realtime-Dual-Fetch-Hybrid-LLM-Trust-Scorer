import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/api/chat")
OLLAMA_MODEL_NAME = os.getenv("OLLAMA_MODEL_NAME", "gemma3:4b")
SERVER_PORT = int(os.getenv("SERVER_PORT", 8000))