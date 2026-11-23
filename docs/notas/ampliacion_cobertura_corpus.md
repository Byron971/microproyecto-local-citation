# Ampliación de cobertura de texto completo

> Cierre 23/11/2026: ampliación y UI publicadas y aceptadas. Catálogo de 19.776; 19.243 artículos analizables, 508 con recorte. Las secciones históricas registran las incidencias y sus correcciones; la aceptación final está al final.


## Alcance y decisiones

Petición del usuario: ampliar la cobertura de Top-3 y clasificación más allá de los 37 artículos iniciales, sobre el catálogo de 19.776 IDs existente. Las sugerencias siguen siendo una ayuda del paso 2; la selección del artículo es manual y los tres fragmentos pertenecen exclusivamente a ese artículo.

No se entrenan modelos, modifican pesos ni se recalculan los embeddings del índice de títulos/resúmenes. El recuperador codifica los fragmentos del artículo seleccionado durante cada análisis, como antes. M/S conserva su entrada AB y sus límites; el comercial conserva contexto, título y resumen, perfil, consentimiento y controles de consumo. QLoRA continúa suspendido.

El snapshot fijado de [ACL-OCL](https://huggingface.co/datasets/WINGNUS/ACL-OCL/tree/300ee6c5e5629d042bfc07cbc406e2f330b53659) contiene rutas JSON para 19.599 de los 19.776 IDs del catálogo. Un archivo presente no implica por sí solo texto procesable. Se registra por artículo si queda preparado, no existe archivo en ese snapshot, no cumple el contrato o hubo un error de adquisición. Un error de red no se considera ausencia de texto.

Se conservan la fragmentación V2 y deduplicación del notebook 10, secciones e índices de párrafo. La decisión inicial de excluir documentos grandes quedó sustituida por la instrucción posterior del usuario: recortar al límite disponible. Se conservan los primeros 100 fragmentos distintos en orden de origen y se limita título, resumen y texto a 56.000 caracteres en conjunto, reservando 4.000 para el contexto. El último fragmento puede quedar parcial y marcado como recortado; no se agregan puntos suspensivos al texto fuente. Título, resumen y sección respetan además sus límites existentes (600/12.000/200). Se registran tamaños originales y analizados y hashes de los metadatos originales; el índice de sugerencias conserva los metadatos originales. La UI advierte del recorte antes del análisis y en resultados: el Top-3 pertenece al contenido retenido, no garantiza cubrir el artículo entero. Esta tarea no acredita balance del dataset, anotación humana, independencia del test ni métricas de calidad científica.

## Simplificación del paso 2

Por instrucción posterior del usuario, al entrar al paso 2 se solicitan automáticamente cinco sugerencias según el contexto. Se elimina el botón inicial de sugerencias. No se hacen solicitudes mientras se escribe el contexto, ni reintentos automáticos; se conserva cancelación, búsqueda literal y recuperación manual ante errores. Volver entre etapas no repite la solicitud para el mismo contexto y versión del catálogo. Cambiar el contexto reinicia el recorrido.

No hay artículo confirmado por defecto, tampoco al elegir ejemplos. Los ejemplos cargan únicamente el contexto; la referencia del ejemplo sigue visible como información en el modal. El usuario debe seleccionar el artículo antes de avanzar. Una selección manual posterior se conserva al navegar.

## Preparación y almacenamiento

- `scripts/descargar_corpus_git.py` extrae únicamente JSON del catálogo desde un snapshot Git local, verifica el hash del blob; la preparación comprueba la identidad del JSON. No descarga LFS ni ejecuta código del dataset. La adquisición HTTP inicial alcanzó 429; se detuvo y se sustituyó por una transferencia Git completa de la revisión fijada, conservando y verificando la caché.
- `scripts/ampliar_cobertura_corpus.py` prepara documentos offline con memoria acotada y reanudación. Genera SQLite, un informe completo y estados por ID en `artifacts/coverage_expansion/`. Conserva íntegros los 37 documentos iniciales.
- `scripts/publicar_corpus_ampliado.py` valida cada cuerpo, lo reconstruye desde su JSON fuente, comprueba metadatos y los 37 originales, y publica un artefacto inmutable con hashes. No publica nada si quedan IDs sin auditar o errores de adquisición pendientes.
- `config/corpus_release.json` identifica la release activa. El archivo grande se distribuye desde S3 privado, no desde Git ni el navegador. `config/corpus_ms.json` conserva el corpus inicial para regresión, compatibilidad y evidencia histórica.
- `IndexedCorpus` verifica integridad al arrancar y lee/descomprime solo el artículo seleccionado; sus metadatos pueden recorrerse sin cargar todos los cuerpos. API y servicio científico usan el mismo inventario y versión. No se descargan artículos durante solicitudes HTTP.
- El JSON ligero del paso 2 conserva títulos/IDs de todos los artículos y sus indicadores de cobertura. Los 33 ejemplos existentes se conservan; no se incorporan etiquetas o predicciones ni se amplía el modal en esta tarea.

El código y la documentación no sustituyen comprobaciones del despliegue. La aceptación pública final se registra al cierre, después de preparar, publicar y verificar la integración.

## Reproducción

Obtener el snapshot público Git sin materializar LFS, fijar su HEAD a `300ee6c5e5629d042bfc07cbc406e2f330b53659` y conservarlo en un directorio de datos distinto del checkout del proyecto. La extracción rechaza otra revisión y no hace solicitudes de red implícitas.

Desde la raíz del proyecto:

```sh
make corpus-extract PYTHON=.venv/bin/python CORPUS_SOURCE_DIR=/ruta/al/snapshot
make corpus-prepare PYTHON=.venv/bin/python CORPUS_SOURCE_DIR=/ruta/al/snapshot
make corpus-release PYTHON=.venv/bin/python AWS_PROFILE=josezambrana
make corpus-catalog PYTHON=.venv/bin/python
```

La publicación del corpus usa el bucket y permisos existentes. La infraestructura y el despliegue de imágenes se mantienen bajo Terraform/Make; no crear ni sustituir recursos fuera de ese flujo. API y científico necesitan nuevas imágenes para leer el corpus indexado. Conservar punteros de reversión y detener la constructora al terminar.

## Corrección del límite de caracteres

La primera publicación operativa (`73aacdf`, corpus `corpus-ms-c2985eac4e952d4b`, API 6 / científico 7) superó salud, hashes y sincronización del HTML, pero todavía no constituía la aceptación pública final. La revisión posterior detectó 270 cuerpos en los que el espacio sobrante tras cortar una palabra podía incorporar caracteres de fragmentos siguientes. Se corrigió la preparación para detenerse al primer fragmento parcial. Una prueba reproduce el defecto sobre el código anterior y pasa con la corrección; el publicador comprueba de forma independiente que no existan fragmentos parciales intermedios. Se conservan la primera base, informe y confirmación en `artifacts/coverage_expansion/*73aacdf*`, y la release S3 anterior permanece inmutable.

La nueva preparación mantiene 19.243 artículos y 508 recortados. Release corregida `corpus-ms-276bc4320e8e8411` (211.255.296 bytes), publicada y contrastada con descarga multipart completa y SHA256. La nueva auditoría reconstruye todos los cuerpos desde la fuente y conserva los 37 originales. Las pruebas comerciales con mocks usan explícitamente el corpus inicial versionado para no depender de una descarga externa ni del estado transitorio entre regeneración e inventario.

## Comprobaciones locales

57 pruebas de API, corpus indexado, recorte, contratos y comercial con mocks; 14 de búsqueda científica, concurrencia y arranque. 38 pruebas unitarias frontend y 78 recorridos UI de escritorio/móvil aprobados; capturas revisadas en `artifacts/coverage-final-mocks/`. Comprobación local adicional con SciBERT/M/S en caché sobre `C80-1027`, recortado de 110 a 100 fragmentos: 7,235 s con dos hilos CPU y Top-3 contrastado con los textos retenidos. No es validación científica ni benchmark estadístico. No se hicieron llamadas comerciales reales.

## Estado de esta tarea

- [x] Implementación del almacenamiento indexado y preparación reanudable.
- [x] Pruebas de contratos e integridad; dos inferencias locales acotadas con pesos en caché, textos contrastados y dos hilos CPU (1,157 s para 3 fragmentos; 11,846 s para 92). Son observaciones operativas, no un benchmark estadístico.
- [x] Completar extracción de 19.599 JSON y preparación de los 19.776 IDs: 19.243 preparados, 508 con algún recorte; 177 sin archivo, 130 sin párrafos de texto completo y 226 con menos de tres fragmentos distintos. La auditoría exhaustiva previa a publicación reconstruye cada cuerpo desde su fuente.
- [x] Publicar corpus privado corregido `corpus-ms-276bc4320e8e8411` (211.255.296 bytes), SHA256 remoto contrastado.
- [x] Completar la publicación corregida y su aceptación pública.
- [x] Verificar recorridos públicos, capturas de escritorio/móvil, salud y constructora detenida.

T04 sigue pendiente por cuota; T05–T06 suspendidas; T07–T09 disponibles para M/S/comercial con familia abierta suspendida; T10 parcial; T11 incluye la aceptación pública de esta ampliación y de su espera asíncrona; T12 y cierre final de T13 pendientes. No se declara completo el proyecto de tres familias.


## Límite público de espera y corrección de integración

La publicación `eb0d14e` verificó servicios, corpus y HTML. El selector público aprobó cuatro recorridos. En la aceptación M/S, tres recorridos pasaron y cinco fallaron: los documentos de 100 fragmentos y 56K caracteres superaban los 30 segundos de API Gateway; el servidor registraba finalmente 200, mientras el navegador recibía 503. Una sugerencia posterior recibió 429 porque el cálculo anterior seguía activo. Esta ejecución no acredita aceptación completa; trazas preservadas en `artifacts/coverage-public-ms-eb0d14e/limite_gateway_30s/`. No se repite una prueba sobre caché para ocultar este límite.

Se conserva `POST /api/analisis-cita-ms/articulo`, con modo opcional `asincrono: true` para la web: devuelve 202 e identificador aleatorio. `GET /api/analisis-cita-ms/articulo/{trabajo_id}` consulta exclusivamente ese cálculo y entrega el mismo resultado final. El contrato síncrono anterior se conserva. Hay un solo cálculo activo, sin cola, con el mismo RLock compartido con sugerencias y M/S; ocupado sigue devolviendo 429. El comercial conserva su solicitud única posterior al Top-3 y su consentimiento.

Los resultados son transitorios, solo en memoria del proceso, con máximo ocho y caducidad de 120 segundos después de terminar, eliminados mediante temporizador. No se ofrece historial ni listado; los IDs son aleatorios de 128 bits. Reiniciar el servicio o expirar el resultado devuelve 410, conservando los datos del formulario. El navegador consulta cada segundo, deja de consultar al abandonar la página y deja de programar nuevas consultas al alcanzar tres minutos (cada petición conserva su timeout de 32 segundos); no reintenta automáticamente POST ni un GET fallido. Abandonar la espera no detiene el cálculo ya iniciado. No se añade almacenamiento AWS ni se aumenta CPU/memoria; no se modifican modelos ni el corpus corregido. Estos límites operativos no cierran T10.

En esta fase quedaba pendiente comprobar la corrección sobre la imagen científica y el frontend publicados, con un proceso recién iniciado. El resultado se registra a continuación.

Validación local de la espera: 65 pruebas de contratos/corpus/publicación/trabajos/comercial, 14 científicas/arranque/concurrencia, 41 unitarias frontend y 82 recorridos UI aprobados. El build es correcto. Esta corrección requiere solo imagen científica y frontend; la API comercial se conserva en `eb0d14e`.


## Publicación y aceptación final — 23/11/2026

- Imagen científica: código `e84fd3ad0661dea3113470df7ac84a084f4144cd`, digest `sha256:f9737536a03de29fee060db65cbb8b394fe33b46703ddbfa819815da99c1e144`, ECS `citas-api-science:9`.
- API conservada en código `eb0d14e6339452c7081dcd39bbd777698174f76b`, imagen `release-api-eb0d14e6339452c7081dcd39bbd777698174f76b`, ECS `citas-api:7`. En el último despliegue solo cambió la imagen científica, su definición y su servicio: CPU, memoria, IAM, secretos y controles comerciales iguales.
- Corpus corregido `corpus-ms-276bc4320e8e8411`, SHA256 SQLite `65bff0328eed93991079d405b060bc0ab18591035e84a060edf13f0813991aa0`. Hash del inventario/versión de contenido `1f496d7b681b0852d927462f7b24a854189f37535e58d598cc131f435146b55d`. Los 37 originales, pesos y embeddings del índice se conservaron.
- Cuatro recorridos públicos del selector aprobados en la versión final, escritorio/móvil: cinco candidatos automáticos, títulos/resúmenes/IDs/versiones contrastados con el índice, ninguna selección por defecto, selección manual y ausencia real de cobertura. Sin clasificación comercial. Evidencia: `artifacts/coverage-public-selector-e84fd3a/`.
- Ocho recorridos M/S públicos aprobados, cuatro tipos por dos tamaños: original `W05-0821`, ampliado `A00-1001`, exceso de fragmentos `C80-1027` (110 → 100) y exceso de caracteres `J00-3003` (92 → 75; 55.994 caracteres retenidos, un solo fragmento parcial al final). Se comprueba un único POST de inicio, respuesta 202 y resultado por GET; cada texto Top-3 coincide con el corpus del artículo confirmado. No se acredita calidad científica.
- La primera pasada asíncrona aprobó cuatro casos y encontró un selector de prueba ambiguo en los otros cuatro: buscaba el aviso tanto en una etapa oculta como en resultados. Se acotó a `#analysis-results` y se repitieron exclusivamente los cuatro afectados, todos aprobados. Se conservan las trazas originales. Evidencia consolidada de los ocho casos: `artifacts/coverage-public-ms-e84fd3a/aceptacion.json`, JSON y capturas por escenario/dispositivo. No se cambió la aplicación para resolver esa ambigüedad del test.
- Capturas públicas de resultados revisadas en escritorio/móvil, con aviso de alcance recortado, tres fuentes y función predicha; sin desbordamiento horizontal. Capturas del selector revisadas también. La auditoría completa de 19.243 cuerpos fue local y de la copia S3; la aceptación web muestrea cuatro artículos, no ejecuta todos los artículos ni valida etiquetas Gold.
- `make release-confirm`: servicios estables, imágenes previstas, salud, 19.243 preparados y versión de corpus correctos; HTML idéntico al build. SHA256 de `index.html`: `1486b4dc1a0290982e17eac68b5df0e9dd1c14f3eafaf79a5c2f2d546073a3e6`.
- EC2 `i-03c35e1f2d0597f9f` detenida mediante Terraform y comprobada por lectura actual; instancia y disco conservados. Reversión inmediata en `artifacts/release-rollback.tfvars.json`; punteros del despliegue anterior a esta tarea en `artifacts/coverage_expansion/reversion_previa_a_cobertura.tfvars.json`. Las releases S3 anteriores son inmutables.
- No se ejecutaron llamadas comerciales reales en esta tarea; consentimiento, perfil, modelo, cuota y exclusión comercial se comprobaron con mocks/contratos y se conservaron. No se ejecutó QLoRA.

## Checklist del proyecto al cierre

| Tarea | Estado comprobado |
|---|---|
| T01–T03 | UI secuencial publicada; sin artículo por defecto, sugerencias automáticas y recorte informado. |
| T04 | Pendiente de resolución/verificación de cuota y aceptación Serverless; ECS se conserva. |
| T05–T06 | Suspendidas por decisión sobre QLoRA. |
| T07–T08 | Catálogo completo y texto ampliado para M/S/comercial; familia abierta suspendida. |
| T09 | Comercial publicado y aceptado históricamente; sin llamadas reales adicionales en esta entrega. |
| T10 | Parcial; siguen pendientes los demás controles de acceso, retención, escala, alertas y presupuesto de tiempo/costo. La espera transitoria no lo cierra. |
| T11 | Ocho recorridos públicos M/S y cuatro del selector aceptados; comercial conserva aceptación anterior. Familia abierta suspendida. |
| T12 | Migración y retirada pendientes; no se retira ECS. |
| T13 | Notas y PRD actualizados con evidencia local y pública; cierre documental final del proyecto pendiente. |

El proyecto de tres familias continúa parcialmente cumplido. Esta entrega acredita funcionamiento de aplicación e integración, no balance, validación humana, independencia del test ni superioridad comparativa.
