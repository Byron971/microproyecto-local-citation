# Seguimiento de integración científica y despliegue M/S

Actualizado: 21 de noviembre de 2026.

Responsable de coordinación: José María. Responsables adicionales y fechas: por acordar.

## Objetivo y alcance acordado

Adaptar la aplicación pública para recomendar artículos y permitir analizar, bajo demanda, los fragmentos relevantes y la función de cita de cada resultado con texto disponible.

Flujo objetivo: **texto del usuario → artículos recomendados → seleccionar un artículo → Top-3 de fragmentos → predicciones M y S**.

Se realizarán dos entregas:

1. Publicar y verificar la pantalla científica existente con SciBERT y los pesos M/S reales.
2. Integrar ese análisis en el flujo de recomendaciones, obteniendo los fragmentos automáticamente.

M/S clasifican nueve funciones de cita; no reemplazan al recomendador de artículos TF-IDF + reordenador 0.2.0. Integrar ambas tareas no implica que el flujo completo esté científicamente evaluado. El Top-3 indica similitud, no respaldo comprobado de una afirmación; la clase Evidence tampoco certifica la validez de una cita.

## Estado inicial y evidencia

| Elemento | Estado comprobado o fuente | Pendiente |
| --- | --- | --- |
| SPA objetivo | https://proyectocitas-grupo19.click/ — dirección facilitada por José | Verificar comportamiento público actual |
| API objetivo | https://api.proyectocitas-grupo19.click — dirección facilitada por José | Verificar versión efectiva y capacidades |
| Pesos M/S | Extraídos de `tmp/experimentos_10.zip` a `proyecto_de_grado/artifacts/experimentos_10/{M,S}/` | Cargar y ejecutar localmente |
| Integridad M/S | `python scripts/verificar_artefactos_ms.py` devolvió `listo: true`: tamaños, SHA-256 y manifiestos válidos para ambos | Repetir control en artefactos distribuidos y contenedor |
| SciBERT base | Revisión exigida: `24f92d32b1bfb0bcaf9ab193ff3ad01e87732fc1` | Comprobar caché local e instalar si falta |
| Inferencia científica | Existe `src/app/ms_runtime.py` y POST `/api/analisis-cita-ms` | Reproducir aquí; verificar después por HTTPS público |
| Interfaz científica | Existe `/analisis-ms`; requiere candidatos manuales o JSON | Automatizar suministro de contenido por artículo |
| Reproducción del equipo | WhatsApp reporta smoke exitoso desde clon limpio con Python 3.12.10, Torch 2.6.0 CPU y Transformers 5.21.0 | Obtener caso y referencia; reproducir en nuestro entorno |
| Despliegue definido en código | Workflow de API construye `Dockerfile` estándar | Preparar distribución e imagen científica |
| Recursos definidos por defecto | Terraform: 512 unidades CPU y 1024 MiB | Consultar recursos reales y medir necesidades científicas |

La revisión anterior no pudo acceder a los dominios desde el entorno de trabajo. No se concluye que estén caídos ni se certifica qué versión sirven. La integridad de archivos no demuestra inferencia.

## Tablero de tareas

### Prioridad previa — comprobar enrutamiento público

Actualización del equipo, 21 de noviembre, 17:22–18:04 (hora de los mensajes compartidos; zona no confirmada): John confirma inferencia local FastAPI/React y el endpoint POST M/S. José confirma que solo está publicada la aplicación estándar y que los modelos científicos todavía no están desplegados. John reporta 403 de S3 al consultar `/api/estado` y `/api/analisis-cita-ms/estado`; no se especifica en esos mensajes el hostname de las solicitudes. Es un reporte del equipo, no una comprobación independiente desde este entorno.

