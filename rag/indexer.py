"""
rag/indexer.py

Indexación de chunks en Qdrant.
Colección: curriculum_documents
Configuración: HNSW + Cosine Similarity + Payload Indexes para filtros.
"""
import logging
import os
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

logger = logging.getLogger(__name__)

COLLECTION_NAME = "curriculum_documents"
VECTOR_SIZE = 1024  # Dimensión de voyage-3

# Campos sobre los que se crearán índices de payload para filtros rápidos
PAYLOAD_INDEX_FIELDS = ["nivel", "area", "ciclo", "grado", "competencia", "tipo"]


def get_qdrant_client() -> QdrantClient:
    """
    Retorna el cliente Qdrant según la configuración:
    - QDRANT_URL definida → conecta al servidor (producción EC2)
    - Sin QDRANT_URL → modo en memoria (desarrollo local)
    """
    qdrant_url = os.getenv("QDRANT_URL", "").strip()
    qdrant_api_key = os.getenv("QDRANT_API_KEY", "").strip() or None

    if qdrant_url:
        logger.info("Conectando a Qdrant en %s", qdrant_url)
        return QdrantClient(url=qdrant_url, api_key=qdrant_api_key, timeout=120)
    else:
        logger.warning("QDRANT_URL no definida. Usando Qdrant en memoria (solo desarrollo).")
        return QdrantClient(":memory:")


def ensure_collection(client: QdrantClient, vector_size: int = VECTOR_SIZE):
    """
    Crea la colección curriculum_documents si no existe.
    Configura HNSW con Cosine Similarity y Payload Indexes para filtros.
    """
    existing = [c.name for c in client.get_collections().collections]

    if COLLECTION_NAME not in existing:
        logger.info("Creando colección '%s' en Qdrant...", COLLECTION_NAME)
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE,
            ),
        )
        # Crear índices de payload para búsqueda filtrada rápida
        for field in PAYLOAD_INDEX_FIELDS:
            client.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name=field,
                field_schema=PayloadSchemaType.KEYWORD,
            )
        logger.info("Colección '%s' creada con %d índices de payload.", COLLECTION_NAME, len(PAYLOAD_INDEX_FIELDS))
    else:
        logger.info("Colección '%s' ya existe en Qdrant.", COLLECTION_NAME)


def index_chunks(
    client: QdrantClient,
    chunks: list[dict],
    embeddings: list[list[float]],
    batch_size: int = 100,
):
    """
    Sube chunks con sus embeddings y metadata a Qdrant en batches.

    Args:
        client: Cliente Qdrant.
        chunks: Lista de dicts con 'id', 'text', 'metadata'.
        embeddings: Lista de vectores (misma longitud que chunks).
        batch_size: Tamaño del lote para la carga.
    """
    if len(chunks) != len(embeddings):
        raise ValueError(
            f"Número de chunks ({len(chunks)}) != número de embeddings ({len(embeddings)})"
        )

    points = []
    for chunk, vector in zip(chunks, embeddings):
        payload = dict(chunk["metadata"])
        payload["text"] = chunk["text"]  # Almacenar texto original para recuperación
        points.append(
            PointStruct(
                id=chunk["id"],
                vector=vector,
                payload=payload,
            )
        )

    total = len(points)
    for i in range(0, total, batch_size):
        batch = points[i:i + batch_size]
        client.upsert(collection_name=COLLECTION_NAME, points=batch)
        logger.info(
            "Indexados %d/%d chunks en Qdrant",
            min(i + batch_size, total), total
        )

    logger.info("Indexación completa: %d puntos en '%s'.", total, COLLECTION_NAME)
