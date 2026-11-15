# Prueba de aceptación del demostrador: baseline / científico, sin Gold

`scripts/ci/smoke_tesis.py` comprueba el servicio desde fuera por HTTP y
genera un reporte sin texto, etiquetas humanas ni Gold.

## Dos niveles separados

### 1. Baseline: reproducible en CI sin pesos científicos

```bash
uv run tablero
# Otra terminal:
uv run python scripts/ci/smoke_tesis.py \
  --salida artifacts/qa_tesis/aceptacion_local.json
```

Debe obtener salud real `/api/estado`, al menos una recomendación de
`/api/recomendar` identificada como `tfidf_reranker_v1` y al menos un
fragmento del baseline `BM25_lexico_baseline`. Los tres checks se hacen por
HTTP contra la API de verdad, no contra fixtures. Esto **no significa** que el
demostrador de tesis completo esté validado.

### 2. Científico: requiere modelos auténticos recuperados y activos

Primero integrar PR #173 (SciBERT), #175 (clasificador SciBERT-A) y #169
(capacidades); recuperar los snapshots y checkpoint `model.safetensors`
y habilitar sus respectivas variables en un entorno con Torch.

```bash
uv run python scripts/ci/smoke_tesis.py --cientifico \
  --salida artifacts/qa_tesis/aceptacion_cientifica_001.json
```

Además del baseline, la opción `--cientifico` verifica:
- `/api/capacidades` declara **realmente cargados** SciBERT y A4;
- `/api/top3-scibert` devuelve `scibert_base_mean_pooling_cosine`,
  fragmentos y revisión coherente con el modelo cargado;
- `/api/clasificar-cita` devuelve nueve scores, modelo A4 coincidente,
  `training_labels=Haiku` y `validacion=provisional_no_gold_humano`.

Si falta cualquiera de esos requisitos, **falla**, sin usar BM25 como si fuera
SciBERT ni inventar funciones de cita. El caso de entrada es ilustrativo y
público dentro del script; no se consulta ni puntúa Test Gold.

El reporte incluye momento UTC, modelos, revisiones, conteos y estado
`gold_certificado=false`. Se crea con modo exclusivo `x` para no sobrescribir
evidencia previa. No imprime ni conserva los textos de entrada, etiquetas
humanas, credenciales o predicciones de prueba.

## Despliegue externo

Para ensayar una URL HTTPS realmente desplegada:
```bash
uv run python scripts/ci/smoke_tesis.py \
  --url https://URL_API_APROBADA --permitir-remoto \
  --salida artifacts/qa_tesis/aceptacion_https_001.json
```
Esto hace peticiones reales a la URL. Debe autorizarse el acceso y el eventual
consumo AWS antes de ejecutarse. La prueba no ejecuta `terraform apply`,
no modifica servicios ni utiliza claves API.

## Límite de la evidencia

- Pasar el baseline no significa que SciBERT/A4 estén instalados.
- Pasar el científico verifica integración de **inferencia provisional**
  y trazabilidad, no F1, Recall@3 ni acuerdo humano.
- No mide latencia p95, concurrencia ni seguridad del despliegue externo.
  Para latencias está el benchmark separado PR #174.
- La CI ejecuta automáticamente solo el baseline real (sin Torch, sin Gold);
  el científico debe ejecutarse explícitamente una vez restaurados los pesos.
