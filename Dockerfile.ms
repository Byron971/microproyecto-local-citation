# Dedicated M/S CPU service. Models arrive via the ECS task role at startup.
FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
    PYTHONPATH=/app:/app/packages/recuperacion-densa/src \
    OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
WORKDIR /app
COPY requirements/science.txt /app/requirements/science.txt
RUN pip install --no-cache-dir torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements/science.txt
# Freeze transitive dependencies to the validated Linux environment.
COPY requirements/science-constraints.txt /app/requirements/science-constraints.txt
RUN pip install --no-cache-dir -r requirements/science-constraints.txt && pip check
# Explicit allowlist: no local datasets, weights, archives or credentials.
COPY src/app/__init__.py src/app/ms_config.py src/app/ms_runtime.py src/app/ms_router.py src/app/scibert_runtime.py src/app/science_main.py /app/src/app/
COPY packages/recuperacion-densa/src/recuperacion_densa /app/packages/recuperacion-densa/src/recuperacion_densa
COPY proyecto_de_grado/docs/evidencias_recuperacion_densa_a1/manifiesto_modelo.json /app/proyecto_de_grado/docs/evidencias_recuperacion_densa_a1/manifiesto_modelo.json
COPY config/ms_release.json /app/config/ms_release.json
COPY config/catalog_search_release.json /app/config/catalog_search_release.json
COPY config/corpus_ms.json /app/config/corpus_ms.json
COPY config/prepared_article_search /app/config/prepared_article_search
COPY src/app/article_corpus.py /app/src/app/article_corpus.py
COPY src/app/scientific_search.py src/app/ms_lock.py /app/src/app/
# Experimental search artifacts are supplied separately when explicitly enabled.
COPY scripts/iniciar_ciencia.py /app/scripts/iniciar_ciencia.py
RUN groupadd -g 10001 modelrunner && useradd -u 10001 -g modelrunner modelrunner \
    && mkdir /models && chown 10001:10001 /models
ARG MS_CODE_SHA=unknown
ENV MS_CODE_SHA=${MS_CODE_SHA}
LABEL org.opencontainers.image.revision=${MS_CODE_SHA}
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --start-period=300s --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/ready', timeout=4)"
CMD ["python", "/app/scripts/iniciar_ciencia.py"]
