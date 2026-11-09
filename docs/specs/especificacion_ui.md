# Especificación de la aplicación React — S3, CloudFront y API en ECS

Estado: primera implementación local en `feature/interfaz-react-107`; publicación en AWS pendiente.

Actualizado: 2026-11-08. React y Terraform implementados; no se ha ejecutado apply de S3/CloudFront.

## 1. Objetivo

Crear desde cero una aplicación React con Vite y TypeScript, independiente
del tablero actual de `src/app/static/`. Se publicará como SPA estática en
Amazon S3, distribuida por CloudFront, y consumirá el API existente en ECS
a través de su URL pública de API Gateway. El centro de la aplicación es el
recomendador:

1. La persona pega un fragmento de texto académico.
2. Elige un modelo.
3. Pulsa **Recomendar**.
4. Revisa los resultados en una tabla.

Las tres secciones analíticas del tablero actual (estudio de los datos,
desempeño del modelo y diagnóstico de negativos) se reconstruyen como vistas
secundarias de la nueva aplicación. El tablero existente es referencia de
contenido y comportamiento, no la base de una migración incremental de su HTML.

La identidad visual es la definida en [identidad_visual.md](../identidad_visual.md):
paleta «Índice», Outfit y DM Sans, iconos de línea fina y el monograma de la C.

### Fuera de alcance

- Cuentas de usuario, autenticación o historial guardado en el servidor.
- Exportar resultados a archivos.
- Desplegar el frontend en Nginx, Docker o ECS; esos servicios no alojarán
  la nueva aplicación React.
- Retirar el tablero anterior de FastAPI en esta entrega.
- Activar un dominio personalizado; se usará primero la URL HTTPS de CloudFront.
- Cambios en los modelos o en su entrenamiento. Esta especificación solo pide al
  backend que **exponga** los modelos que ya existen.

## 2. Usuarios y tarea principal

Estudiantes, docentes e investigadores que tienen un párrafo en el que falta una
cita y quieren candidatos del corpus ACL-200 (19.776 artículos).

**Restricción importante:** el corpus y los modelos están en inglés. La
interfaz está en español, pero debe indicar con claridad que el texto pegado
debe estar en inglés.

## 3. Arquitectura

```text
Navegador ──► CloudFront ──► S3 privado (React compilado)
    │
    └── HTTPS + CORS ──► API Gateway ──► VPC Link ──► ALB interno ──► ECS / FastAPI
```

El navegador descarga HTML, CSS y JavaScript por CloudFront. La aplicación
hace las peticiones directamente al API público; no se propone inicialmente
un segundo origen de API dentro de CloudFront.

| Aspecto | Decisión |
|---|---|
| Framework | React + Vite, en TypeScript; versiones compatibles por fijar al implementar |
| Ubicación | Proyecto nuevo en `frontend/`; salida compilada en `frontend/dist/` |
| Rutas | React Router en modo *history*: `/`, `/datos`, `/modelo`, `/negativos`; CloudFront debe soportar apertura directa y recarga |
| Estado | Hooks; persistir solo modelo elegido y número de resultados en `localStorage` |
| Llamadas al API | Módulo `api.ts` tipado; base configurable y rutas `/api/...` |
| Desarrollo | Servidor Vite con proxy `/api` hacia FastAPI local en `http://127.0.0.1:8000` |
| Publicación | Compilar el proyecto y subir `frontend/dist/` a un bucket S3 exclusivo para el frontend |
| Distribución | CloudFront con HTTPS y acceso al bucket mediante Origin Access Control (OAC) |
| Backend | API Gateway → VPC Link → ALB interno → ECS; el modelo sigue dentro del contenedor FastAPI |
| Gráficas | Recrear el contenido y significado de las gráficas actuales como componentes React, usando la identidad visual; librería por decidir |

### 3.1 Alojamiento estático y rutas

- Bucket S3 privado, con bloqueo de acceso público y permisos de lectura
  limitados a la distribución CloudFront mediante OAC. Usar el origen S3
  normal, no el endpoint de website hosting.
- Publicar inicialmente con la URL HTTPS por defecto de CloudFront y
  redirigir solicitudes HTTP a HTTPS.
- La ruta `/` sirve `index.html`. Las rutas de la SPA, como `/datos`, se
  resuelven a ese mismo documento antes de consultar S3; la pantalla la decide
  React Router. El mecanismo concreto se fijará al implementar CloudFront.
