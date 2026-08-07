"""
rag/extractor.py

Extracción de texto desde PDFs usando Docling.
Inferencia automática de metadata (nivel, tipo) a partir de la ruta del archivo.
"""
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _infer_metadata_from_path(pdf_path: Path) -> dict:
    """
    Infiere metadata básica a partir del nombre del archivo y la estructura de carpetas.
    Ejemplo: pdfs/programa-nivel-primaria-ebr.pdf → nivel="primaria"
    """
    name = pdf_path.stem.lower()
    parent = pdf_path.parent.name.lower()

    # Nivel educativo
    nivel = "general"
    for candidate in ("inicial", "primaria", "secundaria"):
        if candidate in name or candidate in parent:
            nivel = candidate
            break

    # Tipo de documento
    tipo = "general"
    if "curriculo" in name or "curriculum" in name:
        tipo = "curriculo_nacional"
    elif "programa" in name:
        tipo = "programa_curricular"
    elif "orientacion" in name or "planificacion" in name:
        tipo = "orientaciones"
    elif "evaluacion" in name or "formativa" in name:
        tipo = "evaluacion"
    elif "fasciculo" in name:
        tipo = "fasciculo"
    elif "guia" in name:
        tipo = "guia"

    return {
        "nivel": nivel,
        "tipo": tipo,
        "archivo": pdf_path.name,
        "año": "2016",    # Versión por defecto del CN Perú; actualizar si hay versión nueva
        "version": "1.0",
    }


def extract_pdf(pdf_path: Path) -> Optional[dict]:
    """
    Extrae el texto de un PDF usando Docling y retorna:
    {
        "text": str,           # Texto en Markdown estructurado
        "metadata": dict,      # Metadata inferida
        "num_pages": int,
    }
    Retorna None si el archivo no existe o falla la extracción.
    """
    if not pdf_path.exists():
        logger.error("PDF no encontrado: %s", pdf_path)
        return None

    try:
        from docling.document_converter import DocumentConverter

        logger.info("Extrayendo texto de: %s", pdf_path.name)
        converter = DocumentConverter()
        result = converter.convert(str(pdf_path))

        # Docling puede exportar el documento a Markdown
        doc = result.document
        markdown_text = doc.export_to_markdown()

        metadata = _infer_metadata_from_path(pdf_path)
        num_pages = len(doc.pages) if hasattr(doc, "pages") else 0

        logger.info(
            "Extraídas %d páginas de %s (nivel=%s, tipo=%s)",
            num_pages, pdf_path.name, metadata["nivel"], metadata["tipo"]
        )

        return {
            "text": markdown_text,
            "metadata": metadata,
            "num_pages": num_pages,
        }

    except Exception as e:
        logger.exception("Error extrayendo %s: %s", pdf_path.name, e)
        return None
