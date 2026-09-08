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

# Instalar dependencias antes de copiar el resto del código
RUN uv sync --frozen --no-dev --no-install-project

# Copiar el código y los archivos de configuración del proyecto
COPY . .

# Instalar el proyecto completo
RUN uv sync --frozen --no-dev

# Recuperar los datos versionados desde el remoto público de DVC
RUN uv run dvc config core.no_scm true
RUN uv run dvc pull -r publico

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8000"]

