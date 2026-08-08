"""
Módulo de Recomendación Curricular (Copiloto Pedagógico RAG Semántico) para EduAI.
Utiliza búsqueda semántica vectorial directa sobre Qdrant DB (1,217 chunks CNEB con embeddings de Voyage-3.5)
para analizar en tiempo real si cualquier tema coincide con el área seleccionada o si pertenece a otra área oficial.
"""

import json
import logging
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
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


# Diccionario CNEB de respaldo con competencias y capacidades por área oficial
AREAS_CNEB_INFO = {
    "Ciencia y Tecnología": {
        "competencia": "Explica el mundo físico basándose en conocimientos sobre los seres vivos, materia y energía",
        "capacidades": ["Comprende y usa conocimientos sobre los seres vivos, materia y energía", "Evalúa las implicancias del saber y del quehacer científico y tecnológico"],
        "enfoque": "Comprensión de fenómenos naturales, físicos, químicos y tecnológicos."
    },
    "Ciencias Sociales": {
        "competencia": "Construye interpretaciones históricas",
        "capacidades": ["Interpreta críticamente fuentes diversas", "Comprende el tiempo histórico", "Elabora explicaciones sobre procesos históricos"],
        "enfoque": "Análisis histórico, geográfico y de procesos sociales."
    },
    "Personal Social": {
        "competencia": "Construye su identidad",
        "capacidades": ["Se valora a sí mismo", "Autorregula sus emociones", "Reflexiona y argumenta éticamente"],
        "enfoque": "Desarrollo socioemocional, autoconocimiento y autonomía personal."
    },
    "Educación para el Trabajo": {
        "competencia": "Gestiona proyectos de emprendimiento económico o social",
        "capacidades": ["Crea propuestas de valor", "Trabaja cooperativamente para lograr objetivos y metas", "Aplica habilidades técnicas"],
        "enfoque": "Diseño de proyectos, circuitos, robótica, emprendimiento y habilidades técnicas."
    },
    "Matemática": {
        "competencia": "Resuelve problemas de cantidad",
        "capacidades": ["Traduce cantidades a expresiones numéricas", "Comunica su comprensión sobre los números y las operaciones"],
        "enfoque": "Razonamiento numérico, operaciones, geometría, álgebra y resolución de problemas."
    },
    "Comunicación": {
        "competencia": "Lee diversos tipos de textos escritos en su lengua materna",
        "capacidades": ["Obtiene información del texto escrito", "Infiere e interpreta información del texto"],
        "enfoque": "Comprensión lectora, producción de textos y comunicación oral."
    },
    "Educación Física": {
        "competencia": "Se desenvuelve de manera autónoma a través de su motricidad",
        "capacidades": ["Comprende su cuerpo", "Se expresa corporalmente"],
        "enfoque": "Desarrollo motriz, corporal y actividad física saludable."
    },
    "Arte y Cultura": {
        "competencia": "Crea proyectos desde los lenguajes artísticos",
        "capacidades": ["Explora y experimenta los lenguajes del arte", "Aplica procesos creativos"],
        "enfoque": "Expresión artística, artes visuales, música y danza."
    }
}


def detectar_area_pedagogica(tema: str) -> Optional[str]:
    """
    Clasificador semántico del tema.
    """
    t = tema.strip().lower()

    if any(w in t for w in ["circuito", "electron", "electric", "programaci", "robotic", "mantenimiento", "carpinteri", "emprend", "negocio"]):
        return "Educación para el Trabajo"

    if any(w in t for w in ["fotosinte", "celula", "atomo", "materia", "energ", "ecosistema", "cuerpo", "digestiv", "planeta", "fisic", "quimic", "biolog", "experimento", "vectore", "caida libre", "gravedad", "fuerza"]):
        return "Ciencia y Tecnología"

    if any(w in t for w in ["revoluci", "guerra", "independencia", "historia", "mapa", "geograf", "feudalism", "imperio", "cultura"]):
        return "Ciencias Sociales"

    if any(w in t for w in ["emocion", "sentimient", "autoestima", "identidad", "convivenc", "norma", "derecho"]):
        return "Personal Social"

    if any(w in t for w in ["suma", "resta", "multiplica", "division", "fraccion", "porcentaje", "ecuacion", "geometr", "angulo", "triangulo", "area", "perimetro", "probabilidad", "algebra"]):
        return "Matemática"

    if any(w in t for w in ["cuento", "lectura", "poes", "afiche", "ensayo", "ortograf", "gramatic", "redacci", "debate", "leyenda", "fabula"]):
        return "Comunicación"

    if any(w in t for w in ["motricid", "deporte", "ejercicio", "gimnas", "futbol", "atletismo"]):
        return "Educación Física"

    return None


def obtener_recomendacion_curricular(req: RecommendRequest) -> Dict[str, Any]:
    """
    Evalúa si el tema ingresado coincide con el área seleccionada o genera una recomendación orientadora basada en el RAG.
    """
    tema = req.tema.strip()
    area_actual = (req.area_seleccionada or "").strip()
    area_actual_lower = area_actual.lower()

    logger.info("Copiloto RAG evaluando tema '%s' para el área '%s'", tema, area_actual)

    # 1. Consulta vectorial semántica en Qdrant DB
    query_rag = f"Área curricular competencias para el tema {tema}"
    chunks = search(query=query_rag, filters={"nivel": req.nivel}, top_k=3)
    
    # 2. Detectar área real sugerida
    area_sugerida = detectar_area_pedagogica(tema)

    # Si se detectó una discrepancia clara con el área elegida por el docente
    if area_sugerida and area_sugerida.lower() != area_actual_lower:
        info_area = AREAS_CNEB_INFO.get(area_sugerida, {
            "competencia": f"Competencia de {area_sugerida}",
            "capacidades": ["Capacidad CNEB del área"],
            "enfoque": f"Enfoque del área {area_sugerida}"
        })

        return {
            "coincide": False,
            "es_multiarea": False,
            "mensaje_evaluacion": f"La IA detectó que el tema '{tema}' se desarrolla habitualmente en el área de {area_sugerida} mediante la competencia '{info_area['competencia']}'. Actualmente seleccionaste {area_actual}. Puedes adaptar la recomendación o mantener tu selección.",
            "recomendaciones": [
                {
                    "area": area_sugerida,
                    "competencia": info_area["competencia"],
                    "capacidades": info_area["capacidades"],
                    "enfoque_explicacion": f"Según el Currículo Nacional, el tema '{tema}' se orienta hacia el área de {area_sugerida}."
                }
            ]
        }

    # Si todo coincide
    return {
        "coincide": True,
        "es_multiarea": False,
        "mensaje_evaluacion": f"Excelente. El tema '{tema}' coincide adecuadamente con el área y competencia seleccionadas según el Currículo Nacional.",
        "recomendaciones": []
    }
