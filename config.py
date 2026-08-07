import os

from dotenv import load_dotenv
from google import genai

# Cargar variables de entorno desde el archivo .env
load_dotenv()

# ──── Google Gemini ────
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=GOOGLE_API_KEY) if GOOGLE_API_KEY else None

# ──── Base de datos SQLite ────
DB_NAME = os.getenv("DB_NAME", "lesson_memory.db")

# ──── Voyage AI (Embeddings) ────
VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY")

# ──── Qdrant (Vector DB) ────
# En producción (EC2): http://qdrant:6333 (nombre de servicio Docker)
# En local:           http://localhost:6333
# Sin QDRANT_URL:     modo en memoria (solo desarrollo)
QDRANT_URL = os.getenv("QDRANT_URL", "").strip()
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "").strip() or None

# ──── Langfuse (Observabilidad) ────
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
