import json
import asyncio
import logging
import uuid

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from services import generate_lesson_sync, generate_lesson_stream, generate_lesson_result

from database import init_db, get_session, save_session_input
from knowledge import init_knowledge_base
from utils import normalize_session_input

app = FastAPI(
    title="Generador de Sesiones Educativas",
    description="API para generar sesiones con Structured Outputs y WebSockets",
    version="2.0.0"
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Startup tasks: initialize DB and knowledge base off the import path
@app.on_event("startup")
async def startup():
    logger.info("Startup: inicializando base de datos y base de conocimientos")
    await asyncio.to_thread(init_db)
    await asyncio.to_thread(init_knowledge_base)

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
    return {"status": "ok", "message": "Generador de sesiones educativas corriendo (v2) 🚀"}


async def read_request_payload(request: Request):
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            return await request.json()
        except Exception:
            return {}

    try:
        form = await request.form()
    except Exception:
        return {}

    payload = {}
    for key, value in form.multi_items():
        if key in payload:
            current_value = payload[key]
            if not isinstance(current_value, list):
                payload[key] = [current_value]
            payload[key].append(value)
        else:
            payload[key] = value
    return payload


def _build_session_filename(session_id: str):
    safe_session_id = "".join(char for char in session_id if char.isalnum() or char in ("-", "_"))
    return f"sesion_{safe_session_id or 'session'}.json"


@app.post("/api/sessions")
async def create_session(request: Request):
    """Crea una sesión y, si viene información inicial, la guarda."""
    payload = await read_request_payload(request)
    session_id = payload.get("session_id") or str(uuid.uuid4())
    raw_data = payload.get("data", payload)
    normalized_data = normalize_session_input(raw_data or {})
    save_session_input(session_id, normalized_data, source=payload.get("source", "frontend"), status="draft")

    session = get_session(session_id) or {
        "session_id": session_id,
        "source": payload.get("source", "frontend"),
        "status": "draft",
        "input_data": normalized_data,
        "generated_data": None,
    }

    return JSONResponse(session)


@app.get("/api/sessions/{session_id}")
async def get_session_detail(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    return JSONResponse(session)


@app.post("/api/sessions/{session_id}/form")
async def receive_session_form(session_id: str, request: Request):
    """Recibe el formulario de la sesión desde frontend o form-data."""
    payload = await read_request_payload(request)
    raw_data = payload.get("data", payload)
    normalized_data = normalize_session_input(raw_data)
    save_session_input(session_id, normalized_data, source=payload.get("source", "frontend"), status="draft")

    session = get_session(session_id)
    return JSONResponse(session)


@app.post("/api/sessions/{session_id}/generate")
async def generate_session(session_id: str, request: Request):
    """Genera la sesión usando los datos guardados o los enviados en esta petición."""
    payload = await read_request_payload(request)
    known_form_keys = {
        "tema", "titulo", "docente", "fecha", "grado", "seccion", "competenciasSeleccionadas",
        "competencias", "capacidades", "ciclo", "contexto", "duracion", "horasClase",
        "enfoqueTransversal", "enfoque_transversal", "competenciaTransversal", "competencia_transversal",
        "materialesDisponibles", "materiales"
    }
    raw_data = None
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        raw_data = payload.get("data")
    elif isinstance(payload, dict) and any(key in known_form_keys for key in payload.keys()):
        raw_data = payload

    session = get_session(session_id)
    if raw_data:
        normalized_data = normalize_session_input(raw_data)
        save_session_input(session_id, normalized_data, source=payload.get("source", "frontend"), status="generating")
    elif session and session.get("input_data"):
        normalized_data = session["input_data"]
    else:
        raise HTTPException(status_code=400, detail="La sesión no tiene datos de formulario para generar")

    result = await generate_lesson_result(session_id, normalized_data)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return JSONResponse({"session_id": session_id, "status": "completed", "data": result})


@app.get("/api/sessions/{session_id}/download")
async def download_session(session_id: str):
    """Descarga la sesión generada como archivo JSON."""
    session = get_session(session_id)
    if not session or not session.get("generated_data"):
        raise HTTPException(status_code=404, detail="La sesión todavía no tiene una versión generada")

    content = json.dumps(session["generated_data"], ensure_ascii=False, indent=2)
    headers = {"Content-Disposition": f'attachment; filename="{_build_session_filename(session_id)}"'}
    return Response(content=content, media_type="application/json; charset=utf-8", headers=headers)

# Webhook tradicional para integraciones simples (ej. WhatsApp)
@app.post("/webhook")
async def webhook(request: Request):
    """
    Endpoint clásico síncrono. Ideal para bots de WhatsApp o peticiones cURL simples.
    Espera a que todo el proceso termine y devuelve el JSON final.
    """
    form = await request.form()
    user_message = form.get("Body", "")
    session_id = form.get("From", "default_user")

    if not user_message:
        return JSONResponse({"error": "Por favor envía: Tema, Competencia, Grado y Contexto"})

    lesson_plan = generate_lesson_sync(session_id, user_message)
    return JSONResponse(lesson_plan)


# Nuevo Endpoint de Stream (Server-Sent Events) para el Frontend
@app.get("/api/generate-stream")
async def generate_stream(session_id: str, message: str):
    """
    Endpoint SSE (Server-Sent Events) ideal para frontends web (React, Vue, HTML puro).
    Uso en JS: const eventSource = new EventSource(`/api/generate-stream?session_id=id&message=texto`);
    """
    async def event_generator():
        async for chunk in generate_lesson_stream(session_id, message):
            # El formato SSE requiere "data: " seguido de los datos y dos saltos de línea
            yield f"data: {chunk}\n\n"
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")


# Alternativa: WebSocket para el Frontend
@app.websocket("/ws/generate")
async def websocket_generate(websocket: WebSocket):
    """
    Endpoint WebSocket para una conexión bidireccional en tiempo real.
    Permite enviar mensajes y recibir el progreso de forma interactiva.
    """
    await websocket.accept()
    try:
        # El cliente envía un JSON con session_id y message
        data = await websocket.receive_text()
        request_data = json.loads(data)
        session_id = request_data.get("session_id", "ws_user")
        message = request_data.get("message", "")
        
        async for chunk in generate_lesson_stream(session_id, message):
            await websocket.send_text(chunk)
            
        await websocket.close()
    except WebSocketDisconnect:
        logger.info("Cliente WebSocket desconectado")
    except Exception as e:
        await websocket.send_text(json.dumps({"status": "error", "message": str(e)}))
        await websocket.close()
