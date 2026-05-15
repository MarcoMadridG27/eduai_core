from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import chromadb
from google import genai
from google.genai import types
from google.api_core import retry
import os
import re
import json
import requests
import time 

# ========================
# Configuración de Gemini
# ========================
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=GOOGLE_API_KEY)

# ========================
# Base de datos SQLite
# ========================
DB_NAME = "lesson_memory.db"
conn = sqlite3.connect(DB_NAME, check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS lesson_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    role TEXT,
    content TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()

def save_message(session_id, role, content):
    cursor.execute(
        "INSERT INTO lesson_history (session_id, role, content) VALUES (?, ?, ?)", 
        (session_id, role, content)
    )
    conn.commit()

def get_recent_history(session_id, n_turns=3):
    cursor.execute("""
        SELECT role, content FROM lesson_history 
        WHERE session_id=? 
        ORDER BY id DESC LIMIT ?
    """, (session_id, n_turns*2))
    rows = cursor.fetchall()
    return list(reversed(rows))

# ========================
# ChromaDB con currículo escolar
# ========================
class GeminiEmbeddingFunction(chromadb.EmbeddingFunction):
    document_mode = True
    @retry.Retry(predicate=lambda e: isinstance(e, genai.errors.APIError) and e.code in {429,503})
    def __call__(self, input):
        task = "retrieval_document" if self.document_mode else "retrieval_query"
        response = client.models.embed_content(
            model="models/text-embedding-004",
            contents=input,
            config=types.EmbedContentConfig(task_type=task),
        )
        return [e.values for e in response.embeddings]

embed_fn = GeminiEmbeddingFunction()
chroma_client = chromadb.Client()
knowledge_db = chroma_client.get_or_create_collection(
    name="curriculo_secundaria", embedding_function=embed_fn
)

# Documentos curriculares (ejemplo resumido)
# documents = [
#     "Competencia: Resuelve problemas de cantidad. Capacidades: Traduce cantidades a expresiones numéricas...",
#     "Competencia: Resuelve problemas de regularidad, equivalencia y cambios...",
#     "Competencia: Resuelve problemas de forma, movimiento y localización...",
#     "Competencia: Resuelve problemas de gestión de datos e incertidumbre...",
#     "Procesos didácticos de Matemática: Comprensión del problema, Búsqueda y ejecución de estrategias, Socializa sus representaciones, Reflexión y formalización, Planteamiento de otros problemas."
# ]
# knowledge_db.add(documents=documents, ids=[str(i) for i in range(len(documents))])

TXT_URL = "https://raw.githubusercontent.com/angelmc-12/myfirstrepo/master/curriculo_texto.txt"

response = requests.get(TXT_URL, timeout=30)
response.raise_for_status()

text = response.text
chunks = re.split(r'\n{2,}', text)  # separa por párrafos
docs = [chunk.strip() for chunk in chunks if len(chunk.strip()) > 50]

MAX_BATCH = 100
ids = [f"frag_{i}" for i in range(len(docs))]

for i in range(0, len(docs), MAX_BATCH):
    batch_docs = docs[i:i+MAX_BATCH]
    batch_ids = ids[i:i+MAX_BATCH]
    try:
        knowledge_db.add(documents=batch_docs, ids=batch_ids)
        print(f"✅ Lote {i//MAX_BATCH + 1} cargado ({len(batch_docs)} fragmentos)")
        time.sleep(1)  # opcional, evita saturar la API
    except Exception as e:
        print(f"⚠️ Error en el lote {i//MAX_BATCH + 1}: {e}")

# ========================
# Procesar mensaje docente
# ========================
def parse_teacher_message(message: str):
    """Extrae los campos enviados por el frontend como texto plano."""
    titulo = re.search(r"Título:\s*(.*)", message)
    docente = re.search(r"Docente:\s*(.*)", message)
    fecha = re.search(r"Fecha:\s*(.*)", message)
    grado = re.search(r"Grado:\s*(.*)", message)
    seccion = re.search(r"Sección:\s*(.*)", message)
    competencias = re.search(r"Competencias:\s*(.*)", message)
    capacidades = re.search(r"Capacidades:\s*(.*)", message)
    ciclo = re.search(r"Ciclo:\s*(.*)", message)
    contexto = re.search(r"Contexto:\s*(.*)", message)
    duracion = re.search(r"Duración:\s*(.*)", message)
    enfoque_transversal = re.search(r"Enfoque Transversal:\s*(.*)", message)
    competencia_transversal = re.search(r"Competencia Transversal:\s*(.*)", message)
    materiales = re.search(r"Materiales:\s*(.*)", message)

    return {
        "titulo": titulo.group(1).strip() if titulo else "",
        "docente": docente.group(1).strip() if docente else "",
        "fecha": fecha.group(1).strip() if fecha else "",
        "grado": grado.group(1).strip() if grado else "",
        "seccion": seccion.group(1).strip() if seccion else "",
        "competencias": competencias.group(1).strip() if competencias else "",
        "capacidades": capacidades.group(1).strip() if capacidades else "",
        "ciclo": ciclo.group(1).strip() if ciclo else "",
        "contexto": contexto.group(1).strip() if contexto else "",
        "duracion": duracion.group(1).strip() if duracion else "2 horas",
        "enfoque_transversal": enfoque_transversal.group(1).strip() if enfoque_transversal else "",
        "competencia_transversal": competencia_transversal.group(1).strip() if competencia_transversal else "",
        "materiales": materiales.group(1).strip() if materiales else "",
    }

# ========================
# Construcción del prompt
# ========================


def build_prompt(inputs, retrieved_docs):
    """
    Construye el prompt que se enviará al modelo Gemini.
    Toma en cuenta todos los campos del docente y el contenido curricular relevante.
    """

    prompt = (
        "Actúa como un **asistente pedagógico experto en Matemática del Currículo Nacional Peruano**. "
        "Tu tarea es ayudar a un docente de educación secundaria a **preparar su sesión de aprendizaje** de forma completa y contextualizada, "
        "considerando las competencias, capacidades y enfoques pedagógicos oficiales del MINEDU Perú.\n\n"

        "Genera el entregable en formato JSON **válido**, siguiendo exactamente esta estructura:\n\n"
        "{\n"
        '  "datosGenerales": {\n'
        '    "titulo": "",\n'
        '    "docente": "",\n'
        '    "fecha": "",\n'
        '    "grado": "",\n'
        '    "seccion": ""\n'
        '  },\n'
        '  "tema": "",\n'
        '  "ciclo": "",\n'
        '  "contexto": "",\n'
        '  "horasClase": 2,\n'
        '  "competenciasSeleccionadas": [],\n'
        '  "capacidades": [],\n'
        '  "materialesDisponibles": "",\n'
        '  "enfoqueTransversal": "",\n'
        '  "competenciaTransversal": "",\n'
        '  "competenciaDescripcion": "",\n'
        '  "criteriosEvaluacion": "",\n'
        '  "evidenciasAprendizaje": "",\n'
        '  "propositoSesion": "",\n'
        '  "secuenciaMetodologica": {\n'
        '    "inicio": "",\n'
        '    "desarrollo": "",\n'
        '    "cierre": ""\n'
        '  },\n'
        '  "distribucionHoras": "",\n'
        '  "procesosDidacticos": [],\n'
        '  "actividadesContextualizadas": [],\n'
        '  "materialesDidacticosSugeridos": [],\n'
        '  "recursosAdicionales": {\n'
        '    "fichasDeTrabajo": [],\n'
        '    "problemasYEjercicios": [],\n'
        '    "juegoDidactico": {},\n'
        '    "actividadDeActivacion": [],\n'
        '    "evaluacionFormativa": {},\n'
        '    "comunicadoParaPadres": "",\n'
        '    "actividadesDiferenciadas": {\n'
        '      "refuerzo": [],\n'
        '      "consolidacion": [],\n'
        '      "profundizacion": []\n'
        '    }\n'
        '  }\n'
        "}\n\n"
        "Requisitos de la respuesta:\n"
        "- Usa lenguaje claro y profesional dirigido a docentes peruanos.\n"
        "- **RESPETA ESTRICTAMENTE la duración especificada** (1 hora pedagógica = 45 minutos).\n"
        "- Las actividades deben ser **coherentes con el contexto sociocultural y materiales disponibles**.\n"
        "- Adecúa la dificultad y las estrategias pedagógicas al **grado o ciclo indicado**.\n"
        "- **CONTEXTUALIZACIÓN OBLIGATORIA**: TODAS las actividades deben relacionarse con el contexto sociocultural indicado:\n"
        "  * Rural/Agrícola: cultivos, animales, terrenos, cosechas\n"
        "  * Pesquero: capturas, redes, embarcaciones, mareas\n"
        "  * Comercial: ventas, precios, descuentos, ganancias\n"
        "  * Minero: minerales, excavaciones, volúmenes\n"
        "  * Turístico: rutas, mapas, visitantes, costos\n"
        "  * Urbano: transporte, edificios, tecnología, servicios\n"
        "- La distribución del tiempo debe ser realista (Inicio: 15-20%, Desarrollo: 60-70%, Cierre: 10-15%).\n"
        "- **Secuencia Metodológica Detallada**:\n"
        "  * INICIO: motivación contextualizada, problematización, saberes previos, propósito (mínimo 3 párrafos)\n"
        "  * DESARROLLO: situación problemática + 5 procesos didácticos de Matemática + trabajo variado (mínimo 5 párrafos)\n"
        "  * CIERRE: metacognición, transferencia, evaluación formativa (mínimo 2 párrafos)\n"
        "- **Procesos Didácticos de Matemática** (siempre en este orden):\n"
        "  1. Familiarización con el problema\n"
        "  2. Búsqueda y ejecución de estrategias\n"
        "  3. Socialización de representaciones\n"
        "  4. Reflexión y formalización\n"
        "  5. Planteamiento de otros problemas\n"
        "- **Criterios de Evaluación**: Deben ser observables, medibles y específicos para esta sesión.\n"
        "- **Evidencias de Aprendizaje**: Productos concretos que generarán los estudiantes.\n"
        "- **Propósito de la Sesión**: Claro, alcanzable y redactado en términos de lo que aprenderán.\n"
        "- **Integrar Enfoques Transversales**: Incluir naturalmente el enfoque transversal en las actividades.\n"
        "- **Integrar Competencia Transversal**: Si es TICs, sugerir tecnología; si es Aprendizaje Autónomo, incluir autoevaluación.\n"
        "- Actividades progresivas en dificultad, factibles con los materiales disponibles.\n"
        "- No devuelvas texto adicional fuera del JSON.\n\n"
        
        "**RECURSOS ADICIONALES A INCLUIR:**\n"
        "1. **fichasDeTrabajo**: Genera 2-3 fichas de trabajo con ejercicios progresivos (básico, intermedio, avanzado) relacionados al tema. "
        "Cada ficha debe tener título, instrucciones claras y ejercicios específicos.\n\n"
        
        "2. **problemasYEjercicios**: Crea 5-8 problemas o ejercicios variados sobre el tema, incluyendo:\n"
        "   - Problemas básicos de comprensión\n"
        "   - Ejercicios de aplicación intermedia\n"
        "   - Desafíos avanzados para estudiantes que necesitan mayor reto\n"
        "   - Incluye las respuestas correctas y criterios de evaluación\n\n"
        
        "3. **juegoDidactico**: Diseña un juego educativo de 15-20 minutos que:\n"
        "   - Use materiales simples disponibles en el aula (papel, plumones, dados, etc.)\n"
        "   - Tenga instrucciones paso a paso\n"
        "   - Incluya 3 niveles de dificultad\n"
        "   - Fomente el trabajo colaborativo\n"
        "   - Termine con reflexión grupal\n\n"
        
        "4. **actividadDeActivacion**: Proporciona 2-3 actividades de activación de saberes previos de 3-5 minutos para iniciar la clase. "
        "Deben ser dinámicas y ayudar a conectar con conocimientos anteriores.\n\n"
        
        "5. **evaluacionFormativa**: Crea una evaluación formativa de 20-30 minutos que incluya:\n"
        "   - 5-6 preguntas variadas (básicas, intermedias y avanzadas)\n"
        "   - Respuestas correctas\n"
        "   - Criterios de evaluación claros\n"
        "   - Alineada con las competencias del CNEB\n\n"
        
        "6. **comunicadoParaPadres**: Elabora un breve mensaje (200-300 palabras) para padres de familia que:\n"
        "   - Explique qué están aprendiendo sus hijos\n"
        "   - Proporcione 2-3 estrategias sencillas para apoyar en casa\n"
        "   - Use lenguaje cálido y motivador\n"
        "   - Sea apropiado para enviar por WhatsApp (incluye emojis)\n\n"
        
        "7. **actividadesDiferenciadas**: Proporciona rutas de trabajo diferenciadas:\n"
        "   - **refuerzo**: 2-3 actividades para estudiantes que necesitan consolidar conceptos básicos\n"
        "   - **consolidacion**: 2-3 actividades para estudiantes en proceso de aprendizaje\n"
        "   - **profundizacion**: 2-3 actividades desafiantes para estudiantes que ya dominan el tema\n\n"
    )

    # --- Información proporcionada por el docente ---
    prompt += (
        "**DATOS GENERALES:**\n"
        f"- Título: {inputs['titulo']}\n"
        f"- Docente: {inputs['docente']}\n"
        f"- Fecha: {inputs['fecha']}\n"
        f"- Grado: {inputs['grado']}\n"
        f"- Sección: {inputs['seccion']}\n\n"
        
        "**COMPETENCIAS Y CAPACIDADES:**\n"
        f"- Competencias: {inputs['competencias']}\n"
        f"- Capacidades: {inputs['capacidades']}\n\n"
        
        "**CONTEXTO:**\n"
        f"- Ciclo: {inputs['ciclo']}\n"
        f"- Contexto sociocultural: {inputs['contexto']}\n"
        f"- Duración: {inputs['duracion']} (1 hora = 45 minutos)\n\n"
        
        "**ENFOQUES:**\n"
        f"- Enfoque Transversal: {inputs['enfoque_transversal']}\n"
        f"- Competencia Transversal: {inputs['competencia_transversal']}\n\n"
        
        "**RECURSOS:**\n"
        f"- Materiales disponibles: {inputs['materiales']}\n\n"
        
        "**IMPORTANTE - RESPETA LA DURACIÓN ESPECIFICADA:**\n"
        f"El docente ha indicado que la sesión debe durar exactamente: {inputs['duracion']}\n"
        "- Cada hora pedagógica = 45 minutos.\n"
        "- Ajusta TODAS las actividades, tiempos y secuencias metodológicas a esta duración específica.\n"
        "- El campo 'horasClase' en el JSON debe reflejar exactamente el número de horas indicado.\n"
        "- La 'distribucionHoras' debe desglosar minutos específicos: Inicio (15-20%), Desarrollo (60-70%), Cierre (10-15%).\n"
        "- Si la duración es corta (1 hora = 45 min), prioriza actividades esenciales.\n"
        "- Si la duración es larga (2-3 horas = 90-135 min), incluye más práctica y profundización.\n"
        "- NO propongas actividades que excedan el tiempo disponible.\n\n"
        
        f"**CONTEXTUALIZACIÓN AL ENTORNO {inputs['contexto'].upper()}:**\n"
        "- TODAS las situaciones problemáticas, ejemplos y actividades DEBEN estar relacionadas con este contexto.\n"
        "- Usa vocabulario, elementos y situaciones propias de este entorno sociocultural.\n"
        "- Las actividades deben ser significativas y pertinentes para estudiantes de este contexto.\n\n"
    )

    # --- Información curricular recuperada ---
    if retrieved_docs:
        prompt += "Fragmentos relevantes del Currículo Nacional:\n"
        for i, doc in enumerate(retrieved_docs, 1):
            prompt += f"{i}. {doc.strip()}\n"
        prompt += "\n"

    prompt += (
        "Ahora, genera el JSON completo con la sesión de aprendizaje contextualizada y lista para ser aplicada en el aula."
    )

    return prompt


def clean_model_output(raw: str):
    """Intenta limpiar outputs de modelos que vienen como texto con code-fences
    o texto extra y devuelve (obj, cleaned_string).
    - Si puede parsear JSON devuelve el objeto y la cadena usada.
    - Si no puede, devuelve (None, cleaned_candidate).
    """
    if not isinstance(raw, str):
        return None, None

    s = raw.strip()

    # Remover code fences como ```json ... ``` o ``` ... ```
    m = re.match(r"^```(?:json)?\s*([\s\S]*)\s*```$", s, re.IGNORECASE)
    if m:
        s = m.group(1).strip()

    # A veces vienen con comillas extra o texto antes/ despues; buscar primer '{' y último '}'
    first = s.find('{')
    last = s.rfind('}')
    if first != -1 and last != -1 and last > first:
        candidate = s[first:last+1]
    else:
        candidate = s

    # Intentar cargar JSON directamente
    try:
        obj = json.loads(candidate)
        return obj, candidate
    except Exception:
        # Intentar otras limpiezas comunes
        candidate2 = candidate.strip().strip('"')
        candidate2 = candidate2.replace('\n', '\\n')
        try:
            obj = json.loads(candidate2)
            return obj, candidate2
        except Exception:
            # No se pudo parsear
            return None, candidate

def generate_lesson(session_id, message):
    """
    Genera una sesión de aprendizaje considerando todos los campos del mensaje docente.
    Usa el tema, competencia, grado/ciclo, contexto, duración y materiales
    para recuperar fragmentos relevantes del currículo y construir un prompt completo.
    """

    # --- Extraer los datos del mensaje ---
    inputs = parse_teacher_message(message)

    # --- Construir texto de búsqueda (usando todos los campos disponibles) ---
    query_parts = [
        inputs.get("titulo", ""),
        inputs.get("competencias", ""),
        inputs.get("capacidades", ""),
        inputs.get("grado", ""),
        inputs.get("ciclo", ""),
        inputs.get("contexto", ""),
        inputs.get("materiales", "")
    ]
    query_text = " ".join(part for part in query_parts if part).strip()

    # --- Buscar fragmentos relevantes en ChromaDB ---
    embed_fn.document_mode = False
    result = knowledge_db.query(query_texts=[query_text], n_results=5)
    retrieved_docs = result["documents"][0] if result["documents"] else []

    # --- Construir el prompt completo para Gemini ---
    prompt = build_prompt(inputs, retrieved_docs)

    # --- Llamar al modelo de Gemini ---
    response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=prompt
    )

    raw_output = response.text
    # --- Limpiar y validar el JSON devuelto ---
    parsed, cleaned_candidate = clean_model_output(raw_output)
    if parsed is not None:
        lesson_json = parsed
    else:
        # Intento fallback: cargar el texto tal cual
        try:
            lesson_json = json.loads(raw_output)
        except Exception:
            # No se pudo parsear; devolver estructura de error incluyendo candidato limpio
            lesson_json = {
                "error": "El modelo no devolvió un JSON válido",
                "raw": raw_output,
                "cleaned_candidate": cleaned_candidate
            }

    # --- Guardar historial de conversación ---
    # Guardar entradas y salidas para debugging: inputs, raw model output y resultado final
    save_message(session_id, "user", json.dumps(inputs, ensure_ascii=False))
    save_message(session_id, "bot_raw", raw_output)
    save_message(session_id, "bot", json.dumps(lesson_json, ensure_ascii=False))

    return lesson_json

# ========================
# API FastAPI (WhatsApp / Frontend)
# ========================
app = FastAPI()

# --- CORS Middleware ---
origins = ["*"]  # Ajusta en producción
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"status": "ok", "message": "Generador de sesiones educativas corriendo 🚀"}

@app.post("/webhook")
async def webhook(request: Request):
    form = await request.form()
    user_message = form.get("Body", "")
    session_id = form.get("From", "default_user")

    if not user_message:
        return JSONResponse({"error": "Por favor envía: Tema, Competencia, Grado y Contexto 📚"})

    lesson_plan = generate_lesson(session_id, user_message)
    return JSONResponse(lesson_plan)
