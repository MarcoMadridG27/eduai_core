import os

from dotenv import load_dotenv
from google import genai

# Cargar variables de entorno desde el archivo .env
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
# Si no hay API key, dejar `client` como None para que el resto del código
# pueda detectar la ausencia de credenciales y fallar de manera controlada.
client = genai.Client(api_key=GOOGLE_API_KEY) if GOOGLE_API_KEY else None

DB_NAME = os.getenv("DB_NAME", "lesson_memory.db")
TXT_URL = os.getenv("TXT_URL", "https://raw.githubusercontent.com/angelmc-12/myfirstrepo/master/curriculo_texto.txt")