- Los assets inexistentes deben conservar su error: no convertir cualquier
  403/404 en una respuesta 200 con HTML. Las rutas desconocidas de la
  aplicación muestran una pantalla de «Página no encontrada».
- Esta resolución no depende de `nginx.conf` ni de rutas nuevas en FastAPI.

### 3.2 Conexión con el API existente

- Producción usa una base pública configurable, propuesta como
  `VITE_API_BASE_URL`, que apunta al origen HTTPS de API Gateway sin el sufijo
  `/api`. Las funciones añaden rutas como `/api/recomendar` una sola vez.
- La URL actual del laboratorio es
  `https://qlipl9bh0i.execute-api.us-east-1.amazonaws.com`. Es una referencia
  temporal, no debe quedar fija en los componentes. La cuenta personal tendrá
  su propio endpoint y requerirá configurar y volver a publicar el frontend.
- En desarrollo, una base vacía permite usar rutas relativas y el proxy Vite.
  También debe poder configurarse una URL remota explícita para probar ECS.
- La configuración `VITE_*` forma parte del JavaScript público compilado.
  Solo contiene configuración pública: nunca claves AWS, tokens privados o
  credenciales del laboratorio. El navegador no usa el perfil AWS local.
- El endpoint de API Gateway permanece público. CORS controla qué orígenes
  pueden leer respuestas desde un navegador; no es autenticación del API.

### 3.3 CORS y errores de conexión

La SPA y el API tienen orígenes distintos. La infraestructura del HTTP API
debe habilitar CORS con el origen HTTPS exacto de CloudFront y los orígenes
locales que se usen al conectar directamente al API. Permitir `GET`, `POST`
y las solicitudes preflight `OPTIONS`, junto con `Content-Type` para JSON.
No se requieren cookies ni peticiones con credenciales para el alcance actual.

Centralizar CORS en API Gateway y evitar encabezados duplicados o contradictorios
en FastAPI. Verificar tanto respuestas correctas como errores. El bloqueo
CORS, el fallo de red y el timeout necesitan un mensaje claro y reintento;
no deben confundirse con una lista de recomendaciones vacía.

El stack del API incorpora `cors_allowed_origins`; aplicar allí el origen de
CloudFront es un paso de despliegue pendiente. En CI se utiliza la variable
`CORS_ALLOWED_ORIGINS` para conservar esa configuración entre publicaciones.

### 3.4 Publicación y caché

- El frontend tiene su propio proceso de build y publicación; un cambio de
  interfaz no reconstruye ni despliega el modelo en ECS.
- Publicar los assets antes que `index.html`. Los assets con hash pueden
  tener caché larga; `index.html` debe actualizarse con caché corta o
  revalidación. La política de CloudFront debe respetar esa diferencia.
- Conservar los assets necesarios para páginas ya abiertas durante una
  actualización. Invalidar el documento de entrada cuando corresponda.
- Las peticiones de inferencia van directamente a API Gateway, no a la caché
  de CloudFront. Mostrar versión anterior del HTML no debe mezclar contratos
  incompatibles del API.
- La infraestructura y el proceso de publicación deben quedar documentados
  y reproducibles. Bucket, distribución, OAC y CORS se definirán con Terraform;
  el stack independiente está en `terraform/frontend/` y la publicación en
  `scripts/publicar_frontend.sh`. Las instrucciones están en `frontend/README.md`.
- El bucket del frontend es distinto del bucket del estado de Terraform.
  En la cuenta personal se requieren permisos para esos recursos y para el
  API existente. No se asumen los permisos ni el rol `LabRole` del laboratorio.

### 3.5 Relación con el tablero anterior

La nueva aplicación no requiere modificar `Dockerfile.dashboard` ni Nginx para
publicarse. Docker Compose puede seguir sirviendo la interfaz anterior como
herramienta local. FastAPI también conserva por ahora `/` y `/static` para
mantener el despliegue y sus comprobaciones actuales.

La URL pública de la nueva experiencia será la de CloudFront. Retirar el tablero
anterior, redirigir sus visitas o modificar los smoke tests actuales será una
decisión posterior, una vez validada la nueva aplicación.

Referencias de arquitectura: [S3 privado con OAC](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html)
y [CORS en HTTP API](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-cors.html).

## 4. Estructura de la pantalla

