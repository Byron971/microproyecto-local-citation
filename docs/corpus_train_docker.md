# Ejecutar Top-3 con corpus TRAIN auténtico en Docker (sin Gold)

La API existente devuelve `503` en `/api/top3-corpus/ejemplos` si no
encuentra el archivo S2.2. Esto sucede en la imagen normal porque
`.dockerignore` excluye `artifacts/` (correctamente: ningún dato de
investigación debe incrustarse sin control en imágenes públicas).

`docker-compose.top3.yml` proporciona un montaje **opt-in, solo lectura**
del archivo local, sin eliminar las reglas de Docker existentes.

## Preparar el artefacto original en el equipo

A partir de ACL-200 y la caché OCL reales obtenidos siguiendo el pipeline DVC:

```bash
uv run python -m proyecto_de_grado.src.data.exportar_corpus_top3 --limite 5
uv run python -m src.app.corpus_preflight \
  --archivo proyecto_de_grado/artifacts/top3_s2/casos_train.json
```

El preflight exige `version=1`, todos los casos `split=train`, procedencia
`muestra_desarrollo_train_no_gold`, chunks verificables y ausencia de claves
de etiquetas o relevancia; produce únicamente conteos y un SHA-256 del JSON.
**No genera datos sintéticos ni descarga fuentes**. Nunca montar el Gold, los
CSV de anotadores ni el split `test`, incluso para una demo.

## Arrancar Compose sin copiar corpus al contenedor

En Linux/WSL/Bash, desde la raíz:

```bash
export TOP3_CORPUS_HOST_PATH="$(pwd)/proyecto_de_grado/artifacts/top3_s2/casos_train.json"
docker compose -f docker-compose.yml -f docker-compose.top3.yml up --build
```

En Windows PowerShell:

```powershell
$env:TOP3_CORPUS_HOST_PATH = (Resolve-Path "proyecto_de_grado/artifacts/top3_s2/casos_train.json").Path
docker compose -f docker-compose.yml -f docker-compose.top3.yml up --build
```

La ruta de host se monta como
`/app/proyecto_de_grado/artifacts/top3_s2/casos_train.json`, que coincide
con el `TOP3_CORPUS_PATH` por defecto. No se copia al build de Docker ni al
bucket público. Si falta `TOP3_CORPUS_HOST_PATH`, Compose **no inicia**.
La imagen API sigue utilizando TF-IDF/BM25; este cambio no instala SciBERT.

## Smoke de integración funcional

Con la API arrancada:

```bash
curl -fsS http://127.0.0.1:8000/api/top3-corpus/ejemplos
```

Debe mostrar `total > 0` y únicamente identificadores y títulos de TRAIN.
Abrir React local con `npm --prefix frontend run dev` y acceder a
`http://127.0.0.1:5173/fragmentos`. Seleccionar **Cargar casos reales de
desarrollo** y después **Ejecutar Top-3 de desarrollo**. La respuesta es BM25
sobre chunks del citado, **no** una evaluación Gold, ni un ranking SciBERT.

El workflow `Corpus TRAIN de demostracion` valida el montaje y las reglas
con un fixture sintético sin publicar datos reales; **el smoke con OCL real
todavía debe ejecutarse en el equipo que tenga el corpus**.

## Seguridad y trazabilidad

Solo se debe montar un subconjunto de desarrollo autorizado, no información
privada ni documentos protegidos sin derecho de uso. Registrar el SHA-256
mostrado por preflight para demostrar exactamente qué corpus consumió la demo.
No incorporar `casos_train.json` al repositorio, wheel, imagen ni CloudFront.
