"""
Módulo de Recomendación Curricular (Copiloto Pedagógico RAG Semántico Robustecido) para EduAI.
Normaliza acentos, diacríticos y mayúsculas/minúsculas para analizar cualquier variación de texto.
Utiliza el Currículo Nacional de la Educación Básica (CNEB) del Perú.
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
        "enfoque": "Comprensión de fenómenos físicos, seres vivos, anatomía, botánica, química y ecología."
    },
    "Ciencias Sociales": {
        "competencia": "Construye interpretaciones históricas",
        "capacidades": ["Interpreta críticamente fuentes diversas", "Comprende el tiempo histórico", "Elabora explicaciones sobre procesos históricos"],
        "enfoque": "Análisis histórico, geográfico, procesos sociales y economía."
    },
    "Personal Social": {
        "competencia": "Construye su identidad",
        "capacidades": ["Se valora a sí mismo", "Autorregula sus emociones", "Reflexiona y argumenta éticamente"],
        "enfoque": "Desarrollo socioemocional, ciudadanía, convivencia y autoconocimiento."
    },
    "Educación para el Trabajo": {
        "competencia": "Gestiona proyectos de emprendimiento económico o social",
        "capacidades": ["Crea propuestas de valor", "Trabaja cooperativamente para lograr objetivos y metas", "Aplica habilidades técnicas"],
        "enfoque": "Diseño de proyectos, electrónica, robótica, emprendimiento, modelo canvas y habilidades técnicas."
    },
    "Matemática": {
        "competencia": "Resuelve problemas de cantidad",
        "capacidades": ["Traduce cantidades a expresiones numéricas", "Comunica su comprensión sobre los números y las operaciones"],
        "enfoque": "Razonamiento numérico, álgebra, geometría, cálculo y estadística."
    },
    "Comunicación": {
        "competencia": "Lee diversos tipos de textos escritos en su lengua materna",
        "capacidades": ["Obtiene información del texto escrito", "Infiere e interpreta información del texto"],
        "enfoque": "Comprensión lectora, gramática, ortografía, lírica, narrativa y comunicación oral."
    },
    "Educación Física": {
        "competencia": "Se desenvuelve de manera autónoma a través de su motricidad",
        "capacidades": ["Comprende su cuerpo", "Se expresa corporalmente"],
        "enfoque": "Desarrollo motriz, expresión corporal, deportes, atletismo y vida saludable."
    },
    "Arte y Cultura": {
        "competencia": "Crea proyectos desde los lenguajes artísticos",
        "capacidades": ["Explora y experimenta los lenguajes del arte", "Aplica procesos creativos"],
        "enfoque": "Expresión plástica, pintura, dibujo, música, danza, teatro y patrimonio cultural."
    },
    "Educación Religiosa": {
        "competencia": "Construye su identidad como persona humana, amada por Dios",
        "capacidades": ["Conoce a Dios y asume su identidad religiosa", "Cultiva y valora las manifestaciones religiosas"],
        "enfoque": "Formación espiritual, ética cristiana, valores y parábolas."
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
    """Clasificador semántico del tema usando patrones amplios del CNEB."""
    t = tema_limpio

    # 1. Ciencia y Tecnología (Biología, Anatomía, Física, Química, Ecología)
    palabras_ciencia = [
        "sistema nervioso", "nervioso", "cerebro", "neurona", "medula", "celula", "organelo", "mitocondria",
        "fotosinte", "seres vivos", "ser vivo", "reino animal", "reino vegetal", "fungi", "bacterias", "virus",
        "ecosistema", "biodiversidad", "movimiento", "rectilineo", "mru", "mrv", "gravedad", "velocidad",
        "aceleracion", "fuerza", "vector", "cinematica", "energia", "materia", "atomo", "molecula", "quimica",
        "fisica", "biologia", "aparato digestivo", "digestiv", "circulatorio", "respiratorio", "excretor",
        "esqueleto", "hueso", "musculo", "adn", "genetica", "termodinamica", "experimento", "planeta", "clima global"
    ]
    if any(p in t for p in palabras_ciencia):
        return "Ciencia y Tecnología"

    # 2. Educación para el Trabajo (EPT)
    palabras_ept = [
        "circuito", "electron", "electric", "robotic", "programaci", "software", "mantenimiento", "carpinteri",
        "emprend", "negocio", "canvas", "modelo de negocio", "propuesta de valor", "mercadotecnia", "presupuesto",
        "soldadura", "confeccion", "textil", "habilidades tecnicas", "inventario", "taller digital"
    ]
    if any(p in t for p in palabras_ept):
        return "Educación para el Trabajo"

    # 3. Ciencias Sociales (Historia, Geografía, Economía)
    palabras_ccss = [
        "revoluci", "guerra", "independencia", "historia", "mapa", "geograf", "feudalism", "imperio", "cultura",
        "virreinato", "incas", "tahuantinsuyo", "preinca", "chavin", "mochica", "nazca", "paracas", "primer gobierno",
        "guerra del pacifico", "revolucion industrial", "constitucion", "relieve", "cuenca", "economia", "mercado"
    ]
    if any(p in t for p in palabras_ccss):
        return "Ciencias Sociales"

    # 4. Personal Social / DPCC
    palabras_psocial = [
        "emocion", "sentimient", "autoestima", "identidad", "convivenc", "norma", "derecho", "valores", "etica",
        "pubertad", "adolescencia", "resolucion de conflictos", "bullying", "ciudadania", "participacion"
    ]
    if any(p in t for p in palabras_psocial):
        return "Personal Social"

    # 5. Matemática
    palabras_mate = [
        "suma", "resta", "multiplica", "division", "fraccion", "porcentaje", "ecuacion", "inecuacion", "geometr",
        "angulo", "triangulo", "area", "perimetro", "probabilidad", "algebra", "polinomio", "estadistica",
        "regla de tres", "razon", "proporcion", "trigonometria", "plano cartesiano", "volumen", "matematica"
    ]
    if any(p in t for p in palabras_mate):
        return "Matemática"

    # 6. Comunicación
    palabras_comu = [
        "cuento", "lectura", "poes", "poema", "afiche", "ensayo", "ortograf", "gramatic", "redacci", "debate",
        "leyenda", "fabula", "comprension lectora", "novela", "obra literaria", "oratoria", "discurso", "sintaxis"
    ]
    if any(p in t for p in palabras_comu):
        return "Comunicación"

    # 7. Educación Física
    palabras_edfis = [
        "motricid", "esquema corporal", "deporte", "ejercicio", "gimnas", "futbol", "basquet", "voley",
        "atletismo", "calentamiento", "resistencia", "flexibilidad", "actividad fisica", "juego predeportivo"
    ]
    if any(p in t for p in palabras_edfis):
        return "Educación Física"

    # 8. Arte y Cultura
    palabras_arte = [
        "dibujo", "pintura", "escultura", "grabado", "musica", "instrumento", "ritmo", "melodia", "danza",
        "baile", "teatro", "dramatizac", "artes plasticas", "folclore", "manifestacion artistica", "acuarela"
    ]
    if any(p in t for p in palabras_arte):
        return "Arte y Cultura"

    # 9. Educación Religiosa
    palabras_religion = [
        "dios", "jesus", "biblia", "evangelio", "parabola", "mandamiento", "sacramento", "oracion", "virgen maria", "fe"
    ]
    if any(p in t for p in palabras_religion):
        return "Educación Religiosa"

    return None


def obtener_recomendacion_curricular(req: RecommendRequest) -> Dict[str, Any]:
    """Evalúa si el tema coincide adecuadamente o sugiere el área oficial correspondiente."""
    tema_limpio = _limpiar_texto(req.tema)
    area_actual_limpia = _limpiar_texto(req.area_seleccionada)

    logger.info("Copiloto RAG evaluando tema '%s' (normalizado: '%s') para el área '%s'", req.tema, tema_limpio, req.area_seleccionada)

    # 1. Búsqueda vectorial semántica en Qdrant DB para enriquecer el contexto
    qdrant_area_detectada = None
    try:
        chunks = search(query=f"Área curricular competencias para el tema {req.tema}", filters={"nivel": req.nivel}, top_k=3)
        for c in chunks:
            text = c.get("text", "")
            for area_nombre in AREAS_CNEB_INFO:
                if area_nombre.lower() in text.lower():
                    qdrant_area_detectada = area_nombre
                    break
            if qdrant_area_detectada:
                break
    except Exception as e:
        logger.warning("Qdrant RAG aviso: %s", str(e))

    # 2. Detectar área real sugerida (prioridad clasificador pedagógico -> Qdrant)
    area_sugerida = detectar_area_pedagogica(tema_limpio) or qdrant_area_detectada

    # 3. Si se detectó un área específica y no coincide con el área seleccionada
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
                        "enfoque_explicacion": f"Según el Currículo Nacional (CNEB), el tema '{req.tema}' corresponde a las competencias del área de {area_sugerida}."
                    }
                ]
            }

    # 4. Si coincide verdaderamente
    return {
        "coincide": True,
        "es_multiarea": False,
        "mensaje_evaluacion": f"Excelente. El tema '{req.tema}' coincide adecuadamente con el área y competencia seleccionadas según el Currículo Nacional.",
        "recomendaciones": []
    }
