"""
rag/chunker.py

Chunking semántico del texto limpio.
Respeta la estructura jerárquica del Currículo Nacional peruano:
Competencias, Capacidades, Estándares de Aprendizaje, Desempeños, Orientaciones.
Target: 500–800 tokens por chunk (medido con tiktoken).
Cada chunk conserva metadata + texto completo.
"""
import re
import uuid
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Aproximación: 1 token ≈ 4 caracteres para español
# Se usa tiktoken si está disponible, si no esta aproximación
TARGET_MIN_TOKENS = 500
TARGET_MAX_TOKENS = 800

# Palabras clave del currículo peruano que definen secciones semánticas
_CURRICULUM_SECTION_KEYWORDS = [
    r"^#+\s+",                                   # Encabezados Markdown
    r"^(?:COMPETENCIA|Competencia)\b",
    r"^(?:CAPACIDAD|Capacidad(?:es)?)\b",
    r"^(?:ESTÁNDAR|Estándar(?:es)?)\b",
    r"^(?:DESEMPEÑO|Desempeño(?:s)?)\b",
    r"^(?:ORIENTACIÓN|Orientación(?:es)?)\b",
    r"^(?:SITUACIONES DE APRENDIZAJE|Situaciones de aprendizaje)\b",
    r"^(?:ENFOQUE|Enfoque)\b",
    r"^(?:ÁREA|Área)\b.*:",
    r"^\*\*",                                     # Texto en negrita (títulos en Markdown)
]

_SECTION_BREAK_RE = re.compile(
    "|".join(_CURRICULUM_SECTION_KEYWORDS), re.MULTILINE | re.IGNORECASE
)


def _count_tokens_approx(text: str) -> int:
    """Cuenta tokens aproximados. Usa tiktoken si está disponible, si no aproximación por caracteres."""
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        # Fallback: ~4 chars por token en español (funciona bien para chunking)
        return len(text) // 4



def _split_into_sections(text: str) -> list[str]:
    """
    Divide el texto en secciones usando los marcadores semánticos del currículo.
    Cada sección comienza en un marcador de sección curricular o encabezado Markdown.
    """
    lines = text.splitlines(keepends=True)
    sections = []
    current_section = []

    for line in lines:
        if _SECTION_BREAK_RE.match(line.strip()) and current_section:
            section_text = "".join(current_section).strip()
            if section_text:
                sections.append(section_text)
            current_section = [line]
        else:
            current_section.append(line)

    if current_section:
        section_text = "".join(current_section).strip()
        if section_text:
            sections.append(section_text)

    return sections if sections else [text]


def _merge_sections(sections: list[str]) -> list[str]:
    """
    Combina secciones pequeñas hasta alcanzar el mínimo de tokens.
    Divide secciones muy grandes en partes de máximo TARGET_MAX_TOKENS.
    """
    chunks = []
    buffer = []
    buffer_tokens = 0

    for section in sections:
        section_tokens = _count_tokens_approx(section)

        if section_tokens > TARGET_MAX_TOKENS:
            # Flush buffer actual antes de dividir la sección grande
            if buffer:
                chunks.append("\n\n".join(buffer))
                buffer = []
                buffer_tokens = 0

            # Dividir la sección grande por párrafos
            paragraphs = section.split("\n\n")
            sub_buffer = []
            sub_tokens = 0
            for para in paragraphs:
                para_tokens = _count_tokens_approx(para)
                if sub_tokens + para_tokens > TARGET_MAX_TOKENS and sub_buffer:
                    chunks.append("\n\n".join(sub_buffer))
                    sub_buffer = [para]
                    sub_tokens = para_tokens
                else:
                    sub_buffer.append(para)
                    sub_tokens += para_tokens
            if sub_buffer:
                chunks.append("\n\n".join(sub_buffer))

        elif buffer_tokens + section_tokens > TARGET_MAX_TOKENS:
            # Hacer flush del buffer y empezar uno nuevo
            if buffer:
                chunks.append("\n\n".join(buffer))
            buffer = [section]
            buffer_tokens = section_tokens

        else:
            buffer.append(section)
            buffer_tokens += section_tokens

    if buffer:
        chunks.append("\n\n".join(buffer))

    return chunks


