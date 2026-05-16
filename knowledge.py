import chromadb
import requests
import re
import time
from google import genai
from google.genai import types
from google.api_core import retry
from config import client, TXT_URL

# ========================
# ChromaDB con currículo escolar
# ========================
class GeminiEmbeddingFunction(chromadb.EmbeddingFunction):
    document_mode = True
    @retry.Retry(predicate=lambda e: isinstance(e, genai.errors.APIError) and e.code in {429,503})
    def __call__(self, input):
        task = "retrieval_document" if self.document_mode else "retrieval_query"
        response = client.models.embed_content(
            model="gemini-embedding-2",
            contents=input,
            config=types.EmbedContentConfig(task_type=task),
        )
        return [e.values for e in response.embeddings]

embed_fn = GeminiEmbeddingFunction()
chroma_client = chromadb.Client()
knowledge_db = chroma_client.get_or_create_collection(
    name="curriculo_secundaria", embedding_function=embed_fn
)

def init_knowledge_base():
    """Descarga e indexa el currículo en ChromaDB si no está ya cargado."""
    try:
        # Se verifica si ya hay documentos para no re-descargar
        if knowledge_db.count() > 0:
            print("Base de conocimientos ya inicializada.")
            return
            
        print("Descargando currículo y cargando en base de conocimientos...")
        response = requests.get(TXT_URL, timeout=30)
        response.raise_for_status()
        
        text = response.text
        chunks = re.split(r'\n{2,}', text)  # separa por párrafos
        docs = [chunk.strip() for chunk in chunks if len(chunk.strip()) > 50]
        
        MAX_BATCH = 100
        ids = [f"frag_{i}" for i in range(len(docs))]
        
        for i in range(0, len(docs), MAX_BATCH):
            batch_docs = docs[i:i+MAX_BATCH]
            batch_ids = ids[i:i+MAX_BATCH]
            try:
                knowledge_db.add(documents=batch_docs, ids=batch_ids)
                print(f"Lote {i//MAX_BATCH + 1} cargado ({len(batch_docs)} fragmentos)")
                time.sleep(1)  # opcional, evita saturar la API
            except Exception as e:
                print(f"Error en el lote {i//MAX_BATCH + 1}: {e}")
    except Exception as e:
        print(f"Error inicializando la base de conocimientos: {e}")

# Inicializar al importar
init_knowledge_base()
