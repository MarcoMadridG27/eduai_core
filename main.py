from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from services import generate_lesson_sync, generate_lesson_stream
import json

app = FastAPI(
    title="Generador de Sesiones Educativas",
    description="API para generar sesiones con Structured Outputs y WebSockets",
    version="2.0.0"
)

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"status": "ok", "message": "Generador de sesiones educativas corriendo (v2) 🚀"}

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
        print("Cliente WebSocket desconectado")
    except Exception as e:
        await websocket.send_text(json.dumps({"status": "error", "message": str(e)}))
        await websocket.close()
