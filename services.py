import asyncio
import json
import logging
import time

from google.genai import types

from config import (
    LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, client
)
from database import (save_generated_session, save_message, save_session_input,
                      update_session_status)
from prompts import build_core_prompt, build_resources_prompt
from rag.retriever import search as rag_search
from schemas import CoreLessonPlan, RecursosAdicionales
from utils import normalize_session_input

logger = logging.getLogger(__name__)


def _get_langfuse():
    """Retorna cliente Langfuse si está configurado, si no None."""
    if LANGFUSE_SECRET_KEY and LANGFUSE_PUBLIC_KEY:
        try:
            from langfuse import Langfuse
            return Langfuse(
                secret_key=LANGFUSE_SECRET_KEY,
                public_key=LANGFUSE_PUBLIC_KEY,
                host=LANGFUSE_HOST,
            )
        except Exception as e:
            logger.warning("Langfuse no disponible: %s", e)
    return None

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

    # 2. Buscar en Qdrant con filtros por nivel, grado y área
    yield json.dumps({"status": "progress", "step": "Buscando contexto en el Currículo Nacional..."})
    rag_start = time.time()

    # Construir query textual para embedding
    query_parts = [
        inputs.get("tema", ""),
        ", ".join(inputs.get("competenciasSeleccionadas", [])),
        ", ".join(inputs.get("capacidades", [])),
        inputs.get("grado", ""),
        inputs.get("area", ""),
        inputs.get("contexto", "")
    ]
    query_text = " ".join(part for part in query_parts if part).strip()

    # Extraer filtros de metadata desde los inputs del docente
    rag_filters = {}
    nivel_raw = str(inputs.get("nivel") or inputs.get("ciclo") or "").lower()
    if "inicial" in nivel_raw:
        rag_filters["nivel"] = "inicial"
    elif "primaria" in nivel_raw:
        rag_filters["nivel"] = "primaria"
    elif "secundaria" in nivel_raw:
        rag_filters["nivel"] = "secundaria"

    area_raw = str(inputs.get("area") or "").lower().strip()
    if area_raw:
        rag_filters["area"] = area_raw

    retrieved_docs = await asyncio.to_thread(
        rag_search, query_text, rag_filters, 5
    )
    rag_latency_ms = int((time.time() - rag_start) * 1000)
    logger.info(
        "RAG: %d chunks recuperados en %dms (filtros=%s)",
        len(retrieved_docs), rag_latency_ms, rag_filters
    )

    if not client:
        update_session_status(session_id, "error")
        yield json.dumps({"status": "error", "message": "API Key de Gemini no configurada correctamente"})
        return

    idioma_req = inputs.get("idioma", "español")
    # Determinar nivel y área para el system instruction
    nivel_label = rag_filters.get("nivel", "Educación Básica Regular").capitalize()
    area_label = (inputs.get("area") or "todas las áreas").capitalize()
    system_instruction = (
        f"Actúa como un asistente pedagógico experto en {area_label} de nivel {nivel_label} del Currículo Nacional Peruano del MINEDU (CNEB). "
        f"IMPORTANTE: El usuario ha solicitado redactar esta sesión completamente en '{idioma_req}'. "
        f"Por lo tanto, DEBES redactar todo el contenido textual de los valores del JSON únicamente en el idioma '{idioma_req}', "
        "de manera gramaticalmente correcta, natural y con alta calidad pedagógica. "
        "Las claves del JSON de salida deben permanecer tal cual en español."
    )

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
    resources_prompt = build_resources_prompt(core_plan_json, inputs.get("idioma", "español"))

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

    # Normalizar y asegurar que 'actividades_previas' exista como lista de strings
    try:
        # Determinar fallbacks localizados
        lang_key = str(inputs.get("idioma", "español")).lower()
        if "ingl" in lang_key or "en" == lang_key:
            fallback_ap = [
                "Prepare available materials",
                "Recall prior concepts",
                "Organize the group into teams"
            ]
            fallback_des = [
                "Solves the problematic situation using relevant strategies.",
                "Explains and justifies the procedure followed with mathematical language.",
                "Verifies their results and corrects errors if necessary."
            ]
            fallback_act = "Participates actively, listens with respect, and cooperates with their group."
        elif "quechua" in lang_key or "qu" == lang_key:
            fallback_ap = [
                "Tupachiy yachana imakuna",
                "Yuyariy ñawpa yachaykunata",
                "T'aqaman yachaqkunata allichay"
            ]
            fallback_des = [
                "Allichan yachay sasachakuyta allin yachaykunawan.",
                "Sut'inchan churanpas ruraykunata yupay yachay rimasqawan.",
                "Qhawarin rurasqan allin kasqanta hinallataq pantasqakunatapas pantachin."
            ]
            fallback_act = "Allin yuyaywan ruran, hukkunata uyarin hinallataq t'aqanwan llank'an."
        elif "aymara" in lang_key or "ay" == lang_key:
            fallback_ap = [
                "Yatichawi yänaka wakichaña",
                "Nayra yatichäwita amtaña",
                "Tama yatirinaka wakichaña"
            ]
            fallback_des = [
                "Jan walt'awi walt'ayi yatxataña walt'awinakampi.",
                "Qhanañchi lurañanakapata yatxatata arukiptawi.",
                "Uñji aski lurata ukatxa pantasqanaka chiqpachañani."
            ]
            fallback_act = "Ch'amampi chikañasi, yäpampi ist'i ukatxa tamapampi irnaqi."
        else:
            fallback_ap = [
                "Preparar materiales disponibles",
                "Recordar conceptos previos",
                "Organizar al grupo en equipos"
            ]
            fallback_des = [
                "Resuelve la situación problemática usando estrategias pertinentes.",
                "Explica y justifica el procedimiento seguido con lenguaje matemático.",
                "Verifica sus resultados y corrige errores si es necesario."
            ]
            fallback_act = "Participa activamente, escucha con respeto y colabora con su grupo."

        ap = final_lesson.get("actividades_previas")
        if not ap:
            # Intentar inferir desde secuenciaMetodologica.inicio
            sm = final_lesson.get("secuenciaMetodologica") or {}
            inicio = None
            if isinstance(sm, dict):
                inicio = sm.get("inicio")
            if inicio and isinstance(inicio, str) and inicio.strip():
                import re
                items = re.split(r'\n|\.|\s*\d+\.\s*', inicio)
                cleaned = [s.strip() for s in items if s and s.strip()]
                final_lesson["actividades_previas"] = cleaned[:3] if cleaned else fallback_ap
            else:
                final_lesson["actividades_previas"] = fallback_ap
        else:
            # Si vino como string, convertir a lista
            if isinstance(ap, str):
                import re
                items = re.split(r'\n|\s*\d+\.\s*', ap)
                final_lesson["actividades_previas"] = [s.strip() for s in items if s and s.strip()]
            elif isinstance(ap, list):
                # limpieza básica
                final_lesson["actividades_previas"] = [str(x).strip() for x in ap if str(x).strip()]
            else:
                final_lesson["actividades_previas"] = [str(ap)]

        desempenos = final_lesson.get("desempenos")
        if not desempenos:
            competencia_desc = final_lesson.get("competenciaDescripcion") or ""
            if isinstance(competencia_desc, str) and competencia_desc.strip():
                import re
                items = re.split(r'\n|\s*\d+\.\s*|\.\s+', competencia_desc)
                cleaned = [s.strip() for s in items if s and s.strip()]
                final_lesson["desempenos"] = cleaned[:4] if cleaned else [competencia_desc.strip()]
            else:
                final_lesson["desempenos"] = fallback_des

        if not final_lesson.get("actitudes_observables"):
            competencia_transversal = inputs.get("competenciaTransversal") or inputs.get("competencia_transversal") or ""
            enfoque_transversal = inputs.get("enfoqueTransversal") or inputs.get("enfoque_transversal") or ""
            final_lesson["actitudes_observables"] = competencia_transversal or enfoque_transversal or fallback_act
    except Exception:
        # Como último recurso, asegurar un fallback mínimo
        final_lesson.setdefault("actividades_previas", fallback_ap)
        final_lesson.setdefault("desempenos", fallback_des)
        final_lesson.setdefault("actitudes_observables", fallback_act)

    # Guardar en DB
    def save_logs():
        save_message(session_id, "user", json.dumps(
            inputs, ensure_ascii=False))
        save_message(session_id, "bot", json.dumps(
            final_lesson, ensure_ascii=False))
        save_generated_session(session_id, final_lesson)

    await asyncio.to_thread(save_logs)
    update_session_status(session_id, "completed")

    # Registrar traza en Langfuse (si está configurado)
    try:
        lf = _get_langfuse()
        if lf:
            trace = lf.trace(name="generate_lesson", session_id=session_id)
            trace.span(
                name="rag_retrieval",
                metadata={"filters": rag_filters, "chunks_retrieved": len(retrieved_docs)},
                input=query_text,
                output=str(retrieved_docs[:2]),
            )
            trace.generation(
                name="core_plan",
                model="gemini-3.1-flash-lite",
                input=core_prompt[:500],
                output=core_plan_json[:500],
            )
            lf.flush()
    except Exception as lf_err:
        logger.debug("Langfuse trace error (no crítico): %s", lf_err)

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
