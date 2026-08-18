import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
GEN_MODEL   = os.getenv("GEN_MODEL", "llama3.1:8b")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
CHROMA_DIR  = Path(os.getenv("CHROMA_DIR", "./data/chroma"))
RAW_DIR     = Path("./data/raw")
COLLECTION  = "personal_email"