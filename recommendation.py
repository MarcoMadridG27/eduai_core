"""
Módulo de Recomendación Curricular (Copiloto Pedagógico RAG Dinámico con Gemini AI + Qdrant) para EduAI.
Evalúa cualquier tema de forma 100% dinámica utilizando Gemini LLM y la base vectorial Qdrant del CNEB.
"""

import json
import logging
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from google import genai
from google.genai import types
from config import GOOGLE_API_KEY, client as genai_client
from rag.retriever import search

logger = logging.getLogger(__name__)


class RecommendRequest(BaseModel):
    nivel: str
    grado: Optional[str] = ""
    area_seleccionada: Optional[str] = ""
    competencias_seleccionadas: Optional[List[str]] = []
    tema: str


class SugerenciaArea(BaseModel):
    area: str
    competencia: str
    capacidades: List[str] = []
    enfoque_explicacion: str


class RecommendResponse(BaseModel):
    coincide: bool
    es_multiarea: bool
    mensaje_evaluacion: str
    recomendaciones: List[SugerenciaArea] = []


PROMPT_EVALUACION_RAG = """
Eres un especialista curricular experto del Ministerio de Educación del Perú (MINEDU / CNEB).
Evalúa de forma analítica y rigurosa si el tema ingresado por el docente se desarrolla curricularmente en el área seleccionada, o si su pertinencia pedagógica principal corresponde a otra área del Currículo Nacional (CNEB).

Nivel educativo: {nivel}
Área seleccionada por el docente: {area_seleccionada}
Tema de la sesión: "{tema}"

Contexto relevante extraído del CNEB (Qdrant Vector DB):
{contexto_rag}

Instrucciones:
1. Si el tema "{tema}" pertenece, se aborda o es afín al área "{area_seleccionada}", responde en JSON con "coincide": true.
2. Si el tema "{tema}" NO pertenece al área "{area_seleccionada}" (por ejemplo "circuito electrónico" en Comunicación, "sistema nervioso" en Educación Física, "fotosíntesis" en Comunicación, "revolución francesa" en Matemática), responde con "coincide": false, identificando el área adecuada del CNEB, su competencia oficial, capacidades y una explicación pedagógica clara.
3. Responde ÚNICAMENTE con un objeto JSON válido con la siguiente estructura exacta:

{{
  "coincide": true | false,
  "es_multiarea": false,
  "mensaje_evaluacion": "Mensaje pedagógico claro orientando al docente",
  "recomendaciones": [
    {{
      "area": "Nombre del Área Sugerida",
      "competencia": "Nombre exacto de la competencia CNEB",
      "capacidades": ["Capacidad 1", "Capacidad 2"],
      "enfoque_explicacion": "Explicación breve de por qué este tema pertenece a esta área."
    }}
  ]
}}
"""


def obtener_recomendacion_curricular(req: RecommendRequest) -> Dict[str, Any]:
    """
    Evalúa dinámicamente cualquier tema usando Qdrant RAG + Gemini LLM.
    """
    logger.info("Copiloto RAG evaluando tema '%s' para el área '%s' (%s)", req.tema, req.area_seleccionada, req.nivel)

    # 1. Recuperar contexto semántico de Qdrant (1,217 chunks del CNEB)
    contexto_rag = ""
    try:
        chunks = search(query=f"Área curricular competencias para el tema {req.tema}", filters={"nivel": req.nivel}, top_k=3)
        textos_chunks = [c.get("text", "") for c in chunks if c.get("text")]
        if textos_chunks:
            contexto_rag = "\n---\n".join(textos_chunks[:2])
    except Exception as e:
        logger.warning("Aviso Qdrant retriever: %s", str(e))

    # 2. Evaluación Dinámica con Gemini AI (LLM Principal)
    active_client = genai_client or (genai.Client(api_key=GOOGLE_API_KEY) if GOOGLE_API_KEY else None)
    if active_client:
        try:
            prompt = PROMPT_EVALUACION_RAG.format(
                nivel=req.nivel,
                area_seleccionada=req.area_seleccionada,
                tema=req.tema,
                contexto_rag=contexto_rag or "Sin contexto vectorial adicional."
            )

            # Usar gemini-3.1-flash-lite con cuotas y velocidad optimizadas
            response = active_client.models.generate_content(
                model="gemini-3.1-flash-lite",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2
                )
            )

            if response and response.text:
                parsed = json.loads(response.text)
                if "coincide" in parsed and "mensaje_evaluacion" in parsed:
                    return parsed
        except Exception as e:
            logger.error("Error en Gemini LLM recommendation RAG: %s", str(e))

    # Fallback seguro en caso extremo de falla de red/API key
    return {
        "coincide": True,
        "es_multiarea": False,
        "mensaje_evaluacion": f"El tema '{req.tema}' fue registrado para el área {req.area_seleccionada}.",
        "recomendaciones": []
    }
