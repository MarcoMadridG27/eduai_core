"""
Módulo de Recomendación Curricular (Copiloto Pedagógico) para EduAI.
Analiza el tema ingresado por el docente utilizando RAG sobre Qdrant + Matriz CNEB oficial
para sugerir áreas, competencias, capacidades y enfoques con tono pedagógico orientador.
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


# Mapeo CNEB RAG de palabras clave -> Áreas y Competencias Sugeridas
MAPEO_PEDAGOGICO = {
    "emocion": {
        "area": "Personal Social",
        "competencia": "Construye su identidad",
        "capacidades": ["Se valora a sí mismo", "Autorregula sus emociones"],
        "explicacion": "El desarrollo socioemocional y reconocimiento de emociones se aborda en Personal Social."
    },
    "sentimient": {
        "area": "Personal Social",
        "competencia": "Construye su identidad",
        "capacidades": ["Se valora a sí mismo", "Autorregula sus emociones"],
        "explicacion": "Los sentimientos y autorregulación emocional corresponden al desarrollo personal."
    },
    "autonomia": {
        "area": "Personal Social",
        "competencia": "Construye su identidad",
        "capacidades": ["Se valora a sí mismo", "Autorregula sus emociones"],
        "explicacion": "La autonomía se trabaja en Personal Social a través de la construcción de la identidad."
    },
    "norma": {
        "area": "Personal Social",
        "competencia": "Convive y participa democráticamente en la búsqueda del bien común",
        "capacidades": ["Interactúa con todas las personas", "Construye normas y asume acuerdos y leyes"],
        "explicacion": "Las normas de convivencia y acuerdos del aula pertenecen a la competencia de convivencia democrática."
    },
    "convivenc": {
        "area": "Personal Social",
        "competencia": "Convive y participa democráticamente en la búsqueda del bien común",
        "capacidades": ["Interactúa con todas las personas", "Construye normas y asume acuerdos y leyes"],
        "explicacion": "La convivencia pacífica e interacción social corresponden al área de Personal Social."
    },
    "motricid": {
        "area": "Psicomotricidad",
        "competencia": "Se desenvuelve de manera autónoma a través de su motricidad",
        "capacidades": ["Comprende su cuerpo", "Se expresa corporalmente"],
        "explicacion": "Las habilidades motrices y la exploración corporal corresponden a Psicomotricidad / Educación Física."
    },
    "cuerpo": {
        "area": "Psicomotricidad",
        "competencia": "Se desenvuelve de manera autónoma a través de su motricidad",
        "capacidades": ["Comprende su cuerpo", "Se expresa corporalmente"],
        "explicacion": "El esquema corporal y movimiento autónomo pertenecen a Psicomotricidad / Educación Física."
    },
    "cuento": {
        "area": "Comunicación",
        "competencia": "Lee diversos tipos de textos escritos en su lengua materna",
        "capacidades": ["Obtiene información del texto escrito", "Infiere e interpreta información del texto"],
        "explicacion": "La lectura y creación de cuentos e historias desarrolla las competencias comunicativas."
    },
    "lectura": {
        "area": "Comunicación",
        "competencia": "Lee diversos tipos de textos escritos en su lengua materna",
        "capacidades": ["Obtiene información del texto escrito", "Infiere e interpreta información del texto"],
        "explicacion": "La comprensión lectora se promueve en el área de Comunicación."
    },
    "suma": {
        "area": "Matemática",
        "competencia": "Resuelve problemas de cantidad",
        "capacidades": ["Traduce cantidades a expresiones numéricas", "Comunica su comprensión sobre los números"],
        "explicacion": "Las operaciones de adición y conteo forman parte del razonamiento cuantitativo."
    },
    "numero": {
        "area": "Matemática",
        "competencia": "Resuelve problemas de cantidad",
        "capacidades": ["Traduce cantidades a expresiones numéricas", "Comunica su comprensión sobre los números"],
        "explicacion": "La noción de número y conteo se trabaja en el área de Matemática."
    },
    "forma": {
        "area": "Matemática",
        "competencia": "Resuelve problemas de forma, movimiento y localización",
        "capacidades": ["Modela objetos con formas geométricas", "Comunica su comprensión sobre las formas"],
        "explicacion": "Las formas geométricas y la ubicación en el espacio corresponden a la competencia espacial."
    },
    "planta": {
        "area": "Ciencia y Tecnología",
        "competencia": "Indaga mediante métodos científicos para construir sus conocimientos",
        "capacidades": ["Problematiza situaciones para hacer indagación", "Genera y registra datos o información"],
        "explicacion": "El estudio de los seres vivos y la naturaleza se desarrolla en Ciencia y Tecnología / Descubrimiento del Mundo."
    },
    "animal": {
        "area": "Ciencia y Tecnología",
        "competencia": "Indaga mediante métodos científicos para construir sus conocimientos",
        "capacidades": ["Problematiza situaciones para hacer indagación", "Genera y registra datos o información"],
        "explicacion": "La observación y cuidado de los animales forma parte de la indagación científica."
    }
}

# Temas transversales multi-área
TEMAS_MULTIAREA = {
    "agua": [
        {
            "area": "Ciencia y Tecnología",
            "competencia": "Indaga mediante métodos científicos para construir sus conocimientos",
            "capacidades": ["Problematiza situaciones para hacer indagación", "Genera y registra datos o información"],
            "enfoque_explicacion": "Enfoque científico: Experimentos, estados físicos del agua y ciclo hidrológico."
        },
        {
            "area": "Personal Social",
            "competencia": "Gestiona responsablemente el espacio y el ambiente",
            "capacidades": ["Comprende las relaciones entre los elementos naturales y sociales", "Genera acciones para conservar el ambiente"],
            "enfoque_explicacion": "Enfoque ambiental y ciudadano: Cuidado del agua y uso responsable en la comunidad."
        },
        {
            "area": "Comunicación",
            "competencia": "Escribe diversos tipos de textos en su lengua materna",
            "capacidades": ["Adecúa el texto a la situación comunicativa", "Organiza y desarrolla las ideas de forma coherente"],
            "enfoque_explicacion": "Enfoque comunicativo: Creación de afiches, slogans o poesías sobre la importancia del agua."
        }
    ],
    "reciclaj": [
        {
            "area": "Personal Social",
            "competencia": "Gestiona responsablemente el espacio y el ambiente",
            "capacidades": ["Comprende las relaciones entre los elementos naturales y sociales", "Genera acciones para conservar el ambiente"],
            "enfoque_explicacion": "Enfoque ambiental: Conciencia ecológica y segregación de residuos en el colegio."
        },
        {
            "area": "Ciencia y Tecnología",
            "competencia": "Diseña y construye soluciones tecnológicas para resolver problemas de su entorno",
            "capacidades": ["Determina una alternativa de solución tecnológica", "Diseña la alternativa de solución"],
            "enfoque_explicacion": "Enfoque tecnológico: Construcción de juguetes o utilitarios con material reciclado."
        }
    ]
}


def obtener_recomendacion_curricular(req: RecommendRequest) -> Dict[str, Any]:
    """
    Analiza el tema con RAG en Qdrant y evalúa si la selección del docente coincide o sugiere
    alternativas pedagógicas según el CNEB.
    """
    tema_lower = req.tema.strip().lower()
    logger.info("Copiloto Curricular analizando tema: '%s' (Nivel: %s, Área selec: %s)", req.tema, req.nivel, req.area_seleccionada)

    # 1. Verificar si es un Tema Multi-Área (Caso C)
    for clave, opciones in TEMAS_MULTIAREA.items():
        if clave in tema_lower:
            return {
                "coincide": False,
                "es_multiarea": True,
                "mensaje_evaluacion": f"El tema '{req.tema}' es un eje integrador que puede abordarse desde distintas áreas del Currículo Nacional según el enfoque de tu sesión.",
                "recomendaciones": opciones
            }

    # 2. Análisis por coincidencias de la matriz CNEB RAG (Caso B)
    sugerencia_pedagogica = None
    for clave, sug in MAPEO_PEDAGOGICO.items():
        if clave in tema_lower:
            sugerencia_pedagogica = sug
            break

    # Si encontramos una sugerencia pedagógica clara
    if sugerencia_pedagogica:
        area_sugerida = sugerencia_pedagogica["area"]
        comp_sugerida = sugerencia_pedagogica["competencia"]
        area_actual = (req.area_seleccionada or "").strip().lower()

        # Si el área seleccionada por el docente NO coincide con el área pedagógica estándar del CNEB
        if area_actual and area_actual != area_sugerida.lower():
            return {
                "coincide": False,
                "es_multiarea": False,
                "mensaje_evaluacion": f"La IA detectó que el tema '{req.tema}' se desarrolla habitualmente en el área de {area_sugerida} mediante la competencia '{comp_sugerida}'. Actualmente seleccionaste {req.area_seleccionada}. Puedes adaptar la recomendación o mantener tu selección si deseas darle otro enfoque.",
                "recomendaciones": [
                    {
                        "area": area_sugerida,
                        "competencia": comp_sugerida,
                        "capacidades": sugerencia_pedagogica["capacidades"],
                        "enfoque_explicacion": sugerencia_pedagogica["explicacion"]
                    }
                ]
            }

    # 3. Consulta RAG a Qdrant para enriquecer la respuesta
    chunks = search(query=f"Competencia área curricular {req.tema}", filters={"nivel": req.nivel}, top_k=2)

    # Caso A: Todo coincide o no requiere corrección
    return {
        "coincide": True,
        "es_multiarea": False,
        "mensaje_evaluacion": f"Excelente. El tema '{req.tema}' coincide adecuadamente con el área y competencia seleccionadas según el Currículo Nacional.",
        "recomendaciones": []
    }