La vista inicial se reduce a la tarea principal:

```text
[C] Recomendación local                         Recomendar · Explorar ▾

Encuentra referencias                           Modelo                 ⓘ
Busca artículos relacionados con                [modelo disponible     ▾]
un fragmento de tu texto.
┌────────────────────────────────────────────────────────────────────┐
│ Contexto en inglés                                                 │
│ ┌────────────────────────────────────────────────────────────────┐ │
│ │                                                                │ │
│ └────────────────────────────────────────────────────────────────┘ │
│ [ Recomendar ] Resultados [10 ▾]     [ Usar un ejemplo ] │
└────────────────────────────────────────────────────────────────────┘

Referencias recomendadas       (solo después de consultar)
```

La frase bajo el título explica la tarea en una línea breve. No se muestran
contador de caracteres, atajo de teclado ni advertencia permanente. Se elimina
el panel «Opciones»: modelo y cantidad tienen controles visibles. En móvil el
selector de modelos pasa bajo el título y el botón de ejemplos ocupa su propia fila.
El selector usa un botón combobox de 48 px y una lista propia de opciones,
con selección marcada, estados no disponibles, flecha explícita y ayuda
junto a la etiqueta. En escritorio ocupa 320 px a la derecha; el bloque deja
24 px antes del formulario. Se conserva el foco visible y el acceso por teclado (flechas, Inicio/Fin,
Enter y Escape); al salir del control o hacer clic fuera, el menú se cierra.

### 4.1 Encabezado

- Monograma C y nombre del proyecto en una barra compacta de 80 px en
  escritorio, alineada con los 900 px del recomendador. Navegación con áreas
  de interacción de al menos 40 px y fondo discreto en la sección activa.
- Recomendar es el acceso principal. «Explorar» agrupa Datos, Desempeño,
  Negativos y «Fragmentos Top-3 · experimental»; es accesible con teclado y
  cerrable con Escape. Top-3 no forma parte del flujo principal de artículos.
- Se retira el indicador permanente de estado. La disponibilidad y los fallos
  se comunican cuando afectan al formulario o la consulta.

### 4.2 Selector de modelos y ayuda

- Se sitúa a la derecha del título en escritorio; se llena dinámicamente con
  `GET /api/modelos`, incluso si hay un único modelo disponible.
- El icono ⓘ junto a la etiqueta abre una explicación breve del modelo elegido,
  tomada de su `descripcion`. Funciona con teclado y se cierra con Escape.
- Mantener la elección disponible de `localStorage` o usar el predeterminado;
  los modelos no disponibles permanecen deshabilitados.
- Si falla el catálogo, se avisa brevemente y se recomienda sin el campo
  `modelo`, utilizando el predeterminado del API.
- Cambiar de modelo no relanza la consulta. Los resultados existentes se
  identifican como anteriores hasta volver a recomendar.

### 4.3 Contexto

- Etiqueta única «Contexto en inglés», sin explicación adicional ni contador.
- Campo de seis filas, redimensionable, sin corrector ortográfico y con ejemplo
  de texto académico como placeholder.
- Se conserva `Ctrl/Cmd+Enter`, aunque el atajo no se muestra permanentemente.

### 4.4 Acciones y ejemplos reales

- «Recomendar» como acción principal; «Buscando…» y botón deshabilitado al enviar.
- Validar texto vacío junto al campo, sin llamar al API.
- La cantidad (5, 10 o 20; 10 por defecto) se cambia junto al botón.
- «Probar con un ejemplo real» ofrece los ejemplos de `GET /api/ejemplos`.
  Cada opción muestra el título del artículo citado y un número de ejemplo;
  el ID del contexto se conserva internamente para distinguir consultas del
  mismo artículo. No selecciona por calidad
  de resultados ni inventa temas o textos.
- «Usar un ejemplo» abre un modal con una lista de títulos y una vista previa
  del fragmento original. Cada elemento completo se puede pulsar para cargar
  su texto y cerrar el modal. Se identifica el ejemplo en uso.
- El modal mantiene el foco dentro y devuelve el foco al botón al cerrarse.
  Se cierra con Escape, el botón de cierre o al pulsar fuera.
