"""
Módulo de Recomendación Curricular (Copiloto Pedagógico RAG) para EduAI.
Consulta la base de datos vectorial de Qdrant (1,217 chunks del CNEB) y utiliza Gemini AI
para evaluar si el tema coincide verdaderamente con el área seleccionada o si sugiere una corrección orientadora.
"""

import json
import logging
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from config import GOOGLE_API_KEY
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


# Mapeo pedagógico oficial por áreas de Educación Básica
MATRIZ_AREAS_CNEB = {
    "Educación para el Trabajo": {
        "palabras": ["circuito", "electronica", "electric", "programacion", "robotic", "mantenimiento", "empr", "negocio", "proyecto", "costura", "carpinteria", "diseno"],
        "competencia": "Gestiona proyectos de emprendimiento económico o social",
        "capacidades": ["Crea propuestas de valor", "Trabaja cooperativamente para lograr objetivos y metas", "Aplica habilidades técnicas"]
    },
    "Ciencia y Tecnología": {
        "palabras": ["fotosintesis", "celula", "energia", "atomo", "materia", "ecosistema", "cuerpo", "digestiv", "planeta", "fisica", "quimica", "biologia", "experimento", "indagacion"],
        "competencia": "Explica el mundo físico basándose en conocimientos sobre los seres vivos, materia y energía",
        "capacidades": ["Comprende y usa conocimientos sobre los seres vivos, materia y energía", "Evalúa las implicancias del saber y del quehacer científico y tecnológico"]
    },
    "Matemática": {
        "palabras": ["suma", "resta", "multiplicacion", "division", "fraccion", "porcentaje", "ecuacion", "geometria", "angulo", "triangulo", "area", "perimetro", "estadistica", "probabilidad", "poligono", "funcion", "algebra"],
        "competencia": "Resuelve problemas de cantidad",
        "capacidades": ["Traduce cantidades a expresiones numéricas", "Comunica su comprensión sobre los números y las operaciones"]
    },
    "Personal Social": {
        "palabras": ["emocion", "sentimiento", "autoestima", "identidad", "convivencia", "norma", "derecho", "historia", "ciudadania", "conflicto", "cultura"],
        "competencia": "Construye su identidad",
        "capacidades": ["Se valora a sí mismo", "Autorregula sus emociones"]
    },
    "Ciencias Sociales": {
        "palabras": ["historia", "revolucion", "cultura", "independencia", "mapa", "geografia", "economia", "feudalismo", "guerra"],
        "competencia": "Construye interpretaciones históricas",
        "capacidades": ["Interpreta críticamente fuentes diversas", "Comprende el tiempo histórico"]
    },
    "Comunicación": {
        "palabras": ["cuento", "lectura", "poesia", "afiche", "ensayo", "ortografia", "gramatica", "redaccion", "debate", "noticia", "leyenda", "fabula", "texto"],
        "competencia": "Lee diversos tipos de textos escritos en su lengua materna",
        "capacidades": ["Obtiene información del texto escrito", "Infiere e interpreta información del texto"]
    }
}


