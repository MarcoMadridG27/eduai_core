"""
rag/embedder.py

Interfaz de embeddings swappable.
Implementación por defecto: Voyage AI (voyage-3, recomendado para RAG).

Para cambiar de proveedor (OpenAI, Gemini, Nomic, BAAI):
→ Crear una nueva clase que herede de EmbedderBase e implementar
  embed_documents() y embed_query().
→ Cambiar la variable `default_embedder` al final del archivo.
"""
import logging
import os
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)


class EmbedderBase(ABC):
    """Interfaz abstracta para cualquier proveedor de embeddings."""

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Genera embeddings para indexación (modo document)."""
        ...

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """Genera un embedding para una consulta (modo query)."""
        ...


class VoyageEmbedder(EmbedderBase):
    """
    Embedder usando Voyage AI.
    Modelo: voyage-3 (optimizado para RAG multilenguaje, incluye español).
    API Key: VOYAGE_API_KEY en .env
    """
    MODEL = "voyage-3"
    BATCH_SIZE = 128  # Límite de la API de Voyage AI

    def __init__(self, api_key: Optional[str] = None):
        import voyageai
        self._api_key = api_key or os.getenv("VOYAGE_API_KEY")
        if not self._api_key:
            raise ValueError(
                "VOYAGE_API_KEY no configurada. Agrégala en el archivo .env"
            )
        self._client = voyageai.Client(api_key=self._api_key)
        logger.info("VoyageEmbedder inicializado con modelo %s", self.MODEL)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """
        Genera embeddings en modo 'document' para indexación.
        Procesa en batches de BATCH_SIZE para respetar límites de la API.
        """
        all_embeddings = []
        for i in range(0, len(texts), self.BATCH_SIZE):
            batch = texts[i:i + self.BATCH_SIZE]
            result = self._client.embed(
                batch,
                model=self.MODEL,
                input_type="document",
            )
            all_embeddings.extend(result.embeddings)
            logger.debug("Embeddings generados para lote %d-%d", i, i + len(batch))
        return all_embeddings

    def embed_query(self, text: str) -> list[float]:
        """Genera un embedding en modo 'query' para búsqueda semántica."""
        result = self._client.embed(
            [text],
            model=self.MODEL,
            input_type="query",
        )
        return result.embeddings[0]


class GeminiEmbedder(EmbedderBase):
    """
    Alternativa: Embedder usando Google Gemini Embedding.
    Para activar: cambiar default_embedder = GeminiEmbedder()
    """
    MODEL = "gemini-embedding-2"

    def __init__(self, api_key: Optional[str] = None):
        import os
        from google import genai
        from google.genai import types as gtypes
        self._gtypes = gtypes
        _key = api_key or os.getenv("GOOGLE_API_KEY")
        self._client = genai.Client(api_key=_key)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        response = self._client.models.embed_content(
            model=self.MODEL,
            contents=texts,
            config=self._gtypes.EmbedContentConfig(task_type="retrieval_document"),
        )
        return [e.values for e in response.embeddings]

    def embed_query(self, text: str) -> list[float]:
        response = self._client.models.embed_content(
            model=self.MODEL,
            contents=[text],
            config=self._gtypes.EmbedContentConfig(task_type="retrieval_query"),
        )
        return response.embeddings[0].values


def get_embedder() -> EmbedderBase:
    """
    Retorna el embedder activo según la configuración del entorno.
    Prioridad: VOYAGE_API_KEY → VoyageEmbedder (default)
               VOYAGE_API_KEY ausente → GeminiEmbedder (fallback)
    """
    if os.getenv("VOYAGE_API_KEY"):
        return VoyageEmbedder()
    logger.warning("VOYAGE_API_KEY no encontrada. Usando GeminiEmbedder como fallback.")
    return GeminiEmbedder()
