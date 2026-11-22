# Constructor EC2 de imágenes

Instancia aislada Ubuntu 24.04 AMD64 t3.large, disco cifrado gp3 de 60 GB.
Reutiliza la red existente sin modificarla. Sin reglas de entrada; acceso SSM.
Llave privada local: private/maiag19.pem (0600, ignorada por Git).
La llave pública se registra en EC2; no hay SSH directo abierto.

Desde la raíz del repositorio:

```sh
make builder-status AWS_PROFILE=josezambrana
make builder-session AWS_PROFILE=josezambrana
```

La sesión interactiva requiere el plugin Session Manager en el equipo local.
Docker, Git y rclone se instalan por cloud-init. La instancia se apaga a las tres
horas del primer arranque satisfactorio. El apagado conserva el disco; no elimina
su costo. El estado Terraform es local e ignorado por Git: conservarlo para retirar.

Retiro explícito de este constructor (no de producción):

```sh
make builder-destroy-plan AWS_PROFILE=josezambrana
make builder-destroy AWS_PROFILE=josezambrana
```

Pendiente: publicar rama revisada, clonar commit, construir/publicar imagen,
recuperar M/S desde S3, autorizar rclone y comprobar el adaptador QLoRA.
No guardar tokens Microsoft en Git ni en parámetros SSM registrados.

Clonación por SSM, sin credenciales GitHub (repositorio público):

```sh
make builder-clone AWS_PROFILE=josezambrana
make builder-clone-result AWS_PROFILE=josezambrana
```

El comando fija el commit local actual, exige un repositorio remoto limpio y
comprueba ambos Dockerfiles. No construye ni publica imágenes. La copia está en
`/opt/citas/microproyecto-local-citation`, propiedad de ubuntu.
