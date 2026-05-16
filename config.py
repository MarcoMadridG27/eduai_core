import os
from dotenv import load_dotenv
from google import genai

# Cargar variables de entorno desde el archivo .env
load_dotenv()

# ========================
# Configuración de Gemini
# ========================
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=GOOGLE_API_KEY) if GOOGLE_API_KEY else genai.Client()

# ========================
# Configuración general
# ========================
DB_NAME = "lesson_memory.db"
TXT_URL = "https://raw.githubusercontent.com/angelmc-12/myfirstrepo/master/curriculo_texto.txt"
