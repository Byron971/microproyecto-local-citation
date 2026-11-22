# T05: recuperación de QLoRA

Estado: en curso; rclone requiere aprobación del administrador universitario.
Alternativa elegida por el usuario: navegador Firefox en EC2, pendiente de sesión
SharePoint y recuperación real.

El notebook existente identifica Qwen/Qwen2.5-7B-Instruct y LoRA r=16, alpha=32,
NF4 de cuatro bits. Esto es configuración del código, no prueba del adaptador.
No fija una revisión de la base. No ejecutar ninguna celda de entrenamiento.

Se prepara acceso desde EC2 mediante rclone y un túnel SSM de localhost:53682.
Microsoft solicita Files.Read.All, offline_access y User.Read, sin escritura.
La configuración y tokens permanecen fuera del repositorio en EC2, permisos
0600; nunca se incluyen en SendCommand, Git ni respuestas del comprobador.

Comandos desde la raíz:

```sh
make qlora-session-plugin AWS_PROFILE=josezambrana
make qlora-auth-start AWS_PROFILE=josezambrana
make qlora-auth-status AWS_PROFILE=josezambrana
make qlora-auth-tunnel AWS_PROFILE=josezambrana
make qlora-auth-check AWS_PROFILE=josezambrana
make qlora-auth-check-result AWS_PROFILE=josezambrana
```

El túnel debe permanecer abierto durante el inicio de sesión. Usar el enlace
AUTH_URL vigente en el navegador local. El proceso de autorización vence a los
30 minutos; comprobar estado antes de reiniciarlo. No copiar logs privados.

Criterios pendientes:

- Acceder a qlora_18000/qlora_citas_adapter_v1/ en SharePoint.
- Descargar adaptador, configuración, tokenizador y manifiestos disponibles.
- Registrar tamaños, SHA256 y procedencia, fuera de Git para los pesos.
- Verificar base y revisión; distinguir una revisión recuperada de una nueva
  revisión fijada para inferencia. No atribuir revisión histórica sin evidencia.
- Recuperar la base compatible y comprobar tokenizer y módulos del adaptador.
- Ejecutar una entrada sintética con el adaptador cargado y registrar su salida.

EC2 actual es CPU de 8 GB y no acredita capacidad para Qwen de 7B. La inferencia
requiere un destino compatible; no crear GPU ni aumentar memoria automáticamente
sin preparar primero el plan y disponer de los artefactos. No sustituir por Qwen
base ni declarar T05 completo solo por descargar el adaptador.

## Navegador directo en EC2

```sh
make qlora-browser-start AWS_PROFILE=josezambrana
make qlora-browser-status AWS_PROFILE=josezambrana
make qlora-browser-tunnel AWS_PROFILE=josezambrana
```

Con el túnel activo, abrir en el Mac:
http://127.0.0.1:6080/vnc.html?autoconnect=1&resize=scale

El usuario inicia sesión en Firefox dentro de EC2. Descargas:
/home/ubuntu/Downloads/qlora. Perfil y logs privados quedan fuera de Git en EC2.
Xvfb no escucha TCP, VNC y el visor escuchan solo en loopback; no se cambian
reglas de seguridad ni se publica el escritorio. El navegador respeta las
políticas de inicio de sesión, MFA y descarga de la universidad.

Tras descargar, inventariar sin cargar ni entrenar:

```sh
python3 scripts/auditar_adapter_qlora.py --root RUTA_ADAPTADOR --output RUTA_EXTERNA/inventario.json
```

El informe distingue base/revisión declaradas de revisión confirmada, y no
acredita inferencia. Si falta adapter_config.json o adapter_model.safetensors,
se detiene; no sustituye por Qwen base ni por resultados precalculados.
