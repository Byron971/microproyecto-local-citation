FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_LINK_MODE=copy

WORKDIR /app

# Instalar uv dentro de la imagen
RUN pip install --no-cache-dir uv

# Copiar primero los archivos necesarios para resolver dependencias
COPY pyproject.toml uv.lock README.md ./
COPY model-package ./model-package

# El artefacto se entrena antes de construir la imagen (uv run tox -c
# model-package -e train), no dentro del build: la imagen instala el paquete
# ya entrenado y no necesita ni el dataset ni las dependencias de entrenamiento.
RUN test -f model-package/modelo_citas/trained/*.pkl || (echo "Falta el artefacto: ejecute tox -c model-package -e train" && exit 1)

# Instalar dependencias antes de copiar el resto del c�digo
RUN uv sync --frozen --no-dev --no-install-project

# Copiar el c�digo y los archivos de configuraci�n del proyecto
COPY . .

# Instalar el proyecto completo
RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8000"]

