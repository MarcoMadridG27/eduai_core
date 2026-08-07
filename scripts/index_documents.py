"""
scripts/index_documents.py

Script de indexación offline del Currículo Nacional del MINEDU.
Ejecutar UNA SOLA VEZ (o cuando se añadan PDFs nuevos):

    python scripts/index_documents.py

Pipeline:
  1. Lee todos los PDFs de la carpeta `pdfs/`
  2. Extrae texto con Docling
  3. Limpia el texto
  4. Genera chunks semánticos (500-800 tokens)
  5. Genera embeddings con Voyage AI
  6. Indexa en Qdrant (colección curriculum_documents)

Variables de entorno requeridas:
  VOYAGE_API_KEY   → API key de Voyage AI
  QDRANT_URL       → URL del servidor Qdrant (default: http://localhost:6333)
"""
import logging
import os
import sys
import time
from pathlib import Path

# Asegurar que el directorio raíz de la app esté en el path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("index_documents")


def find_pdfs(root: Path) -> list[Path]:
    """Encuentra todos los PDFs en la carpeta raíz de forma recursiva."""
    pdfs = list(root.rglob("*.pdf"))
    logger.info("Encontrados %d PDFs en '%s'", len(pdfs), root)
    return sorted(pdfs)


def main():
    # Carpeta de PDFs (relativa al directorio del proyecto)
    project_root = Path(__file__).parent.parent
    pdf_root = project_root / "pdfs"

    if not pdf_root.exists():
        logger.error("Carpeta 'pdfs/' no encontrada en %s", project_root)
        sys.exit(1)

    pdfs = find_pdfs(pdf_root)
    if not pdfs:
        logger.error("No se encontraron PDFs en %s", pdf_root)
        sys.exit(1)

    # Inicializar componentes
    from rag.embedder import get_embedder
    from rag.indexer import ensure_collection, get_qdrant_client, index_chunks
    from rag.extractor import extract_pdf
    from rag.cleaner import clean_text
    from rag.chunker import chunk_document

    logger.info("Inicializando Qdrant y embedder...")
    qdrant_client = get_qdrant_client()
    embedder = get_embedder()

    # Detectar tamaño del vector desde el embedder
    test_vector = embedder.embed_query("test")
    vector_size = len(test_vector)
    logger.info("Tamaño del vector de embeddings: %d", vector_size)

    ensure_collection(qdrant_client, vector_size=vector_size)

    # Estadísticas globales
    total_chunks = 0
    total_pdfs_ok = 0
    total_pdfs_fail = 0
    start_time = time.time()

    for pdf_path in pdfs:
        logger.info("=" * 60)
        logger.info("Procesando: %s", pdf_path.name)

        # 1. Extracción
        extracted = extract_pdf(pdf_path)
        if not extracted:
            logger.warning("Omitido (error de extracción): %s", pdf_path.name)
            total_pdfs_fail += 1
            continue

        raw_text = extracted["text"]
        base_metadata = extracted["metadata"]
        logger.info("  → %d páginas extraídas", extracted["num_pages"])

        # 2. Limpieza
        clean = clean_text(raw_text)
        logger.info("  → Texto limpio: %d caracteres", len(clean))

        # 3. Chunking semántico
        chunks = chunk_document(clean, base_metadata)
        logger.info("  → %d chunks generados", len(chunks))

        if not chunks:
            logger.warning("  → Sin chunks. Omitido.")
            total_pdfs_fail += 1
            continue

        # 4. Embeddings
        logger.info("  → Generando embeddings con Voyage AI...")
        texts = [c["text"] for c in chunks]
        try:
            embeddings = embedder.embed_documents(texts)
        except Exception as e:
            logger.exception("  → Error generando embeddings: %s", e)
            total_pdfs_fail += 1
            continue

        # 5. Indexación en Qdrant
        logger.info("  → Indexando en Qdrant...")
        try:
            index_chunks(qdrant_client, chunks, embeddings)
            total_chunks += len(chunks)
            total_pdfs_ok += 1
        except Exception as e:
            logger.exception("  → Error indexando: %s", e)
            total_pdfs_fail += 1

    # Resumen final
    elapsed = time.time() - start_time
    logger.info("=" * 60)
    logger.info("INDEXACIÓN COMPLETADA en %.1f segundos", elapsed)
    logger.info("  PDFs procesados exitosamente: %d", total_pdfs_ok)
    logger.info("  PDFs con errores:             %d", total_pdfs_fail)
    logger.info("  Total chunks en Qdrant:       %d", total_chunks)

    # Verificar colección final
    try:
        info = qdrant_client.get_collection("curriculum_documents")
        logger.info(
            "  Puntos en Qdrant:             %d",
            info.points_count
        )
    except Exception:
        pass


if __name__ == "__main__":
    main()
