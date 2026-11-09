# Frontend estático

Stack independiente para S3 privado y CloudFront con OAC. La configuración es
portable entre cuentas: usa la identidad AWS activa, sin account ID fijo ni
referencias a LabRole. Requiere credenciales con permisos sobre estos servicios.
No crea el bucket del backend ni el API. Su key de estado es
`citas-frontend/terraform.tfstate`; usa una key propia por proyecto si despliegas
más de uno en la misma cuenta.

Los pasos de creación, CORS, publicación y verificación están en
[frontend/README.md](../../frontend/README.md).

`api_base_url` es configuración pública del build y no enruta el API por
CloudFront. Si el API vive en otra cuenta, la conexión funciona por HTTPS, pero
su dueño debe permitir el origen CloudFront en CORS.
