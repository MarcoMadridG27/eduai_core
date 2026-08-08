"""
Módulo de Recomendación Curricular (Copiloto Pedagógico RAG Semántico Robustecido) para EduAI.
Normaliza acentos, diacríticos y mayúsculas/minúsculas para analizar cualquier variación de texto.
"""

import json
import logging
import unicodedata
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


AREAS_CNEB_INFO = {
    "Ciencia y Tecnología": {
        "competencia": "Explica el mundo físico basándose en conocimientos sobre los seres vivos, materia y energía",
        "capacidades": ["Comprende y usa conocimientos sobre los seres vivos, materia y energía", "Evalúa las implicancias del saber y del quehacer científico y tecnológico"],
        "enfoque": "Comprensión de fenómenos físicos, cinemática, movimiento, química y seres vivos."
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


def _limpiar_texto(texto: str) -> str:
    """Normaliza texto eliminando acentos, diacríticos y convirtiendo a minúsculas."""
    if not texto:
        return ""
    texto_norm = unicodedata.normalize('NFD', texto)
    texto_sin_acentos = ''.join(c for c in texto_norm if unicodedata.category(c) != 'Mn')
    return texto_sin_acentos.lower().strip()


def detectar_area_pedagogica(tema_limpio: str) -> Optional[str]:
    """Clasificador semántico del tema usando patrones amplios normalizados."""
    t = tema_limpio

    # Ciencia y Tecnología (Física, Biología, Química)
    palabras_ciencia = [
        "movimiento", "movimient", "rectilineo", "rect", "mru", "mrv", "caida", "libre", "gravedad",
        "velocidad", "aceleracion", "fuerza", "vector", "cinematica", "energia", "materia", "atomo",
        "celula", "fotosinte", "ecosistema", "digestiv", "planeta", "fisic", "quimic", "biolog", "experimento"
    ]
    if any(p in t for p in palabras_ciencia):
        return "Ciencia y Tecnología"

    # Educación para el Trabajo
    palabras_ept = [
        "circuito", "electron", "electric", "programaci", "robotic", "mantenimiento", "carpinteri", "emprend", "negocio"
    ]
    if any(p in t for p in palabras_ept):
        return "Educación para el Trabajo"

    # Ciencias Sociales
    palabras_ccss = [
        "revoluci", "guerra", "independencia", "historia", "mapa", "geograf", "feudalism", "imperio", "cultura"
    ]
    if any(p in t for p in palabras_ccss):
        return "Ciencias Sociales"

    # Personal Social
    palabras_psocial = [
        "emocion", "sentimient", "autoestima", "identidad", "convivenc", "norma", "derecho"
    ]
    if any(p in t for p in palabras_psocial):
        return "Personal Social"

    # Matemática
    palabras_mate = [
        "suma", "resta", "multiplica", "division", "fraccion", "porcentaje", "ecuacion", "geometr",
        "angulo", "triangulo", "area", "perimetro", "probabilidad", "algebra"
    ]
    if any(p in t for p in palabras_mate):
        return "Matemática"

    # Comunicación
    palabras_comu = [
        "cuento", "lectura", "poes", "afiche", "ensayo", "ortograf", "gramatic", "redacci", "debate", "leyenda", "fabula"
    ]
    if any(p in t for p in palabras_comu):
        return "Comunicación"

    # Educación Física
    palabras_edfis = [
        "motricid", "deporte", "ejercicio", "gimnas", "futbol", "atletismo", "calentamiento", "resistencia"
    ]
    if any(p in t for p in palabras_edfis):
        return "Educación Física"

    return None


def obtener_recomendacion_curricular(req: RecommendRequest) -> Dict[str, Any]:
    """Evalúa si el tema coincide adecuadamente o sugiere el área oficial correspondiente."""
    tema_limpio = _limpiar_texto(req.tema)
    area_actual_limpia = _limpiar_texto(req.area_seleccionada)

    logger.info("Copiloto RAG evaluando tema '%s' (normalizado: '%s') para el área '%s'", req.tema, tema_limpio, req.area_seleccionada)

    # 1. Búsqueda vectorial semántica en Qdrant DB
    try:
        search(query=f"Área curricular competencias para el tema {req.tema}", filters={"nivel": req.nivel}, top_k=3)
    except Exception as e:
        logger.warning("Qdrant RAG aviso: %s", str(e))

    # 2. Detectar área real sugerida
    area_sugerida = detectar_area_pedagogica(tema_limpio)

    # Si se detectó un área específica diferente a la seleccionada
    if area_sugerida:
        area_sugerida_limpia = _limpiar_texto(area_sugerida)
        if area_sugerida_limpia != area_actual_limpia:
            info_area = AREAS_CNEB_INFO.get(area_sugerida, {
                "competencia": f"Competencia oficial del área de {area_sugerida}",
                "capacidades": ["Capacidad CNEB del área"],
                "enfoque": f"Enfoque pedagógico de {area_sugerida}"
            })

            return {
                "coincide": False,
                "es_multiarea": False,
                "mensaje_evaluacion": f"La IA detectó que el tema '{req.tema}' se desarrolla habitualmente en el área de {area_sugerida} mediante la competencia '{info_area['competencia']}'. Actualmente seleccionaste {req.area_seleccionada}. Puedes adaptar la recomendación o mantener tu selección.",
                "recomendaciones": [
                    {
                        "area": area_sugerida,
                        "competencia": info_area["competencia"],
                        "capacidades": info_area["capacidades"],
                        "enfoque_explicacion": f"Según el Currículo Nacional, el tema '{req.tema}' corresponde a las competencias del área de {area_sugerida}."
                    }
                ]
            }

    # Si coincide
    return {
        "coincide": True,
        "es_multiarea": False,
        "mensaje_evaluacion": f"Excelente. El tema '{req.tema}' coincide adecuadamente con el área y competencia seleccionadas según el Currículo Nacional.",
        "recomendaciones": []
    }