- Al elegir un ejemplo, se carga su texto original para solicitar recomendaciones.
- La muestra actual contiene 50 contextos únicos de la partición de validación
  de ACL-200, exportados en `data/processed/dashboard_insights.json` por
  `compute_examples` de `src/training/build_insights.py`. El endpoint aleatorio
  anterior ya usaba esa muestra; la nueva interfaz permite escogerla.
- Los textos conservan `TARGETCIT`, `OTHERCIT` y posibles cortes del fragmento
  original. Al elegir uno se explica que `TARGETCIT` señala la cita original.
  Son ejemplos de demostración, no una evaluación nueva ni un Test Gold humano.
- La nota «Revisa el artículo antes de citarlo» aparece junto a los resultados,
  no antes de realizar la primera consulta.

### 4.5 Tabla de recomendaciones

La sección de resultados **no existe antes de la primera consulta**. Al pulsar
Recomendar, la sección aparece debajo del formulario con un esqueleto de carga.
La página se desplaza hasta ella y el foco pasa a su encabezado.

| Columna | Origen | Notas |
|---|---|---|
| # | `posicion` | Números tabulares |
| Título | `titulo` | Texto completo con ajuste de línea. Si viene vacío: «(sin título)» |
| ID | `paper_id` | En fuente de ancho fijo |
| Puntaje | `similitud` | 3 decimales. El encabezado muestra la etiqueta `puntaje.etiqueta` del modelo, con su descripción en un tooltip |
| TF-IDF | `similitud_tfidf` | 3 decimales. Se oculta si el modelo no la devuelve |
| Acciones | — | Expandir resumen; copiar referencia APA 7 |

Comportamiento:

- Encabezado de la sección: «Recomendaciones · N artículos · [nombre del modelo]».
- Orden inicial por `posicion`. Las columnas #, Puntaje y TF-IDF se pueden
  ordenar con clic o teclado (`aria-sort`). Ordenar no altera la posición
  original, que sigue visible.
- Cada fila se expande para mostrar el `resumen` completo, o «Este artículo no
  tiene resumen». Por defecto aparece expandida la primera fila.
- Los resultados de ejemplos se presentan como cualquier consulta, sin etiquetas
  de «cita correcta» ni mensajes de evaluación del modelo.
- **Copiar referencia APA 7** consulta los metadatos oficiales de ACL Anthology
  por ID mediante `GET /api/referencias/{paper_id}` y formatea una referencia
  bibliográfica con autores, fecha, título y fuente según los datos disponibles.
  No copia únicamente el ID ni infiere autores/año a partir del identificador.
- Se utiliza Citation.js con su plantilla APA 7 y localización española. Conserva
  el DOI cuando existe y aplica las reglas de datos ausentes sin inventarlos.
  La biblioteca se carga solo al copiar; las recomendaciones no dependen de esa
  consulta externa.
- El portapapeles incluye texto plano y, cuando el navegador lo permite, HTML
  para conservar las cursivas. Se confirma «Referencia APA 7 copiada». Si el
  navegador bloquea la escritura, se muestra la misma referencia seleccionable
  para copiar manualmente. Si falla la fuente, se informa y permite reintentar.
- El API verifica que el ID pertenezca al corpus del modelo, consulta únicamente
  el BibTeX oficial y cachea las respuestas válidas en memoria. No modifica el
  wheel ni descarga metadatos durante el arranque.

### 4.6 Estados de la vista Recomendar

| Estado | Qué ve la persona |
|---|---|
| Inicial | Formulario sin la sección de resultados |
| Validación | Error junto al campo; no se llama al API |
| Consultando | Botón deshabilitado con «Buscando…» y esqueleto de 5 filas |
| Con resultados | Tabla (sección 4.5) |
| Sin resultados | «El modelo no encontró artículos parecidos a este texto. Prueba con un fragmento más largo o más específico» |
| 422 | El `detail` del backend junto al campo |
| 503 | «El modelo aún se está cargando. Inténtalo en unos segundos» y botón **Reintentar** |
| Modelo no disponible (404 o 409) | «El modelo elegido ya no está disponible»; se recarga la lista de modelos |
| Error de red | «No se pudo conectar con el servidor» y botón **Reintentar** |

Si una consulta termina después de que se lanzó otra más nueva, su respuesta se
descarta (cancelar con `AbortController`).

### 4.7 Vistas analíticas