- [x] R1. Reproducido 403 S3 en `https://proyectocitas-grupo19.click/api/estado`; el dominio API responde 200 JSON. Ver evidencia del diagnóstico del 21 de noviembre abajo.
- [x] R2. ECS estándar `citas-api:1` preservado; nuevo `citas-api-science:2`, una tarea sana, target saludable e integración pública verificados. Evidencia: `artifacts/ms_deploy/despliegue_final.json`.
- [x] R3. El bundle público `index-CHS3r4dZ.js` contiene base `https://0l5wznwt5i.execute-api.us-east-1.amazonaws.com`. Se verificó ese destino por HTTP y se ejecutó una recomendación desde la SPA en navegador.
- [x] R4. Confirmada arquitectura de llamadas directas a API Gateway con CORS operativo; no requiere behavior API en CloudFront para el funcionamiento actual.
- [x] R5. Estado y POST estándar 200; estado M/S 200 con modelos cargados y POST científico real por HTTPS aprobado con caso sintético de 46 fragmentos comparado contra referencia local.

El Terraform local de CloudFront define únicamente origen S3 y behavior adicional `/assets/*`; no define origen backend ni behavior `/api/*`. El cliente React admite `VITE_API_BASE_URL` y usa rutas relativas si está vacío. Por eso un 403 de S3 en el dominio SPA es compatible con solicitudes dirigidas al origen estático, pero no prueba que ECS esté apagado. Agregar behaviors no es obligatorio si la SPA utiliza correctamente el dominio API. Confirmar la configuración efectiva antes de modificar infraestructura.

Dependencia: resolver R1–R4 antes de atribuir fallos públicos a los modelos. R5 forma parte de la aceptación de entrega 1.

#### Evidencia del diagnóstico público — 21 de noviembre, aproximadamente 18:12 Bolivia

| Consulta | Resultado |
| --- | --- |
| `https://proyectocitas-grupo19.click/api/estado` | 403, `server: AmazonS3`, XML AccessDenied; es el dominio estático |
| `https://api.proyectocitas-grupo19.click/api/estado` | 200 JSON, `server: uvicorn`, modelo 0.2.0 y `listo: true` |
| `https://0l5wznwt5i.execute-api.us-east-1.amazonaws.com/api/estado`, con Origin SPA | 200 JSON y `access-control-allow-origin: https://proyectocitas-grupo19.click` |
| OPTIONS `/api/recomendar` en dominio API con Origin SPA | 204; permite POST y content-type |
| POST `/api/recomendar` en el destino configurado por React | 200 JSON con recomendaciones reales |
| SPA pública en navegador, consulta “Neural approaches for scientific document classification” | Se mostraron 10 referencias, encabezadas por D15-1167 |
| `https://api.proyectocitas-grupo19.click/api/analisis-cita-ms/estado` | 404 JSON de FastAPI; la ruta científica no está publicada en ese backend |

Conclusión: conexión de la SPA estándar con el backend verificada; el 403 se reproduce al consultar rutas API en el hostname estático. No se modificaron AWS, DNS ni CloudFront. El endpoint científico ausente requiere desplegar el backend actualizado; no se corrige concediendo acceso público al bucket. La inspección ECS y el POST científico se completaron posteriormente durante el despliegue descrito abajo.

Marcar una tarea únicamente cuando exista la evidencia indicada. Estados: pendiente, en curso, bloqueado, completado. Las casillas abiertas están pendientes salvo anotación expresa.

### Entrega 1 — API científica pública

#### A. Inferencia local reproducible

- [x] A1. Extraer únicamente pesos y manifiestos M/S en las rutas esperadas.
- [x] A2. Verificar tamaños, hashes y coherencia de manifiestos. Resultado inicial: `listo: true`.
- [x] A3. Descargados y verificados contra el manifiesto los seis archivos SciBERT de la revisión fijada, en `artifacts/huggingface`.
- [x] A4. Preparado `.venv-ms` con Python 3.12.10 y versiones científicas del equipo; dependencias congeladas en `artifacts/ms_local/requirements_instalados.txt`. Paquete de recuperación cargado por PYTHONPATH; la compatibilidad de empaquetado Python >=3.14 sigue pendiente de formalizar para distribución.
- [x] A5. Recuperados solicitud TRAIN y respuesta de referencia desde `tmp/caso_train_smoke_ms.zip`, sin imprimir textos privados.
- [ ] A6. Revisar equivalencia de fragmentación, ensamblado AB, tokenización, truncamiento y ajuste PH respecto al notebook 10.
- [x] A7. Smoke offline real `ok: true` y POST local HTTP 200 con Top-3/clases coincidentes; nueve puntuaciones por modelo. Evidencia local en `artifacts/ms_local/smoke_referencia.json` y `reporte_http.json`; procedimiento en [verificación macOS](verificacion_local_ms_macos.md).

