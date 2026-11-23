# Ampliación de cobertura de texto completo

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

El código y la documentación no sustituyen comprobaciones del despliegue. La aceptación pública queda pendiente hasta completar la preparación, publicación y verificación.

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
- [x] Publicar corpus privado `corpus-ms-c2985eac4e952d4b` (211.222.528 bytes), SHA256 remoto contrastado.
- [ ] Completar la publicación corregida y su aceptación pública.
- [ ] Verificar recorridos públicos, capturas de escritorio/móvil, salud y constructora detenida.

T04 sigue pendiente por cuota; T05–T06 suspendidas; T07–T09 disponibles para M/S/comercial con familia abierta suspendida; T10 parcial; T11 requiere la aceptación pública de esta ampliación; T12 y cierre final de T13 pendientes. No se declara completo el proyecto de tres familias.
