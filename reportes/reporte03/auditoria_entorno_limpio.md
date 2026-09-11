# Auditoría de reproducción desde un entorno limpio

**Issue #32** · Ejecutada el 11 de septiembre de 2026 sobre un clon nuevo de `main` (`7c63a0f`), en Windows 11, **sin credenciales de AWS**.

El objetivo no fue comprobar que el código está, sino que **alguien ajeno al equipo puede reproducirlo**: se clonó, instaló, descargó datos, entrenó, levantó la API y se pidió una recomendación real, anotando cada comando y su duración.

## Resultado por criterio

| Criterio | Estado | Evidencia |
|---|---|---|
| Clon limpio de `main` | ✅ | `7c63a0f`, 142 archivos rastreados |
| Dependencias sin pasos manuales ocultos | ✅ | `uv sync` en 30 s |
| `dvc pull` recupera los datos | ✅ | 11 archivos, 117,6 MB, **sin credenciales** |
| Suite de pruebas completa | ✅ | 96 aprobadas en 113 s |
| Paquete del modelo instalable | ✅ | `uv pip install -e model-package` |
| Paquete probado | ⚠️ | Instala, pero **requiere entrenar y un paso extra no documentado** |
| API y tablero levantan | ✅ | API en 6 s; `GET /` responde 200 |
| Flujo contexto → API → ranking | ✅ | Paquete y API devuelven rankings idénticos |
| Docker/Compose construye desde cero | ✅ | Dos imágenes construidas en 287 s; API `healthy` en 10 s |
| Flujo completo dentro de contenedores | ✅ | `auditoria_docker_tablero.png` |
| Sin secretos ni temporales versionados | ✅ | Cero coincidencias de `.pem`, `.key`, `credentials`, `.joblib`, `mlflow.db` |

**Los diez criterios se cumplen.**

## Tiempos medidos

| Paso | Duración |
|---|---:|
| `uv sync` | 30 s |
| `uv run dvc pull` | 41 s |
| `uv run pytest` (96 pruebas) | 113 s |
| `train_pipeline` → artefacto de 49.308.404 bytes | 76 s |
| `uv sync --reinstall-package modelo-citas` | 3 s |
| Arranque de la API hasta responder | 6 s |

Una instalación completa desde cero, sin contenedores, toma **unos 4,5 minutos** de cómputo.

---

## Hallazgos

### 1. Falta un paso indispensable en la documentación (corregido)

El paquete viaja sin modelo entrenado: `modelo_citas/trained/` solo contiene `__init__.py`. Hay que generarlo con `train_pipeline`, pero **eso no basta**: el entrenamiento escribe el artefacto en el árbol de fuentes mientras que `modelo_citas.predict` lo busca dentro del entorno virtual.

Un `uv sync` normal no lo resuelve: detecta que el paquete no cambió de versión y no lo vuelve a copiar. El síntoma aparece después, al pedir una predicción:

```
FileNotFoundError: No se encontró el modelo entrenado en
.venv/Lib/site-packages/modelo_citas/trained/modelo-citas-output0.1.0.pkl
```

El comando que faltaba es `uv sync --reinstall-package modelo-citas`. Sin él, **quien clone el repositorio no puede levantar la API**. Ya está documentado en `docs/manual_instalacion.md`.

El `Dockerfile` no sufre el problema porque reconstruye el entorno tras entrenar (línea 31).

### 2. Las pruebas del paquete no ejercitan una predicción real

`model-package/tests` pasa 7 pruebas **en 0,12 s**. Ese tiempo es incompatible con cargar un artefacto de 49 MB, de modo que ninguna prueba recorre el camino que falla en la práctica. Por eso el defecto anterior no se detectó antes.

### 3. El despliegue depende del remoto público de DVC

El `Dockerfile` ejecuta `dvc pull -r publico` durante el build. Ese remoto es un bucket S3 en una cuenta de AWS Academy que **se desactiva al terminar el curso**: a partir de entonces el build fallará. Conviene dejarlo dicho en el reporte final.

### 4. El modelo desplegado es la versión 1

`model-package/modelo_citas/processing/features.py` mantiene **su propia copia** del extractor, con las cinco características originales. Las diez características de la versión 2 (PR #37) viven en `src/features/pair_features.py` y **no llegan al paquete**.

Comprobado en la API en ejecución: `/api/estado` informa los coeficientes del modelo cargado, y `similarity_title = 1.5384` coincide exactamente con el de la versión 1 entrenada con negativos aleatorios.

Si el reporte final presenta la versión 2 como modelo seleccionado (Recall@10 = 0,3793) mientras el tablero desplegado responde con la versión 1 (0,2882), la incoherencia es visible abriendo cualquiera de los dos. **Es el hueco de integración más importante que queda.**

---

## Verificación cualitativa

Para el contexto *«we use neural machine translation with attention mechanisms»*, la primera recomendación es **`D15-1166` — «Effective Approaches to Attention-based Neural Machine Translation»**, que es precisamente el artículo canónico del tema.

Las cinco primeras posiciones coinciden exactamente entre la llamada directa al paquete y la respuesta de `/api/recomendar`, lo que confirma que la API no introduce ninguna transformación propia sobre el ranking del modelo.

## Despliegue con contenedores

`docker compose build` construyó las dos imágenes desde cero en **287 s**, sin intervención manual. El `Dockerfile` resuelve por su cuenta lo que en la instalación local exige pasos extra: ejecuta `dvc pull -r publico`, entrena el modelo y reconstruye el entorno para que el artefacto quede dentro del paquete instalado.

| Contenedor | Estado | Puerto |
|---|---|---|
| `microproyecto-citas-api` | `healthy` a los 10 s | 8000 |
| `microproyecto-citas-dashboard` | activo | 8080 |

Verificado a través de Nginx, que es el camino del usuario real:

- `GET http://localhost:8080/` → 200, con el tablero completo
- `GET /api/estado` → `"TF-IDF + reordenador lineal"`, entrenado durante el build
- `POST /api/recomendar` → mismo ranking que la ejecución local y que la llamada directa al paquete

`auditoria_docker_tablero.png` muestra el tablero servido por los contenedores, con la consulta escrita y **«Effective Approaches to Attention-based Neural Machine Translation»** en la primera posición.

### Nota sobre el entorno del auditor

El primer intento no pudo completarse porque el motor de Docker de la máquina no arrancaba: la distribución `docker-desktop` de WSL fallaba con `0xc00000fd` durante su arranque interno. Se descartaron por separado los procesos duplicados, la distribución de sistema y el disco de datos; la causa estaba en la instalación de Docker Desktop, y se resolvió reinstalándola. **Era un problema del equipo del auditor, no del entregable.**

## Nota sobre un error de esta auditoría

Durante la ejecución se concluyó de forma equivocada que la API servía la línea base en lugar del reordenador. La causa fue un servidor de una sesión anterior que seguía ocupando el puerto elegido: `uvicorn` no pudo enlazarlo, el registro lo dijo (`[Errno 10048]`) y las consultas fueron a parar al proceso viejo. Queda anotado porque es un modo de error fácil de repetir: **conviene leer el registro de arranque antes de dar por válida cualquier medición contra un servicio local**.
