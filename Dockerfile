# Usar imagen base de Python
FROM python:3.11-slim

# Establecer directorio de trabajo
WORKDIR /app

# Crear un usuario no privilegiado para ejecutar la aplicación de forma segura
RUN groupadd -g 10001 appuser && \
    useradd -u 10000 -g appuser -m -s /bin/bash appuser

# Copiar archivos de requisitos
COPY requirements.txt .

# Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copiar de forma explícita los archivos de la aplicación para evitar COPY . .
COPY config.py database.py knowledge.py main.py prompts.py schemas.py services.py utils.py ./

# Crear directorio para la base de datos SQLite y ajustar permisos
RUN mkdir -p /app/data && chown -R appuser:appuser /app

# Exponer el puerto 7700
EXPOSE 7700

# Variable de entorno para la API key de Google
ENV GOOGLE_API_KEY=""

# Cambiar al usuario no privilegiado
USER appuser

# Comando para ejecutar la aplicación
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7700"]