`/datos`, `/modelo` y `/negativos` reproducen el contenido de las pestañas
actuales, a partir de `GET /api/insights`, con la nueva identidad visual. Los
datos se piden una sola vez, en la primera visita a cualquiera de estas vistas,
y se guardan en memoria durante la sesión. Mientras cargan se muestra un
esqueleto; si fallan, un mensaje con **Reintentar**.

## 5. Identidad visual y accesibilidad

- Los tokens de color y tipografía se toman de
  [identidad_visual.md](../identidad_visual.md) y se declaran como variables CSS
  en un único archivo `tokens.css`.
- Iconos de línea fina con trazo de 1,25 px en una cuadrícula de 24 px. Se usa
  el conjunto base del documento de identidad: buscar, documento, cita, enlace,
  filtro y guardar.
- Todo el texto normal cumple 4.5:1. El acento `#00A88F` solo se usa como
  relleno, con texto `#121826`.
- Todos los controles se pueden usar con teclado y tienen un foco visible.
- La tabla usa `<table>`, `<th scope>` y `<caption>`. Los mensajes de estado y
  error se anuncian con `aria-live="polite"`.
- Se respeta `prefers-reduced-motion` y se desactiva el desplazamiento suave.
- La interfaz está en español, con `lang="es"` en el documento; el campo de
  contexto lleva `lang="en"`.

## 6. Contrato con el backend

El API actual ya ofrece recomendaciones, ejemplos, estado e insights.
`GET /api/modelos` y el campo `modelo` están implementados en esta rama;
requieren publicar la nueva imagen del API para estar disponibles en ECS. La conexión entre orígenes se define en §3.2–3.3.

### 6.1 Nuevo: `GET /api/modelos`

```json
{
  "predeterminado": "tfidf_reranker_v1",
  "modelos": [
    {
      "id": "tfidf_reranker_v1",
      "nombre": "TF-IDF + reordenador lineal",
      "descripcion": "Recupera 100 candidatos con TF-IDF y los reordena con regresión logística.",
      "disponible": true,
      "motivo": null,
      "puntaje": {
        "etiqueta": "Puntaje del reordenador",
        "descripcion": "Salida estimada para ordenar candidatos; no garantiza que la referencia sea correcta."
      },
      "devuelve_tfidf": true
    }
  ]
}
```

- `id` es estable y es lo que se envía al recomendar.
- `puntaje` existe porque el número de cada modelo significa cosas distintas: un
  coseno TF-IDF no es una probabilidad. La interfaz no compara puntajes entre
  modelos.
- El backend decide qué modelos lista: por ejemplo, la línea base TF-IDF y los
  reordenadores definidos en `config/model*.yaml`, si su artefacto está
  disponible.

### 6.2 Cambios en `POST /api/recomendar`

Petición. El campo `modelo` es nuevo y opcional:

```json
{ "contexto": "…", "top_k": 10, "modelo": "tfidf_reranker_v1" }
```

Respuesta. El campo `modelo` es nuevo y repite el modelo que se usó de verdad:

```json
{
  "consulta": "…",
  "modelo": "tfidf_reranker_v1",
  "total": 10,
  "recomendaciones": [
    {
      "posicion": 1,
      "paper_id": "P05-1022",
      "titulo": "…",
      "resumen": "…",
      "similitud": 0.9123,
      "similitud_tfidf": 0.3412
    }
  ]
}
```

- Sin `modelo`, se usa el predeterminado. Así el cambio es compatible con el
  tablero actual.
- Si el `modelo` no existe: 404. Si existe pero no está cargado: 409. En ambos
  casos `detail` lleva un mensaje legible.
- `similitud_tfidf` puede faltar en modelos que no la calculan.

### 6.3 Nuevo: `GET /api/ejemplos`

Devuelve `total`, `particion` y `ejemplos`; cada ejemplo conserva `context_id`,
`texto`, `cita_correcta` y `titulo_correcto` del JSON exportado. La partición
actual es `val`. Sin datos cargados responde 503; una lista vacía no impide
escribir un contexto propio. No modifica el endpoint aleatorio existente.

### 6.4 Sin cambios

- `GET /api/estado`
- `GET /api/ejemplo`, que devuelve `texto`, `cita_correcta` y `titulo_correcto`
- `GET /api/insights`

## 7. Criterios de aceptación

- [ ] Con el backend listo, pegar un texto en inglés, elegir un modelo y pulsar
      Recomendar muestra la tabla con N filas ordenadas por posición.