Dependencia: A3–A6 antes de A7. Cierre: smoke real `ok: true`, comparación satisfactoria con referencia según la tolerancia documentada, sin utilizar Test Gold.

#### B. Distribución privada de artefactos

- [x] B1. Creado bucket privado `citas-api-models-646941583111-us-east-1`; release de contenido `ms-scibert-b8ee47317c29afbc` bajo `releases/`. Versionado activo; sin Object Lock.
- [x] B2. Inventario de 10 archivos y hashes en `config/ms_release.json`; excluidos `pred_gold.jsonl`, anotaciones y casos de prueba.
- [x] B3. Artefactos y `release.json` publicados y verificados mediante descarga completa, tamaño y SHA256. Reporte `completado`, `verificado: true`, UTC 2026-11-22 00:25:21; log termina en `RELEASE OK`.
- [x] B4. Rol `citas-api-ecs-task` con GetObject sobre `releases/*`. Simulación IAM: lectura permitida y escritura denegada; bucket con bloqueo público, AES-256 y versionado verificados.
- [x] B5. Implementar aprovisionamiento al almacenamiento local del contenedor antes de servir inferencia, con descarga temporal, verificación y fallo explícito ante archivos inválidos. Implementado en `scripts/iniciar_ciencia.py`; pruebas de caché, corrupción y release distinta aprobadas. Validación real del arranque en contenedor incluida en C1.
- [x] B6. Hacer configurables las rutas M/S y la caché Hugging Face; mantener carga local durante la inferencia. `MS_MODEL_ROOT`, `MS_ARTIFACTS_DIR`, `MS_SCIBERT_MANIFEST` y `HF_HOME`; servicio local precargado y POST 200 verificados.
- [x] B7. Revisar `.dockerignore` y el contexto de construcción para excluir ZIP, pesos, cachés, datos privados y dependencias locales. `Dockerfile.ms` usa COPY explícito; contexto observado de 142 KB, sin checkpoints ni ZIP.

Dependencia: B1–B2 antes de publicación; B3–B6 antes del despliegue. Cierre: contenedor limpio aprovisionado desde S3 sin depender de SharePoint ni descargar modelos por cada consulta.

#### C. Imagen, infraestructura y operación

- [x] C1. Imagen M/S Python 3.12 formalizada en `Dockerfile.ms`, base por digest, dependencias transitivas fijadas y `pip check`. Builds x86_64/ARM64 aprobados. POST real completo Linux ARM nativo: 23.598 s, Top-3 y M/S coincidentes con referencia. x86_64 emulado carga y readiness correctos, pero POST agotó 300 s; La aceptación posterior en ECS x86_64 nativo pasó con el caso sintético de C8. Evidencia en [contenedor científico](contenedor_cientifico_ms.md).
- [ ] C2. Workflow y script preparados en `.github/workflows/deploy-scientific-api.yml` y `scripts/ci/deploy-science.sh`; YAML/Bash verificados. Falta incorporarlos al repositorio remoto y ejecutar GitHub Actions. Esta primera publicación se hizo con CodeBuild temporal y Terraform local.
- [ ] C3. Dimensionamiento inicial medido: 4 vCPU/8 GiB, 4.813 s; configuración final 2 vCPU/6 GiB, 8.533 s para caso sintético de 46 candidatos. Una inferencia concurrente adicional recibe 429 en 0.773 s. Memoria observada inicialmente por CloudWatch ~1.60 GiB, no pico de proceso. Faltan prueba de carga sostenida y variedad de solicitudes hasta el límite de entrada.
- [x] C4. Carga obligatoria antes de completar startup; `/health/ready` usado por contenedor y target group, tarea ECS saludable. El estado público informa modelos cargados; no sustituye POST.
- [x] C5. API Gateway conserva 30 s; cliente React ajustado a 32 s. Capacidad final probada en 8.533 s; bloqueo no encolante con HTTP 429 y Retry-After 5, verificado públicamente. La prueba no garantiza latencia para toda distribución posible de entradas.
- [x] C6. Imagen por digest en SSM, código identificado `199c457f6b5cd46f952bfd06f7b8f2515d32e62262bd6cef574e026616899f10`, release `ms-scibert-b8ee47317c29afbc`; hashes de checkpoints/SciBERT verificados al arrancar y versión expuesta en estado. Evidencia en `artifacts/ms_deploy/despliegue_final.json`.
- [x] C7. Plan inicial: cinco altas y cero cambios/destrucciones de recursos existentes. Ajuste posterior limitado a tarea/servicio científicos. Revisión científica 1 conservada para rollback; estado previo y HTML anterior guardados. Cómputo final aproximado US$0.10763/h (US$78.57/730 h), excluidos IPv4 y auxiliares. Ver guía de despliegue.
- [x] C8. API científica desplegada en ECS x86_64 nativo y POST real por HTTPS validado con textos sintéticos: Top-3, clases y nueve probabilidades coinciden con referencia local, tolerancia 0.005. No se envió el caso TRAIN privado: revisión automática rechazó esa transmisión sin autorización específica; se completó la aceptación con datos inventados.
- [x] C9. React publicado con API base `https://api.proyectocitas-grupo19.click`; `/analisis-ms` probado en navegador con ejemplo ilustrativo, Top-3 y resultados M/S visibles. Preflight CORS 204 y recomendación estándar 200. Assets anteriores conservados y HTML previo respaldado.

