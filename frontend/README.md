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

## Publicar en cualquier cuenta AWS

El API debe estar desplegado antes. Para habilitar el selector, publica la
versión del API de esta rama, que incorpora `/api/modelos`, `/api/ejemplos`
y `/api/referencias/{paper_id}`. Con el API anterior
la interfaz puede usar el modelo predeterminado como alternativa. En la cuenta elegida necesitas un bucket
para el estado, permisos S3/CloudFront y permisos para modificar CORS de API
Gateway. El stack de frontend no crea roles IAM ni modifica ECS.

Configura el perfil de la cuenta y el bucket del estado existente:

```sh
export AWS_PROFILE=mi-cuenta
export AWS_REGION=us-east-1
export TF_STATE_BUCKET=mi-bucket-de-estado
cp terraform/frontend/terraform.tfvars.example terraform/frontend/terraform.tfvars
```

Edita el ejemplo: indica región, nombre del proyecto y `api_base_url` de tu API.
El bucket web se nombra automáticamente con proyecto, cuenta y región. Su estado
usa una key distinta de la del API; no reutilices la key de ECS.

```sh
terraform -chdir=terraform/frontend init \
  -backend-config="bucket=$TF_STATE_BUCKET" \
  -backend-config="region=$AWS_REGION"
terraform -chdir=terraform/frontend plan
terraform -chdir=terraform/frontend apply
terraform -chdir=terraform/frontend output -raw frontend_url
```

En `terraform/terraform.tfvars` del API agrega la URL de CloudFront obtenida,
sin barra final, a `cors_allowed_origins`. Conserva los otros orígenes que uses.
Para probar el API remoto desde desarrollo también puedes incluir
`http://localhost:5173` y `http://127.0.0.1:5173`.

```hcl
cors_allowed_origins = ["https://TU_DISTRIBUCION.cloudfront.net"]
```

Si usas GitHub Actions para desplegar el API o Terraform, configura también
la variable de repositorio `CORS_ALLOWED_ORIGINS` con el mismo array JSON
(por ejemplo `["https://TU_DISTRIBUCION.cloudfront.net"]`). Así, un apply de CI
no elimina los orígenes definidos solo en tu tfvars local.

Aplica CORS en el stack del API, con su backend inicializado en la cuenta correcta:

```sh
terraform -chdir=terraform plan
terraform -chdir=terraform apply
bash scripts/publicar_frontend.sh
```

El script obtiene la URL del API del output de Terraform, compila, sube primero
los assets y después `index.html`, y solicita su invalidación. No borra los assets
con hash de versiones anteriores para que las sesiones abiertas sigan funcionando.
La creación de CloudFront y sus invalidaciones pueden tardar varios minutos.

## Verificar

Abre la URL CloudFront. Usa un ejemplo y solicita recomendaciones; comprueba
que `/datos`, `/modelo`, `/negativos` y `/fragmentos` se abren directamente y
al recargar. Confirma en Network del navegador el preflight y las llamadas al
API. Un asset inexistente debe devolver un error, no HTML de la aplicación.
El bucket es privado y no sirve el sitio directamente.

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

El workflow `frontend.yml` valida UI e infraestructura sin secretos. El workflow
`publicar-frontend.yml` permite publicar manualmente desde main después de crear
el stack y configurar CORS. Necesita los secrets `AWS_ACCESS_KEY_ID`,
`AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` si son temporales, y las variables
públicas `TF_STATE_BUCKET`, `API_BASE_URL`, `AWS_REGION` (opcional, us-east-1) y
`PROJECT_NAME` (opcional, citas-api). El bucket del estado debe estar en la región
configurada. Estos valores deben coincidir con tu despliegue local.

## Caché y eliminación

CloudFront reescribe las rutas de aplicación antes de S3; los errores de assets
no se convierten en 200. Los documentos no se cachean en CloudFront y los assets
con hash admiten caché de un año. Las llamadas al API van directamente a API
Gateway, sin caché de CloudFront.

El stack no crea dominios personalizados. Para eliminarlo hay que vaciar primero
su bucket web y ejecutar `terraform -chdir=terraform/frontend destroy`.
El estado, el bucket del API y ECS son independientes. No hay limpieza automática
para evitar borrar un despliegue por error; CloudFront y S3 pueden generar cargos.

## Origen de los ejemplos

El selector usa los 50 contextos de validación (`val`) ya publicados en
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
