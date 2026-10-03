# Imagen base oficial de Python compatible con el proyecto (Python >=3.10)
FROM python:3.11-slim

# Evitar escritura de archivos .pyc y forzar salida stdout/stderr sin buffer
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Instalar dependencias del sistema mínimas requeridas y curl para healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Crear un usuario no privilegiado para ejecutar la aplicación
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -m -s /bin/bash appuser

WORKDIR /app

# Aprovechar la caché de capas de Docker copiando únicamente las dependencias primero
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar únicamente el código y recursos necesarios para la ejecución
COPY app.py .
COPY pyproject.toml .
COPY README.md .
COPY homelens/ ./homelens/

# Ajustar permisos para el usuario sin privilegios
RUN chown -R appuser:appuser /app

# Cambiar al usuario no privilegiado
USER appuser

# Exponer el puerto por defecto de Streamlit
EXPOSE 8501

# Verificación de estado del contenedor
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Comando de inicio de Streamlit (manteniendo protecciones de Streamlit habilitadas)
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
