"""
rag/retriever.py

Recuperación de contexto desde Qdrant.
Reemplaza completamente knowledge.py.

Función principal: search(query, filters, top_k)
  1. Genera embedding de la consulta (VoyageEmbedder, modo query)
  2. Aplica filtros de metadata (nivel, grado, area)
  3. Consulta Qdrant y recupera top-K chunks
  4. Elimina duplicados
  5. Retorna lista de strings de contexto listos para el prompt
"""
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Cliente y embedder se inicializan en la primera llamada (lazy init)
_qdrant_client = None
_embedder = None


def _get_client():
    global _qdrant_client
    if _qdrant_client is None:
        from rag.indexer import get_qdrant_client
        _qdrant_client = get_qdrant_client()
    return _qdrant_client


def _get_embedder():
    global _embedder
    if _embedder is None:
        from rag.embedder import get_embedder
        _embedder = get_embedder()
    return _embedder


def _build_qdrant_filter(filters: dict):
    """
    Construye un filtro Qdrant a partir del dict de metadata.
    Ejemplo: {"nivel": "primaria", "area": "matemática"} →
        Filter(must=[MatchValue(nivel=primaria), MatchValue(area=matemática)])
    Solo incluye campos con valores no vacíos.
    """
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    conditions = []
    for field in ("nivel", "area", "grado", "ciclo", "competencia", "tipo"):
        value = filters.get(field, "").strip() if filters else ""
        if value:
            conditions.append(
                FieldCondition(key=field, match=MatchValue(value=value))
            )

    return Filter(must=conditions) if conditions else None


def _deduplicate(results: list[dict], min_similarity: float = 0.92) -> list[dict]:
    """
    Elimina resultados cuyo texto es casi idéntico (similitud de caracteres > min_similarity).
    Implementación simple sin dependencias externas.
    """
    unique = []
    for r in results:
        text = r["text"]
        is_dup = False
        for u in unique:
            # Ratio de similitud por intersección de conjuntos de palabras
            words_a = set(text.lower().split())
            words_b = set(u["text"].lower().split())
            if not words_a or not words_b:
                continue
            intersection = len(words_a & words_b)
            union = len(words_a | words_b)
            if union > 0 and intersection / union > min_similarity:
                is_dup = True
                break
        if not is_dup:
            unique.append(r)
    return unique


def search(
    query: str,
    filters: Optional[dict] = None,
    top_k: int = 5,
    collection_name: str = "curriculum_documents",
) -> list[str]:
    """
    Busca los fragmentos del Currículo Nacional más relevantes para la consulta.

    Args:
        query: Texto de la consulta del docente (ej: "fracciones cuarto primaria").
        filters: Dict con filtros de metadata opcionales.
                 Claves soportadas: nivel, area, grado, ciclo, competencia, tipo.
                 Ejemplo: {"nivel": "primaria", "area": "matemática", "grado": "cuarto"}
        top_k: Número de resultados a recuperar.
        collection_name: Nombre de la colección en Qdrant.

    Returns:
        Lista de strings con el texto de los chunks recuperados,
        listos para insertar en el prompt de Gemini.
        Retorna lista vacía si Qdrant no está disponible o hay un error.
    """
    if not query.strip():
        return []

    try:
        client = _get_client()
        embedder = _get_embedder()

        # Verificar que la colección existe
        existing = [c.name for c in client.get_collections().collections]
        if collection_name not in existing:
            logger.warning(
                "Colección '%s' no encontrada en Qdrant. "
                "Ejecuta 'python scripts/index_documents.py' para indexar los PDFs.",
                collection_name
            )
            return []

        # Generar embedding de la consulta
        query_vector = embedder.embed_query(query)

        # Construir filtro de payload
        qdrant_filter = _build_qdrant_filter(filters or {})

        # Buscar en Qdrant (soporta qdrant-client v1.16+)
        if hasattr(client, "query_points"):
            response = client.query_points(
                collection_name=collection_name,
                query=query_vector,
                query_filter=qdrant_filter,
                limit=top_k * 2,
                with_payload=True,
                score_threshold=0.35,
            )
            search_results = getattr(response, "points", response)
        elif hasattr(client, "search"):
            search_results = client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                query_filter=qdrant_filter,
                limit=top_k * 2,
                with_payload=True,
                score_threshold=0.35,
            )
        else:
            search_results = []

        if not search_results:
            logger.info("Sin resultados para query='%s' filters=%s", query, filters)
            return []

        # Formatear resultados
        raw = [
            {
                "text": r.payload.get("text", ""),
                "score": r.score,
                "nivel": r.payload.get("nivel", ""),
                "area": r.payload.get("area", ""),
            }
            for r in search_results
            if r.payload.get("text")
        ]

        # Deduplicar y limitar a top_k
        unique_results = _deduplicate(raw)[:top_k]

        logger.info(
            "Recuperados %d chunks para query='%s' (filtros=%s)",
            len(unique_results), query[:60], filters
        )

        return [r["text"] for r in unique_results]

    except Exception as e:
        logger.exception("Error en retriever.search: %s", e)
        return []