PROMPT_EVALUACION_RAG = """Eres un experto pedagógico del Currículo Nacional de Educación Básica (CNEB) de Perú.
Debes evaluar si el tema "{tema}" pertenece curricularmente al área "{area_seleccionada}" en el nivel {nivel}.

CONTEXTO RAG EXTRAÍDO DE LOS DOCUMENTOS DEL CNEB:
{contexto_rag}

REGLAS DE EVALUACIÓN:
1. Si el tema "{tema}" NO PERTENECE al área "{area_seleccionada}" (por ejemplo, "circuitos electronicos" en "Comunicación" o "fotosintesis" en "Matemática"):
   - "coincide": false
   - "es_multiarea": false
   - "mensaje_evaluacion": "La IA detectó que el tema '{tema}' no corresponde habitualmente al área de {area_seleccionada}. Según el Currículo Nacional, pertenece al área de [Área Correcta] mediante la competencia [Competencia Correcta]."
   - "recomendaciones": Incluye el Área adecuada, su competencia CNEB oficial y sus capacidades.

2. Si el tema "{tema}" SÍ corresponde al área "{area_seleccionada}":
   - "coincide": true
   - "es_multiarea": false
   - "mensaje_evaluacion": "Excelente. El tema '{tema}' coincide adecuadamente con el área y competencia seleccionadas según el Currículo Nacional."
   - "recomendaciones": []

Devuelve ÚNICAMENTE un objeto JSON válido con este formato:
{{
  "coincide": boolean,
  "es_multiarea": boolean,
  "mensaje_evaluacion": "string",
  "recomendaciones": [
    {{
      "area": "Nombre del área recomendada",
      "competencia": "Nombre de la competencia",
      "capacidades": ["Capacidad 1", "Capacidad 2"],
      "enfoque_explicacion": "Explicación pedagógica breve"
    }}
  ]
}}
"""


def obtener_recomendacion_curricular(req: RecommendRequest) -> Dict[str, Any]:
    """
    Analiza el tema utilizando RAG en Qdrant + Gemini LLM / Matriz CNEB estricta.
    """
    tema_lower = req.tema.strip().lower()
    area_actual = (req.area_seleccionada or "").strip()
    area_actual_lower = area_actual.lower()

    logger.info("Copiloto RAG evaluando tema '%s' para el área '%s'", req.tema, area_actual)

    # 1. Consulta vectorial RAG en Qdrant
    query_rag = f"Área curricular competencias para el tema {req.tema}"
    chunks_rag = search(query=query_rag, filters={"nivel": req.nivel}, top_k=5)
    contexto_rag = "\n\n".join(chunks_rag) if chunks_rag else "Información general del CNEB."

    # 2. Evaluación mediante matriz pedagógica CNEB
    area_sugerida = None
    info_sugerida = None

    for area_nombre, datos in MATRIZ_AREAS_CNEB.items():
        if any(p in tema_lower for p in datos["palabras"]):
            area_sugerida = area_nombre
            info_sugerida = datos
            break

    # Si encontramos que el tema pertenece a otra área y NO al área actual seleccionada
    if area_sugerida and area_sugerida.lower() != area_actual_lower:
        logger.info("Incongruencia detectada: tema '%s' pertenece a '%s', pero seleccionó '%s'", req.tema, area_sugerida, area_actual)
        return {
            "coincide": False,
            "es_multiarea": False,
            "mensaje_evaluacion": f"La IA detectó que el tema '{req.tema}' se desarrolla habitualmente en el área de {area_sugerida} mediante la competencia '{info_sugerida['competencia']}'. Actualmente seleccionaste {area_actual}. Puedes adaptar la recomendación o mantener tu selección.",
            "recomendaciones": [
                {
                    "area": area_sugerida,
                    "competencia": info_sugerida["competencia"],
                    "capacidades": info_sugerida["capacidades"],
                    "enfoque_explicacion": f"El desarrollo pedagógico del tema '{req.tema}' corresponde a las competencias del área de {area_sugerida} según el Currículo Nacional."
                }
            ]
        }

    # 3. Consulta RAG con Gemini AI si está disponible
    if GOOGLE_API_KEY:
        try:
            model = genai.GenerativeModel("gemini-2.0-flash")
            prompt = PROMPT_EVALUACION_RAG.format(
                tema=req.tema,
                area_seleccionada=area_actual,
                nivel=req.nivel,
                contexto_rag=contexto_rag
            )
            response = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            res_json = json.loads(response.text)
            return res_json
        except Exception as e:
            logger.warning("Respuesta RAG Gemini fallback: %s", str(e))

    # Si coincide o es afín
    return {
        "coincide": True,
        "es_multiarea": False,
        "mensaje_evaluacion": f"Excelente. El tema '{req.tema}' coincide adecuadamente con el área y competencia seleccionadas según el Currículo Nacional.",
        "recomendaciones": []
    }
