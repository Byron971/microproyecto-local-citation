# John — Issue #116: Integración y evidencia de despliegue

Fecha: 4 de noviembre de 2026. Estado: **primer incremento funcional de entrega**, distinto de la solución científica completa.

## 1. Alcance real

Este incremento integra tres partes que **ya tienen implementación verificable**:

1. **Recomendación de artículos** con el wheel `modelo-citas` 0.2.0 (TF-IDF + reordenador lineal).
2. **Recuperación local Top-3 de fragmentos** de **un artículo citado**, suministrados por formulario, mediante BM25 léxico. Si existe una muestra ACL-200/ACL OCL TRAIN validada en disco, el botón «Consultar caso real» también puede usarla.
3. **Interfaz Nginx/HTML + FastAPI** con endpoint de capacidades veraz, disponibilidad, límites de cuerpos HTTP y pruebas E2E con contenedores reales.

**No equivale** a lo exigido por la tesis para la clasificación de nueve funciones de cita y Top-3 denso SciBERT. El código SciBERT S2.8 existe en ramas de investigación, pero en esta etapa no está integrado como endpoint de inferencia de la API desplegada. El Test Gold de clasificación y el Gold de chunks dependen de auditoría humana. Los PR #91/#92 son datos/modelos en el repositorio, **no prueba de una API de clasificación final**.

## 2. Rutas y significado

| Ruta | Uso | Criterio de funcionamiento |
|---|---|---|
| `GET /api/salud/viva` | Liveness HTTP | 200 si el proceso responde, incluso sin cargar modelo |
| `GET /api/salud/lista` | Readiness | 200 solo si el modelo real y los insights están cargados; 503 si no |
| `GET /api/estado` | Modelo empaquetado | 200 y `listo=true` tras arranque correcto |
| `GET /api/capacidades` | Inventario de métodos operativos | Reporta BM25 y TF-IDF; SciBERT y 9 funciones **no desplegados** |
| `POST /api/recomendar` | Ranking de artículos | Inferencia del wheel `modelo-citas` |
| `POST /api/top3-fragmentos` | Ranking de fragmentos Top-3 | BM25 de fragmentos suministrados del artículo citado, **no probabilidad** |
| `GET /api/top3-corpus/ejemplos` | Muestra de train ACL OCL | Si falta el artefacto opcional, 503; no inventar casos |
| `/static/top3.html` | Interfaz Nginx para Top-3 | Muestra disponibilidad real leyendo `/api/capacidades` |

## 3. Pasos reproducibles, entorno local

Dependencias:
- Docker Engine + Docker Compose;
- salida a S3 para descargar el wheel público de `modelo-citas`, fijado con hash en `uv.lock`;
- puertos locales 8000 y 8080 disponibles.

```bash
docker compose --env-file config/runtime.env.example config --quiet
docker compose --env-file config/runtime.env.example up --build --wait --wait-timeout 300 -d
python3 scripts/smoke_despliegue.py \
  --api-url http://127.0.0.1:8000 \
  --dashboard-url http://127.0.0.1:8080 \
  --check-ingress-limit \
  --report artifacts/smoke-despliegue-local.json
docker compose --env-file config/runtime.env.example down
```

También funciona en Windows con Python 3.14 o con `uv run python scripts/smoke_despliegue.py`. El smoke usa la biblioteca estándar y NO requiere claves de OpenAI/Gemini/Cohere ni Test Gold.

**Qué prueba realmente el smoke:** salud viva/lista, modelo empaquetado, inferencia de ranking de artículos (sin exigir métricas de recuperación), BM25, 422 ante entrada inválida, HTML/CSS/JS vía Nginx, proxy y 413 ante cuerpo muy grande. Registra latencia observada **en ese entorno**. No calcula F1, Recall@3 ni MRR@3.

El workflow `.github/workflows/despliegue-e2e.yml` construye imágenes, inicia los contenedores, ejecuta el smoke, guarda `artifacts/smoke-despliegue-ci.json` como evidencia descargable en Actions y cierra contenedores incluso cuando algo falle. También recoge un `docker stats` puntual para observación, sin atribuirlo a benchmarks de rendimiento general.

