FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_LINK_MODE=copy

WORKDIR /app

# Instalar uv dentro de la imagen
RUN pip install --no-cache-dir uv

# Copiar primero los archivos necesarios para resolver dependencias
COPY pyproject.toml uv.lock README.md ./

# El modelo llega como wheel publicado en S3, con el .pkl dentro y el hash
# fijado en uv.lock. La imagen no necesita model-package/, ni el dataset, ni
# las dependencias de entrenamiento: solo descargar e instalar el paquete.
RUN uv sync --frozen --no-dev --no-install-project

# Copiar el código y los archivos de configuración del proyecto
COPY . .

# Instalar el proyecto completo
RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
