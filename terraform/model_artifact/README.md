# Paquete M/S para T04

Este estado gestiona exclusivamente el objeto model.tar.gz de T04 en el bucket
privado existente. Se ejecuta en EC2, donde está el archivo de 1,64 GB. El backend
S3 usa una ruta propia y bloqueo nativo; no comparte el estado de producción.

Desde el equipo de control:

```sh
make builder-publish-models AWS_PROFILE=josezambrana
make builder-publish-models-result AWS_PROFILE=josezambrana
```

El script comprueba identidad y procedencia del paquete, rechaza una ruta con
versiones previas sin estado propio, descarga Terraform con checksum oficial,
valida que el plan solo cree este objeto y verifica el SHA256 leyendo la copia
publicada completa. No crea el endpoint. Informe: /opt/citas/models/published-models.json.
Log: /opt/citas/publish-models.log.

El endpoint de terraform/serverless_ms_probe consulta este objeto como dato;
no debe importar ni administrar este archivo en su propio estado.
Para retirarlo, preparar y revisar un plan destroy de ESTE módulo en EC2 a
través de Makefile. Eliminar el constructor no elimina el objeto ni su estado.
