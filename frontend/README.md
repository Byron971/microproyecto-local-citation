# Aplicación React

Interfaz nueva para el API de citas: recomendador de artículos, evidencia Top-3
y vistas del estudio original. Usa React, Vite y TypeScript, con Outfit y DM Sans
incluidas en el build; el navegador no necesita Google Fonts.

## Desarrollo local

Desde la raíz, inicia FastAPI en una terminal:

```sh
uv run tablero
```

En otra terminal, con Node 22.12 o superior:

```sh
npm --prefix frontend ci
npm --prefix frontend run dev
```

Abre `http://localhost:5173`. Vite envía `/api` al backend local en el puerto 8000. Para usar un API remoto, copia `frontend/.env.example` a
`frontend/.env.local`, asigna `VITE_API_BASE_URL=https://TU_API...` sin `/api` y
reinicia Vite. Ese API debe permitir el origen local en CORS. No uses
credenciales AWS en archivos `VITE_*`: son públicos.

## Estado del despliegue de esta integración

Este PR recupera el **frontend local** y sus pruebas desde el PR #156 y lo
conecta con el backend actual de `main`, sin reemplazar la configuración
segura de FastAPI. **No incorpora todavía el stack Terraform de CloudFront/S3
ni el workflow de publicación**: la URL pública del frontend no está verificada.

Para validar la interfaz, inicia la API y Vite como se indicó arriba.
No ejecutes `terraform apply`, `terraform destroy` ni publiques recursos
AWS desde este PR. La publicación requiere una revisión separada de IaC,
autorización explícita de costos, CI verde y smoke HTTPS externo.

La UI utiliza `/api/modelos`, `/api/ejemplos`,
`/api/referencias/{paper_id}`, `/api/recomendar` y `/api/top3-fragmentos`
del backend integrado, con el catálogo restringido al modelo existente.

## Verificar

Abre `http://localhost:5173`. Usa un ejemplo y solicita recomendaciones;
comprueba que `/datos`, `/modelo`, `/negativos` y `/fragmentos` se abren
al recargar. Confirma las llamadas al API por proxy de desarrollo.

La clasificación de nueve funciones sigue pendiente de un modelo integrado;
la interfaz lo indica y no inventa etiquetas. El catálogo solo publica el
TF-IDF + reordenador realmente instalado. Los YAML de experimentos no son
modelos adicionales. El tablero anterior de FastAPI se conserva.

## Pruebas

```sh
npm --prefix frontend test
npm --prefix frontend run build
cd frontend
npx playwright install chromium
npm run test:e2e
```

Las pruebas de navegador usan respuestas controladas para cubrir escritorio,
375 px y rutas directas. No prueban permisos AWS ni CORS desplegado. Para usar
un Chromium del equipo se admite `PLAYWRIGHT_CHROMIUM_EXECUTABLE=/ruta/al/binario`.

El workflow `frontend.yml` valida la UI sin secretos, incluyendo pruebas de
navegador con respuestas controladas. **No sustituye una prueba E2E contra un
backend real** ni certifica un despliegue AWS.

## Origen de los ejemplos

El modal usa los 50 contextos de validación (`val`) ya publicados en
`data/processed/dashboard_insights.json`. El generador `compute_examples` de
`src/training/build_insights.py` toma una muestra reproducible del dataset y
conserva texto, ID y cita original. No se agregan ejemplos sintéticos ni se
seleccionan según si el recomendador acierta. Los marcadores `TARGETCIT` y
`OTHERCIT`, y los cortes del fragmento, pertenecen al texto original exportado.

`/api/ejemplos` devuelve esa lista sin modificaciones. `/api/ejemplo` mantiene
su comportamiento aleatorio para clientes anteriores. Son ejemplos de uso;
no constituyen un nuevo conjunto de evaluación ni Gold de funciones de cita.

## Copiar referencias en APA 7

El botón de cada resultado copia la referencia bibliográfica, no el ID. El
corpus empaquetado solo contiene título y resumen, por lo que el API consulta
el BibTeX oficial de ACL Anthology al copiar, validando antes el ID contra el
corpus instalado. Se usa una caché en memoria de hasta 512 respuestas válidas
y un timeout de ocho segundos; los fallos se pueden reintentar.

Citation.js genera APA 7 (localización española), incluida la normalización de
títulos en inglés respetando mayúsculas protegidas del BibTeX. El portapapeles
incluye texto plano y HTML cuando es compatible. Si el navegador no permite
copiar, se ofrece el texto para copia manual. No se completa información por
inferencia ni se sustituyen fallos externos por referencias inventadas.

La copia requiere salida HTTPS del API a `aclanthology.org`; no requiere llaves
ni nuevos permisos IAM. La biblioteca de formato se descarga de forma diferida
solo al copiar. No se modifica el modelo ni se ralentiza su arranque.

Fuentes: [exportación bibliográfica de ACL Anthology](https://aclanthology.org/faq/bib/),
[Citation.js](https://github.com/citation-js/citation-js) y
[APA: información ausente](https://apastyle.apa.org/style-grammar-guidelines/references/missing-information).