- [ ] La tabla no aparece antes de la primera consulta.
- [ ] El selector está junto al título, muestra el catálogo y recuerda la
      elección; su ayuda explica el modelo y puede abrirse/cerrarse con teclado.
- [ ] Si `GET /api/modelos` falla, la recomendación sigue funcionando con el
      modelo predeterminado.
- [ ] Con el campo vacío no se llama al API y se muestra el error junto al campo.
- [ ] `Ctrl/Cmd+Enter` envía la consulta.
- [ ] El modal permite usar distintos ejemplos reales sin alterar sus textos;
      los resultados no muestran etiquetas ni avisos de evaluación.
- [ ] Ante un 503 o un error de red se muestra el mensaje y Reintentar funciona.
- [ ] Una respuesta antigua nunca reemplaza a una más nueva.
- [ ] Las vistas `/datos`, `/modelo` y `/negativos` se abren por URL directa y
      muestran el mismo contenido que el tablero actual.
- [ ] Toda la interfaz se puede usar con teclado, y los pares de color de texto
      cumplen 4.5:1.
- [ ] A 375 px de ancho no hay desplazamiento horizontal y los resultados se
      muestran como tarjetas.
- [ ] La aplicación se desarrolla y compila desde `frontend/`, sin depender
      de los archivos HTML/JS del tablero anterior.
- [ ] Vite permite trabajar contra FastAPI local; la configuración de producción
      consume el API de ECS mediante su URL pública configurable.
- [ ] La URL HTTPS de CloudFront sirve la aplicación desde S3 privado; el
      contenido del bucket no es accesible públicamente de forma directa.
- [ ] La apertura directa y recarga de `/datos`, `/modelo` y `/negativos`
      funciona desde CloudFront; un asset inexistente no devuelve `index.html`.
- [ ] Desde el navegador en CloudFront funciona una recomendación real, incluido
      el preflight JSON, y los errores del API se muestran sin bloqueo CORS.
- [ ] Publicar una versión nueva actualiza la interfaz sin reconstruir ECS ni
      romper los assets de una sesión abierta.
- [ ] La configuración compilada no contiene credenciales ni una URL de
      laboratorio fija en los componentes.
- [ ] Hay pruebas de componentes para el formulario, la tabla y los estados de
      error (Vitest + Testing Library), y pruebas del backend para
      `/api/modelos` y el campo `modelo`.

## 8. Decisiones de la primera implementación

- Solo se expone TF-IDF + reordenador lineal del wheel instalado. Su carga
  continúa al arrancar FastAPI; los YAML de experimentos no se anuncian como modelos.
- Las vistas analíticas conservan los datos del experimento original y lo
  explican; no cambian al elegir un modelo de recomendación.
- Las gráficas son componentes SVG de React, sin dependencia externa de gráficas,
  con tablas de datos alternativas para las distribuciones.
- La ruta `/fragmentos` incorpora Top-3 manual mediante el endpoint BM25 existente:
  contexto, ID y párrafos de un único artículo. Incluye un ejemplo sintético
  identificado como tal; no promete descargar artículos ni corpus ausente.
- La clasificación de nueve funciones se presenta como no disponible hasta
  integrar un modelo validado. No se fabrican etiquetas o resultados.
- El tablero anterior continúa disponible. Comparar modelos simultáneamente
  y retirar esa interfaz quedan fuera de esta versión.
- Los recursos son portables entre cuentas. La infraestructura se prepara con
  Terraform y se desplegará en la cuenta elegida por José; no se fija el endpoint
  del laboratorio en componentes ni se asume LabRole para el frontend.

## 9. Verificación y pendientes

Verificado localmente: build TypeScript/Vite, quince pruebas de componentes/API
cliente, pruebas del backend y dos recorridos de navegador (escritorio y 375 px).
Se probaron tres ejemplos reales de React a FastAPI con el modelo instalado,
con diez recomendaciones por consulta y sin errores de JavaScript. Ambos stacks
pasan `terraform validate`; las rutas de CloudFront tienen pruebas sin AWS.

Pendiente: publicar la imagen actualizada del API, crear S3/CloudFront en la
cuenta elegida, aplicar CORS y verificar desde la URL pública. La clasificación
de nueve funciones sigue dependiendo de #103. Estos pendientes no se consideran
cumplidos por el build o las pruebas de navegador con transporte controlado.