def chunk_document(text: str, base_metadata: dict) -> list[dict]:
    """
    Divide el texto limpio en chunks semánticos enriquecidos con metadata.

    Retorna lista de:
    {
        "id": str (UUID),
        "text": str,
        "metadata": {
            "nivel": str,
            "tipo": str,
            "archivo": str,
            "año": str,
            "version": str,
            "chunk_index": int,
            "tokens_approx": int,
            # Inferidos del contenido si es posible:
            "area": str,
            "ciclo": str,
            "grado": str,
            "competencia": str,
        }
    }
    """
    sections = _split_into_sections(text)
    raw_chunks = _merge_sections(sections)

    result = []
    for idx, chunk_text in enumerate(raw_chunks):
        if len(chunk_text.strip()) < 100:
            continue  # Descartar chunks muy pequeños

        metadata = dict(base_metadata)
        metadata["chunk_index"] = idx
        metadata["tokens_approx"] = _count_tokens_approx(chunk_text)

        # Inferencia de area a partir del contenido del chunk
        metadata["area"] = _infer_area(chunk_text, base_metadata.get("nivel", ""))
        metadata["ciclo"] = _infer_ciclo(chunk_text)
        metadata["grado"] = _infer_grado(chunk_text)
        metadata["competencia"] = _infer_competencia(chunk_text)

        result.append({
            "id": str(uuid.uuid4()),
            "text": chunk_text.strip(),
            "metadata": metadata,
        })

    logger.info(
        "Chunking: %d chunks generados de '%s'",
        len(result), base_metadata.get("archivo", "?")
    )
    return result


# ──── Inferencia ligera de metadata desde el texto del chunk ────

_AREA_KEYWORDS = {
    "matemática": ["matemática", "matematica", "números", "algebra", "geometría", "estadística"],
    "comunicación": ["comunicación", "comunicacion", "lectura", "escritura", "oral", "texto"],
    "ciencia y tecnología": ["ciencia", "tecnología", "experimento", "física", "química", "biología"],
    "personal social": ["personal social", "historia", "geografía", "ciudadanía", "convivencia"],
    "inglés": ["inglés", "ingles", "english", "listening", "speaking"],
    "educación religiosa": ["religiosa", "fe", "valores espirituales"],
    "arte y cultura": ["arte", "música", "expresión artística"],
    "educación física": ["educación física", "actividad física", "deporte", "movimiento"],
    "desarrollo personal": ["desarrollo personal", "ciudadanía", "cívica"],
}

_CICLO_KEYWORDS = {
    "I": ["ciclo i", "ciclo 1", "0 a 2", "0-2 años"],
    "II": ["ciclo ii", "ciclo 2", "3 a 5", "3-5 años", "inicial"],
    "III": ["ciclo iii", "ciclo 3", "1.° de primaria", "2.° de primaria"],
    "IV": ["ciclo iv", "ciclo 4", "3.° de primaria", "4.° de primaria"],
    "V": ["ciclo v", "ciclo 5", "5.° de primaria", "6.° de primaria"],
    "VI": ["ciclo vi", "ciclo 6", "1.° de secundaria", "2.° de secundaria"],
    "VII": ["ciclo vii", "ciclo 7", "3.° de secundaria", "4.° de secundaria", "5.° de secundaria"],
}

_GRADO_KEYWORDS = {
    "inicial": ["inicial", "jardín", "3 años", "4 años", "5 años"],
    "primero": ["primer grado", "1.° de primaria", "1° primaria"],
    "segundo": ["segundo grado", "2.° de primaria", "2° primaria"],
    "tercero": ["tercer grado", "3.° de primaria", "3° primaria"],
    "cuarto": ["cuarto grado", "4.° de primaria", "4° primaria"],
    "quinto_primaria": ["quinto grado", "5.° de primaria", "5° primaria"],
    "sexto": ["sexto grado", "6.° de primaria", "6° primaria"],
    "primero_sec": ["1.° de secundaria", "1° secundaria"],
    "segundo_sec": ["2.° de secundaria", "2° secundaria"],
    "tercero_sec": ["3.° de secundaria", "3° secundaria"],
    "cuarto_sec": ["4.° de secundaria", "4° secundaria"],
    "quinto_sec": ["5.° de secundaria", "5° secundaria"],
}


def _infer_area(text: str, nivel: str) -> str:
    text_lower = text.lower()
    for area, keywords in _AREA_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                return area
    return "general"


def _infer_ciclo(text: str) -> str:
    text_lower = text.lower()
    for ciclo, keywords in _CICLO_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                return ciclo
    return ""


def _infer_grado(text: str) -> str:
    text_lower = text.lower()
    for grado, keywords in _GRADO_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                return grado
    return ""


def _infer_competencia(text: str) -> str:
    """Extrae el nombre de la competencia si aparece en el primer encabezado del chunk."""
    lines = text.splitlines()
    for line in lines[:5]:
        stripped = line.strip()
        if stripped.lower().startswith("competen"):
            return stripped[:120]
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()[:120]
    return ""
