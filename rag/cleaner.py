"""
rag/cleaner.py

Limpieza del texto extraído por Docling.
Elimina ruido: números de página, encabezados/pies repetidos, caracteres extraños.
Preserva únicamente el contenido pedagógico útil.
"""
import re


# Patrones de líneas que NO son contenido pedagógico
_NOISE_PATTERNS = [
    r"^\s*\d+\s*$",                        # Líneas que solo contienen un número (nro de página)
    r"^[-–—_=*]{3,}\s*$",                  # Separadores de línea
    r"(?i)^(ministerio de educaci[oó]n|minedu|cneb|www\.).*$",  # Logos/headers institucionales
    r"(?i)^currículo nacional.*$",         # Títulos repetidos del CN
    r"(?i)^programa curricular.*$",        # Títulos repetidos de programas
    r"(?i)^\d{1,3}\s*$",                   # Paginación suelta
    r"(?i)^(página|pág\.?|page)\s*\d+",   # "Página 12"
]

_NOISE_RE = re.compile("|".join(_NOISE_PATTERNS), re.MULTILINE)

# Mínimo de caracteres por párrafo para conservarlo
MIN_CHUNK_CHARS = 60


def clean_text(text: str) -> str:
    """
    Limpia el texto Markdown extraído de un PDF:
    1. Elimina líneas de ruido (nros de página, headers institucionales)
    2. Colapsa múltiples saltos de línea
    3. Normaliza espacios
    4. Elimina párrafos demasiado cortos
    Retorna el texto limpio como string.
    """
    # Eliminar líneas de ruido
    lines = text.splitlines()
    cleaned_lines = []
    for line in lines:
        if _NOISE_RE.match(line.strip()):
            continue
        cleaned_lines.append(line)

    text = "\n".join(cleaned_lines)

    # Colapsar 3+ saltos de línea → 2 (separador de párrafo)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Eliminar espacios al inicio/fin de cada línea
    text = "\n".join(l.rstrip() for l in text.splitlines())

    # Eliminar párrafos muy cortos (encabezados sueltos sin contenido)
    paragraphs = text.split("\n\n")
    paragraphs = [
        p for p in paragraphs
        if len(p.strip()) >= MIN_CHUNK_CHARS or p.strip().startswith("#")
    ]

    return "\n\n".join(paragraphs).strip()