El runtime actual mantiene recuperador y dos clasificadores en memoria, y serializa las inferencias con un lock. Evitar multiplicar workers sin medir el consumo de memoria. Un GET de estado o una respuesta HTTP 200 sin inferencia no cierra C8.

Dependencia: A y B antes de C8. Cierre de entrega 1: inferencia desde la SPA pública con artefactos auténticos, evidencia reproducible y rollback disponible.

### Entrega 2 — Recomendaciones con análisis por artículo

#### D. Contenido de artículos y backend integrado

- [x] D1. Auditar correspondencia entre IDs del recomendador, metadatos y textos de ACL OCL; medir cobertura real del corpus elegido.
- [x] D2. Definir un corpus inicial preparado, con procedencia y condiciones de uso documentadas. Evitar depender de descarga/extracción de PDFs arbitrarios por consulta en esta primera versión.
- [x] D3. Preparar fragmentos con el procedimiento compatible con los experimentos, preservando artículo, ID de fragmento, sección y fuente.
- [x] D4. Exponer disponibilidad de texto por resultado de recomendación.
- [x] D5. Crear un contrato backend para analizar un contexto y un ID de artículo: el servidor resuelve título, resumen y candidatos del mismo artículo.
- [x] D6. Manejar ausencia de texto, menos de tres fragmentos válidos, metadatos insuficientes y artículo desconocido con respuestas explícitas. No usar fragmentos de otro artículo como sustitución.
- [x] D7. Cachear contenido preparado y, si se cachean resultados, incluir contexto, versión del contenido y modelos en la clave.

La implementación actual exige exactamente tres fragmentos para construir AB. Definir el comportamiento ante menos de tres antes de conectar el flujo; no duplicar ni inventar fragmentos para completar la entrada.

Dependencia: D1–D3 antes de D5. Cierre: analizar un artículo recomendado sin suministrar manualmente título, resumen o fragmentos.

#### E. Experiencia de usuario

- [x] E1. Incorporar acción “Analizar cita” en cada artículo recomendado, con disponibilidad visible.
- [x] E2. Conservar el contexto e incorporar selección de posición de cita; construir `TARGETCIT` sin exigir que el usuario conozca el marcador técnico.
- [x] E3. Mostrar Top-3 bajo demanda, con sección, procedencia y acceso a la publicación.
- [x] E4. Mostrar clase estimada de M y S y sus desacuerdos, explicando su significado; no presentar softmax como porcentaje de acierto.
- [x] E5. Añadir estados de carga, indisponibilidad, contenido insuficiente, error y servicio ocupado; evitar resultados obsoletos al cambiar de contexto o artículo.
- [x] E6. Simplificar navegación para distinguir recomendación integrada y demostración manual avanzada; revisar qué vistas históricas siguen siendo útiles.

Dependencia: contrato D5 antes de integración E1–E5. Cierre: recorrido comprensible desde texto hasta fragmentos y funciones sin copiar JSON.