## 4. Seguridad y limitaciones

- Nginx acepta cuerpos de hasta **128 KiB**. FastAPI conserva límites más estrictos de negocio (4000 caracteres de contexto, 100 fragmentos, 5000 caracteres por chunk y 60000 acumulados). La respuesta 413 de Nginx no sustituye validación semántica ni controles de tasa.
- El proxy establece tiempos de conexión, envío y lectura, y no almacena en caché respuestas de API.
- Docker Compose expone por defecto 8000 y 8080 **solo en localhost** heredado del PR #130. Por eso el smoke de CI comprueba HTTP dentro del runner, no disponibilidad a través de una URL pública de Internet.
- Los corpus y pesos de investigación no se copian automáticamente a imágenes de producción. No subir Gold, contraseñas ni cuadernos con secretos.
- `APP_ENV=production` es una etiqueta, **no** activa autenticación, HTTPS, balanceador ni seguridad. Para permitir acceso externo usar TLS, una puerta de entrada segura, restricción de acceso y monitoreo.
- El ejemplo del smoke es sintético y **se usa únicamente para comprobar funcionamiento técnico**, nunca para reportar resultados del artículo.

## 5. Plataforma y ruta hacia la demostración universitaria

**Ola 1 (este PR):** usar Docker Compose en una máquina con CPU, memoria suficiente y salida HTTPS de descarga del wheel. La API base conserva dependencia del paquete `modelo-citas` y de la precarga de insights; registrar salud, latencia real y memoria de contenedores.

**Ola 2 (dependencia de Carlos Duque, #102/#103):** integrar SciBERT como recuperador de fragmentos realmente cargable desde pesos versionados; ejecutar pruebas de consumo y latencia antes de decidir CPU o GPU. No sustituir BM25 sin medición.

**Ola 3 (clasificación 9 funciones):** servir un modelo aprobado con nueve etiquetas canónicas y un manifiesto versionado; definir fallback explícito `no_disponible` y no confundir puntuaciones no calibradas con probabilidades. Validación del Gold (#100, #109/#110) independiente de disponibilidad técnica.

**Ola 4 (URL externa):** publicar en EC2/ECS u otra plataforma seleccionada con DNS y HTTPS, control de acceso, métricas de CPU/RAM/latencia, evidencia de disponibilidad desde navegador ajeno y durante el horario de evaluación. Estos pasos **no se consideran realizados** por el CI local.

## 6. Criterios de cierre de #116

- [x] Inventario de endpoints y resultados veraces.
- [x] Código de liveness y readiness, sin lectura de secretos.
- [x] Nginx con límite de cuerpo y timeout de proxy.
- [x] Pruebas automatizadas de rutas + script de E2E.
- [ ] Workflow Docker E2E en verde sobre el **SHA final** del PR (ver Actions).
- [ ] Construcción Docker real con inferencia de artículo comprobada y evidencia adjunta.
- [ ] Componente SciBERT Top-3 integrado y probado (Carlos Duque).
- [ ] Clasificador nueve funciones integrado y probado (equipo).
- [ ] URL externa operativa con HTTPS, recursos y acceso de evaluación.
- [ ] Revisión cruzada y aceptación final por los cinco.

## 7. Rúbrica y evidencias

La rúbrica de **despliegue** asigna 35/100 a funcionamiento, diferente a la rúbrica del artículo final o informe de avance. Un build verde de contenedores es evidencia técnica, pero por sí solo NO justifica 35/35: faltan inferencias finales, rendimiento y acceso externo.

Conservar en issue #116:
- PR y SHA probado, vínculo al workflow;
- artefacto JSON de smoke descargable;
- ID de versión del wheel y logs sin datos sensibles;
- observación de CPU/RAM y tiempos;
- URL externa cuando exista y validación de terceros;
- capturas/reproducción de demo en horario de sustentación.
