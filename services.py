import asyncio
import json

from google.genai import types

from config import client
from database import (save_generated_session, save_message, save_session_input,
                      update_session_status)
from knowledge import embed_fn, knowledge_db
from prompts import build_core_prompt, build_resources_prompt
from schemas import CoreLessonPlan, RecursosAdicionales
from utils import normalize_session_input

# ========================
# Lógica de Negocio (Chaining & Streaming)
# ========================


async def generate_lesson_stream(session_id: str, message: str):
    """
    Generador asíncrono que emite el progreso de la generación paso a paso,
    usando Prompt Chaining y Structured Outputs.
    """
    # 1. Parsear y persistir datos de entrada
    yield json.dumps({"status": "progress", "step": "Analizando la solicitud del docente..."})
    inputs = normalize_session_input(message)
    save_session_input(session_id, inputs)
    update_session_status(session_id, "generating")
    await asyncio.sleep(0.5)

    # 2. Buscar en Vector DB
    yield json.dumps({"status": "progress", "step": "Buscando contexto en el Currículo Nacional..."})
    query_parts = [
        inputs.get("tema", ""),
        ", ".join(inputs.get("competenciasSeleccionadas", [])),
        ", ".join(inputs.get("capacidades", [])),
        inputs.get("grado", ""),
        inputs.get("contexto", "")
    ]
    query_text = " ".join(part for part in query_parts if part).strip()

    def query_db():
        embed_fn.document_mode = False
        return knowledge_db.query(query_texts=[query_text], n_results=5)

    result = await asyncio.to_thread(query_db)
    retrieved_docs = result["documents"][0] if result["documents"] else []

    if not client:
        update_session_status(session_id, "error")
        yield json.dumps({"status": "error", "message": "API Key de Gemini no configurada correctamente"})
        return

    system_instruction = "Actúa como un asistente pedagógico experto en Matemática del Currículo Nacional Peruano del MINEDU."

    # 3. Fase 1: Core Plan
    yield json.dumps({"status": "progress", "step": "Estructurando la secuencia metodológica de la sesión..."})
    core_prompt = build_core_prompt(inputs, retrieved_docs)

    def generate_core():
        return client.models.generate_content(
            model="gemini-3.1-flash-lite",  # O gemini-1.5-flash
            contents=core_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=CoreLessonPlan,
                system_instruction=system_instruction,
                temperature=0.7
            )
        )

    try:
        response_core = await asyncio.to_thread(generate_core)
        core_plan_json = response_core.text
    except Exception as e:
        update_session_status(session_id, "error")
        yield json.dumps({"status": "error", "message": f"Error en Fase 1: {str(e)}"})
        return

    # 4. Fase 2: Recursos
    yield json.dumps({"status": "progress", "step": "Generando fichas de trabajo, juegos y evaluaciones..."})
    resources_prompt = build_resources_prompt(core_plan_json)

    def generate_resources():
        return client.models.generate_content(
            model="gemini-3.1-flash-lite",  # O gemini-1.5-flash
            contents=resources_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=RecursosAdicionales,
                system_instruction=system_instruction,
                temperature=0.7
            )
        )

    try:
        response_resources = await asyncio.to_thread(generate_resources)
        resources_json = response_resources.text
    except Exception as e:
        update_session_status(session_id, "error")
        yield json.dumps({"status": "error", "message": f"Error en Fase 2: {str(e)}"})
        return

    # 5. Consolidar JSON final
    yield json.dumps({"status": "progress", "step": "Consolidando el documento final..."})
    try:
        final_lesson = json.loads(core_plan_json)
        final_lesson["recursosAdicionales"] = json.loads(resources_json)
    except Exception as e:
        update_session_status(session_id, "error")
        yield json.dumps({"status": "error", "message": f"Error parseando JSON final: {str(e)}"})
        return

    # Guardar en DB
    def save_logs():
        save_message(session_id, "user", json.dumps(
            inputs, ensure_ascii=False))
        save_message(session_id, "bot", json.dumps(
            final_lesson, ensure_ascii=False))
        save_generated_session(session_id, final_lesson)

    await asyncio.to_thread(save_logs)
    update_session_status(session_id, "completed")

    # 6. Emitir completado
    yield json.dumps({"status": "completed", "data": final_lesson})


async def generate_lesson_result(session_id: str, message):
    """Consume el stream y devuelve solo el resultado final o el error."""
    result = {}
    async for chunk in generate_lesson_stream(session_id, message):
        data = json.loads(chunk)
        if data["status"] == "completed":
            result = data["data"]
        elif data["status"] == "error":
            result = {"error": data["message"]}
    return result