#### F. Validación completa y publicación

- [x] F1. Probar contrato de datos e identidad de artículo, fallos de cobertura e integridad, y límites de entrada.
- [x] F2. Probar recorrido React → API con inferencia real y contenido autorizado; distinguir pruebas con respuestas simuladas de pruebas reales.
- [ ] F3. Medir latencia del flujo y comprobar solicitudes simultáneas, recuperación tras reinicio y rollback.
- [x] F4. Publicar API y SPA compatibles, comprobar caché de frontend y ejecutar el recorrido por los dominios públicos.
- [x] F5. Actualizar README y guía de operación con versiones, instalación, ejemplos, cobertura conocida y limitaciones.
- [x] F6. Guardar evidencia final de URL, fecha, versión, hashes y resultado funcional, sin subir Gold, credenciales ni textos privados.

Cierre de entrega 2: desde la URL pública se recomienda un artículo, se selecciona, se recuperan sus fragmentos y se obtienen M/S; los casos sin cobertura se explican correctamente.

## Decisiones pendientes

### Estado actual y próximo bloque

**El recorrido integrado está publicado y probado desde la portada pública.**
En `https://proyectocitas-grupo19.click/` se recomienda, se abre un artículo
con texto disponible, se marca la posición de cita con un botón y se ejecuta
Top-3 + M/S sin copiar metadatos ni fragmentos. La entrada manual sigue como
herramienta avanzada en `/analisis-ms`.

Release de pesos: `ms-scibert-b8ee47317c29afbc`; tarea `citas-api-science:3`.
Imagen integrada: `sha256:121315286820ddff1753f839062303dba48dd98dff6a60aef82fab6465839cd5`.
Corpus: 22 artículos aptos de 38 revisados, frente a 19.776 artículos del catálogo.
Los 16 excluidos exceden las reglas V1 por longitud de párrafo; no se recortaron.
D1–D7 se cierran para este corpus inicial, no para la totalidad del catálogo.

Aceptación pública por ID `S15-1012`: 42 candidatos, Top-3 con identidad y texto
verificados, nueve categorías por modelo, 16.784 s con 2 vCPU/6 GiB.
El documento de mayor volumen preparado pasó en 21.483 s y el de más fragmentos
(55) en 11.238 s. Estas verificaciones usan contextos inventados y documentos
públicos, sin transmitir TRAIN privado ni Gold. No certifican calidad científica.

**Siguiente funcionalidad: ampliar la cobertura de texto completo** sin alterar
silenciosamente la fragmentación del experimento. F3 sigue abierto: existe
medición funcional de latencia y reinicio del servicio, pero faltan carga sostenida,
concurrencia del flujo integrado y ensayo completo de rollback.
Ver [guía del flujo, cobertura y contrato](flujo_integrado_ms.md).

Pendientes operativos: incorporar y ejecutar el workflow preparado (C2), ampliar
mediciones de carga (C3) y cerrar auditoría de equivalencia del notebook (A6).
Ver [despliegue y rollback](despliegue_cientifico_aws.md).

### Revisión de documentos de entrega

Se leyeron los dos documentos de `docs/proyecto_final/` (artículo e informe, REVISION 2). Ambos declaran corte del 16 de noviembre y describen SciBERT-A/Jurado y la matriz A4/Haiku, no la posterior demostración M/S del notebook 10. Conservar ese carácter histórico o crear una revisión nueva; no reemplazar cifras A4 con cifras M/S ni presentar la recuperación de M/S como recuperación de los cuatro pesos A4.

- [ ] DOC1. Actualizar el corte documental y añadir una sección diferenciada para M/S: procedencia, entrada AB, pesos verificados y evidencia de inferencia local/pública según corresponda.
- [ ] DOC2. Conciliar el alcance del demostrador: los documentos sitúan la clasificación de nueve funciones como eje y Top-3 como entrada complementaria. La integración con recomendación de artículos será una funcionalidad adicional, sin sustituir la demostración científica prioritaria.
- [ ] DOC3. Separar disponibilidad de M/S, SciBERT-A/Jurado y cuatro modelos A4; decidir con el equipo si la entrega exige también servir el factorial 2×2. M/S no satisface por sí solo ese requisito.
- [ ] DOC4. Revisar el estado de Gold y métricas con evidencia reciente; los mensajes del equipo no bastan para certificar doble anotación, independencia ni adjudicación.
- [ ] DOC5. Actualizar URLs, arquitectura, versiones y prueba HTTPS únicamente después de validación pública. Mantener los resultados de desarrollo e históricos separados de las puntuaciones mostradas por la aplicación.

