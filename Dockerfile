# Usar imagen base de Python
FROM python:3.11-slim

# Establecer directorio de trabajo
WORKDIR /app

# Crear un usuario no privilegiado para ejecutar la aplicación de forma segura
RUN groupadd -g 10001 appuser && \
    useradd -u 10000 -g appuser -m -s /bin/bash appuser

# Copiar archivos de requisitos primero (cache de capas Docker)
COPY requirements.txt .

# Instalar dependencias del sistema necesarias para Docling
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar módulos de la aplicación
COPY config.py database.py main.py prompts.py schemas.py services.py utils.py ./
COPY rag/ ./rag/
COPY scripts/ ./scripts/

# Copiar webhook si existe
COPY webhook.py ./webhook.py 2>/dev/null || true

# Crear directorios necesarios
RUN mkdir -p /app/data && chown -R appuser:appuser /app

# Exponer el puerto 7700
EXPOSE 7700

# Variables de entorno (valores vacíos por defecto; se pasan en docker-compose)
ENV GOOGLE_API_KEY="" \
    VOYAGE_API_KEY="" \
    QDRANT_URL="" \
    QDRANT_API_KEY="" \
    LANGFUSE_SECRET_KEY="" \
    LANGFUSE_PUBLIC_KEY="" \
    LANGFUSE_HOST="https://cloud.langfuse.com"

# Cambiar al usuario no privilegiado
USER appuser

# Comando para ejecutar la aplicación
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7700"]