Los documentos revisados no fueron modificados. Esta revisión contrasta alcance y actualidad con el código y las evidencias locales; no constituye validación independiente de bibliografía ni de todas las métricas históricas.

| Decisión | Propuesta inicial | Cuándo resolver |
| --- | --- | --- |
| Artefactos en AWS | S3 privado, versionado e integridad por hashes; descarga antes del arranque | B1 |
| Organización del backend | Mantener los dominios actuales; medir si API estándar y científica conviven o requieren servicios separados | C3 |
| Recursos y costos | Dimensionar con mediciones; no asumir que 1 GB alcanza | C3/C7 |
| Corpus inicial | Subconjunto preparado y trazable con texto completo disponible | D1/D2 |
| Resultados científicos | Mostrar M y S; no escoger automáticamente un ganador por consulta | E4 |
| Entrada del usuario | Contexto en inglés y posición de cita explícita, compatible con entrenamiento | E2 |

## Límites del seguimiento

Este plan cubre producto, reproducibilidad y operación. No declara calidad científica validada del flujo integrado, no reentrena modelos y no convierte el Test Gold en material de demostración. La evaluación científica independiente se mantiene separada. Ya se creó almacenamiento privado y permiso de lectura ECS en AWS; la imagen M/S ya está desplegada en ECS y la API pública fue comprobada con datos sintéticos. La integración automática con los artículos recomendados sigue pendiente.

## Registro de avances

| Fecha | Avance | Evidencia / siguiente paso |
| --- | --- | --- |
| 2026-11-21 | Inspeccionado ZIP y extraídos cuatro archivos de inferencia; los JSONL de predicciones permanecen dentro del ZIP | Verificador M/S: `listo: true` para ambos; seguir con A3 |
| 2026-11-21 | Revisados React, runtime M/S, imagen y workflow estándar, configuración de Terraform | Plan de dos entregas acordado con José; estado público de AWS pendiente de verificar |
| 2026-11-21 | Incorporadas confirmaciones del equipo y reporte de 403 S3 | Añadidas tareas R1–R5: diagnosticar host, build SPA, backend y enrutamiento antes de publicar M/S |
| 2026-11-21 | Inferencia local M/S reproducida, distribución privada publicada y verificación de descarga en curso | Avanzar en B5/B6/B7/C1 sin dar B3 por verificada hasta su reporte final |

| 2026-11-21 | S3 verificado; contenedor M/S construido para ambas arquitecturas; POST Linux ARM completo coincidente con referencia | Siguiente: dimensionar y preparar despliegue ECS, tiempos, CI y aceptación x86_64 nativa/pública |

| 2026-11-21 | API M/S en ECS x86_64, release privada verificada, React publicado y POST sintético concordante en 8.533 s; estándar preservado | Evidencia `artifacts/ms_deploy/despliegue_final.json`; continuar entrega 2 y pendientes A6/C2/C3 |

Para cada avance posterior: registrar tarea, resultado comprobado, comando o enlace a evidencia, y bloqueo si existe. Mantener las tareas sin evidencia abiertas.

## Referencias

- [Plan general de José](plan_trabajo_jose_2026_11.md).
- [Guía de reproducción M/S](../guia_reproduccion_ms.md).
- [Manifiesto de distribución](../manifiesto_distribucion_ms.json).
- [Evidencia de inferencia real](../evidencia_inferencia_real_ms_20261120.md).
- [Notebook de modelos finales](../../notebooks/10_modelos_finales_M_S.ipynb).
- [Runtime M/S](../../src/app/ms_runtime.py).
- [Interfaz científica actual](../../frontend/src/pages/AnalisisMS.tsx).
- Conversación del equipo: `tmp/texto_whatsapp.txt`, mensajes del 17–21 de noviembre (archivo local).

