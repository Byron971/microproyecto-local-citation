# Manual de instalación

## Sistema de recomendación local de citas académicas

Este documento explica cómo instalar y ejecutar desde cero el sistema de recomendación local de citas académicas desarrollado para el proyecto.

La solución puede ejecutarse de dos formas:

1. Localmente mediante Python y uv.
2. Mediante contenedores Docker utilizando Docker Compose.

El sistema está compuesto por:

- un modelo de recomendación basado en TF-IDF y un reordenador lineal;
- un paquete instalable denominado `modelo-citas`;
- una API desarrollada con FastAPI;
- un tablero web;
- datos versionados mediante DVC;
- contenedores Docker para API y dashboard.

---

# 1. Requisitos previos

## 1.1 Requisitos generales

Se requiere tener instalado:

- Git
- conexión a Internet
- uv
- Docker, si se desea ejecutar la versión contenerizada
- Docker Compose

Python no necesita instalarse manualmente si se utiliza uv, ya que uv administra la versión requerida por el proyecto.

El proyecto requiere Python 3.14 o superior.

---

# 2. Comprobar las herramientas instaladas

Abrir una terminal y ejecutar:

```bash
git --version
```

Debe mostrarse una versión de Git.

Comprobar uv:

```bash
uv --version
```

Para utilizar Docker:

```bash
docker --version
docker compose version
```

Si los cuatro comandos responden correctamente, el equipo está preparado para continuar.

---

# 3. Instalar uv

Si uv todavía no está instalado, utilizar uno de los siguientes métodos.

## Windows PowerShell

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Cerrar y volver a abrir PowerShell después de instalarlo.

Comprobar:

```powershell
uv --version
```

## Linux o macOS

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Comprobar:

```bash
uv --version
```

---

# 4. Clonar el repositorio

Ejecutar:

```bash
git clone https://github.com/Byron971/microproyecto-local-citation.git
cd microproyecto-local-citation
```

Comprobar la rama:

```bash
git branch --show-current
```

La rama esperada para una instalación normal es:

```text
main
```

---

# 5. Instalar las dependencias

Desde la raíz del repositorio ejecutar:

```bash
uv sync
```

Este comando crea el entorno virtual e instala las dependencias definidas en:

```text
pyproject.toml
uv.lock
```

Para comprobar el entorno:

```bash
uv run python --version
```

---

# 6. Recuperar los datos con DVC

Los datos del proyecto no se almacenan directamente en Git.

El repositorio utiliza DVC para recuperar los archivos necesarios.

El remoto público utilizado para reproducción es:

```text
publico
```

Ejecutar:

```bash
uv run dvc pull -r publico
```

También puede utilizarse:

```bash
uv run dvc pull
```

porque `publico` se encuentra configurado como remoto predeterminado.

Comprobar el estado:

```bash
uv run dvc status
```

Los principales archivos esperados dentro de:

```text
data/raw/
```

son:

```text
contexts.json
papers.json
train.json
val.json
test.json
```

---

# 7. Ejecutar las pruebas del proyecto

Antes de generar el modelo es recomendable validar la instalación.

Ejecutar:

```bash
uv run pytest
```

En la versión validada durante la Entrega 3 la suite contiene 96 pruebas.

El resultado esperado es:

```text
96 passed
```

Pueden aparecer advertencias de deprecación relacionadas con algunas dependencias. Estas advertencias no representan fallos si todas las pruebas terminan correctamente.

---

# 8. Generar el modelo empaquetado

El archivo del modelo entrenado no se almacena directamente en Git.

Debe generarse utilizando el pipeline del paquete `modelo-citas`.

Ejecutar desde la raíz del repositorio:

```bash
uv run tox -c model-package -e train
```

El artefacto generado se almacena dentro de:

```text
model-package/modelo_citas/trained/
```

El nombre esperado sigue la versión del paquete, por ejemplo:

```text
modelo-citas-output0.1.0.pkl
```

Después de generar el modelo, reinstalar el paquete:

```bash
uv sync --reinstall-package modelo-citas
```

---

# 9. Comprobar el paquete del modelo

Puede comprobarse que el paquete es importable mediante:

```bash
uv run python -c "import modelo_citas; print('modelo-citas instalado correctamente')"
```

Si aparece:

```text
modelo-citas instalado correctamente
```

el paquete está disponible en el entorno.

---

# 10. Ejecutar la solución localmente

La aplicación local sirve tanto el tablero como la API.

Ejecutar:

```bash
uv run tablero
```

Durante el arranque se carga:

- el recuperador TF-IDF;
- el reordenador lineal;
- el corpus de artículos;
- la información utilizada por el tablero.

Cuando el servidor esté disponible, abrir en el navegador:

```text
http://127.0.0.1:8000
```

---

# 11. Acceder al tablero

Abrir:

```text
http://127.0.0.1:8000
```

Desde el tablero es posible:

- escribir un contexto académico;
- utilizar un ejemplo real del corpus;
- solicitar recomendaciones;
- seleccionar la cantidad de resultados;
- consultar títulos y resúmenes;
- visualizar información del modelo;
- consultar análisis de los datos;
- consultar métricas de desempeño;
- revisar el diagnóstico de negativos.

El manual de uso detallado se encuentra en:

```text
docs/manual_usuario.md
```

---

# 12. Comprobar la API

Con el servidor local ejecutándose, abrir:

```text
http://127.0.0.1:8000/docs
```

FastAPI mostrará la documentación Swagger/OpenAPI.

Los principales endpoints son:

```text
GET  /api/estado
GET  /api/insights
GET  /api/ejemplo
POST /api/recomendar
```

Para comprobar el estado directamente desde el navegador:

```text
http://127.0.0.1:8000/api/estado
```

La respuesta debe indicar que el modelo se encuentra listo.

---

# 13. Detener la ejecución local

En la terminal donde está ejecutándose:

```text
uv run tablero
```

presionar:

```text
Ctrl + C
```

---

# 14. Ejecución mediante Docker

La solución también puede ejecutarse utilizando contenedores.

Se utilizan dos servicios:

```text
api
dashboard
```

Los archivos principales son:

```text
Dockerfile
Dockerfile.dashboard
docker-compose.yml
nginx.conf
```

---

# 15. Validar la configuración de Docker Compose

Antes de construir las imágenes ejecutar:

```bash
docker compose config --quiet
```

Si el comando no muestra errores, la configuración de Compose es válida.

---

# 16. Construir las imágenes

Desde la raíz del repositorio ejecutar:

```bash
docker compose build
```

La construcción puede tardar varios minutos.

Durante el build de la API se realizan automáticamente las siguientes tareas:

1. instalación de uv;
2. instalación de dependencias;
3. copia del proyecto;
4. recuperación de datos mediante DVC;
5. generación del modelo entrenado;
6. reinstalación del paquete `modelo-citas`;
7. preparación de FastAPI.

Las imágenes generadas son:

```text
microproyecto-citas-api:0.1.0
microproyecto-citas-dashboard:0.1.0
```

---

# 17. Levantar los contenedores

Ejecutar:

```bash
docker compose up -d
```

Docker iniciará primero la API.

El dashboard espera a que la API pase su comprobación de salud antes de iniciar completamente.

---

# 18. Comprobar el estado de los contenedores

Ejecutar:

```bash
docker compose ps
```

El resultado esperado debe ser similar a:

```text
microproyecto-citas-api        Up (...) (healthy)
microproyecto-citas-dashboard  Up (...)
```

La API debe aparecer como:

```text
healthy
```

---

# 19. Acceder al dashboard contenerizado

Abrir:

```text
http://127.0.0.1:8080
```

El dashboard es servido mediante Nginx.

Dentro de Docker, Nginx redirige las solicitudes:

```text
/api/*
```

hacia:

```text
http://api:8000
```

La comunicación entre dashboard y API se realiza por la red interna de Docker Compose.

---

# 20. Acceder directamente a la API contenerizada

La API también se publica en el equipo host mediante:

```text
http://127.0.0.1:8000
```

Para comprobar su estado:

```text
http://127.0.0.1:8000/api/estado
```

Para abrir Swagger:

```text
http://127.0.0.1:8000/docs
```

---

# 21. Consultar los logs

Logs de todos los servicios:

```bash
docker compose logs
```

Logs recientes:

```bash
docker compose logs --no-color --tail=40 api dashboard
```

Logs únicamente de la API:

```bash
docker compose logs api
```

En Linux, para comprobar solicitudes de recomendación:

```bash
docker compose logs --no-color api | grep "POST"
```

En Windows PowerShell puede utilizarse:

```powershell
docker compose logs --no-color api | Select-String "POST"
```

Después de realizar una recomendación desde el tablero debería aparecer una línea similar a:

```text
POST /api/recomendar HTTP/1.1" 200 OK
```

---

# 22. Detener los contenedores

Ejecutar:

```bash
docker compose down
```

Esto detiene y elimina los contenedores creados por Compose.

Las imágenes Docker permanecen disponibles.

---

# 23. Reiniciar los servicios

Para volver a iniciar los servicios:

```bash
docker compose up -d
```

Comprobar:

```bash
docker compose ps
```

---

# 24. Puertos utilizados

La configuración actual utiliza los siguientes puertos:

| Servicio | Puerto interno | Puerto del host | Función |
|---|---:|---:|---|
| Dashboard / Nginx | 80 | 8080 | Interfaz web |
| FastAPI | 8000 | 8000 | API |
| MLflow remoto | 8050 | 8050 | Seguimiento experimental |

Para ejecución local sin Docker:

```text
http://127.0.0.1:8000
```

Para el dashboard con Docker:

```text
http://127.0.0.1:8080
```

---

# 25. Variables de entorno

La API y el dashboard no requieren variables de entorno obligatorias para funcionar con la configuración estándar del proyecto.

Para entrenamiento y seguimiento experimental puede utilizarse:

```text
MLFLOW_TRACKING_URI
```

Ejemplo en Windows PowerShell:

```powershell
$env:MLFLOW_TRACKING_URI="http://<IP_SERVIDOR>:8050"
```

Ejemplo en Linux:

```bash
export MLFLOW_TRACKING_URI=http://<IP_SERVIDOR>:8050
```

Si esta variable no está configurada, MLflow utiliza el backend local definido por el proyecto.

---

# 26. Credenciales y archivos sensibles

Nunca deben almacenarse en Git:

```text
.env
*.pem
*.ppk
```

Las credenciales de AWS Academy son temporales y no deben copiarse dentro del repositorio.

Las claves privadas utilizadas para acceder a EC2 deben mantenerse únicamente en el equipo del usuario.

---

# 27. Despliegue en una instancia EC2

La solución fue validada en una instancia AWS EC2 con:

```text
Sistema operativo: Ubuntu Server 24.04 LTS
Tipo de instancia: t3.small
Almacenamiento: 20 GiB gp3
Orquestación: Docker Compose
```

Después de conectarse a la instancia mediante SSH, instalar Git y Docker.

Actualizar los repositorios:

```bash
sudo apt update
```

Instalar Git:

```bash
sudo apt install -y git
```

Instalar Docker y Docker Compose:

```bash
sudo apt install -y docker.io docker-compose-v2
```

Agregar el usuario actual al grupo Docker:

```bash
sudo usermod -aG docker $USER
```

Cerrar la sesión SSH:

```bash
exit
```

y volver a conectarse para aplicar el nuevo grupo.

Comprobar:

```bash
docker --version
docker compose version
git --version
```

---

# 28. Clonar el proyecto en EC2

Ejecutar:

```bash
git clone https://github.com/Byron971/microproyecto-local-citation.git
cd microproyecto-local-citation
```

Comprobar:

```bash
git branch --show-current
```

Debe indicar:

```text
main
```

---

# 29. Construir y ejecutar en EC2

Validar Compose:

```bash
docker compose config --quiet
```

Construir:

```bash
docker compose build
```

Iniciar:

```bash
docker compose up -d
```

Comprobar:

```bash
docker compose ps
```

La API debe aparecer en estado:

```text
healthy
```

y el dashboard debe aparecer activo.

---

# 30. Configuración de red en AWS

Para utilizar la aplicación desde un navegador externo, el grupo de seguridad de EC2 debe permitir el tráfico necesario.

La configuración mínima recomendada es:

```text
TCP 22    SSH
TCP 8080  Dashboard
```

El puerto 22 debe limitarse a una dirección IP de administración conocida.

El puerto 8080 debe configurarse según el entorno desde el cual se realizará la demostración.

El puerto 8000 no necesita estar expuesto públicamente para que el dashboard funcione, porque Nginx se comunica con la API utilizando la red interna de Docker Compose.

El puerto 8050 únicamente es necesario si se utiliza un servidor MLflow remoto.

---

# 31. Acceder al sistema desplegado en EC2

Consultar la IP pública actual de la instancia.

Abrir:

```text
http://<IP_PUBLICA_EC2>:8080
```

La dirección puede cambiar cuando una instancia de AWS Academy se detiene y vuelve a iniciarse.

Por esta razón no debe almacenarse una IP pública fija dentro del código.

---

# 32. Validar una recomendación real en EC2

Abrir:

```text
http://<IP_PUBLICA_EC2>:8080
```

Pulsar:

```text
Usar un ejemplo real
```

Después pulsar:

```text
Recomendar citas
```

El tablero debe mostrar una lista ordenada de artículos candidatos.

En la terminal de EC2 ejecutar:

```bash
docker compose logs --no-color api | grep "POST"
```

Debe aparecer una respuesta similar a:

```text
POST /api/recomendar HTTP/1.1" 200 OK
```

Esto confirma el flujo:

```text
Navegador
    ↓
Dashboard / Nginx
    ↓
API FastAPI
    ↓
modelo-citas
    ↓
respuesta
```

---

# 33. Solución de errores frecuentes

## Error: `uv` no se reconoce

Cerrar y volver a abrir la terminal después de instalar uv.

Comprobar:

```bash
uv --version
```

Si sigue sin funcionar, revisar que uv se encuentre incluido en la variable `PATH`.

---

## Error durante `dvc pull`

Ejecutar explícitamente:

```bash
uv run dvc pull -r publico
```

Comprobar la configuración:

```bash
uv run dvc remote list
```

Debe aparecer el remoto:

```text
publico
```

---

## Error: no se encuentra el modelo entrenado

Si aparece un error indicando que falta:

```text
modelo-citas-output0.1.0.pkl
```

ejecutar:

```bash
uv run tox -c model-package -e train
uv sync --reinstall-package modelo-citas
```

Después volver a iniciar:

```bash
uv run tablero
```

---

## Error: el puerto 8000 está ocupado

Comprobar si existe otra instancia de la API o del tablero ejecutándose.

Si Docker está activo:

```bash
docker compose ps
```

Detener los servicios:

```bash
docker compose down
```

Después intentar nuevamente.

---

## Error: el puerto 8080 está ocupado

Comprobar los contenedores:

```bash
docker compose ps
```

Detenerlos:

```bash
docker compose down
```

y volver a iniciar.

---

## Error: Docker no tiene permisos en Ubuntu

Si aparece:

```text
permission denied
```

al utilizar Docker, comprobar que el usuario pertenezca al grupo `docker`:

```bash
groups
```

Si `docker` no aparece:

```bash
sudo usermod -aG docker $USER
```

Cerrar la sesión:

```bash
exit
```

y volver a conectarse mediante SSH.

---

## Error: la API aparece como `unhealthy`

Consultar:

```bash
docker compose ps
```

y después:

```bash
docker compose logs --no-color --tail=100 api
```

Buscar errores relacionados con:

- recuperación de datos;
- modelo entrenado;
- dependencias;
- carga de FastAPI.

---

## Error: el dashboard carga pero no recomienda

Comprobar primero:

```bash
docker compose ps
```

La API debe aparecer como:

```text
healthy
```

Consultar los logs:

```bash
docker compose logs --no-color --tail=100 api dashboard
```

También puede comprobarse directamente:

```text
http://127.0.0.1:8000/api/estado
```

En EC2, no es necesario publicar el puerto 8000 si únicamente se utiliza el dashboard.

---

## Error: no se puede abrir el dashboard en EC2

Comprobar:

```bash
docker compose ps
```

Después verificar que el grupo de seguridad de EC2 permita TCP 8080 desde la dirección de origen correspondiente.

También comprobar que se esté utilizando la IP pública actual de la instancia.

---

## Error después de reiniciar AWS Academy

La IP pública de la instancia puede cambiar.

Consultar nuevamente la dirección IPv4 pública desde la consola EC2.

Para MLflow remoto también deberá utilizarse la IP pública actual del servidor correspondiente.

---

# 34. Comprobación final de instalación

Una instalación completa debe superar las siguientes verificaciones:

```bash
git branch --show-current
uv run dvc status
uv run pytest
```

Para Docker:

```bash
docker compose config --quiet
docker compose build
docker compose up -d
docker compose ps
```

El resultado final esperado es:

```text
Rama: main
Datos DVC disponibles
96 pruebas aprobadas
API: healthy
Dashboard: activo
```

Finalmente debe ser posible abrir el tablero y realizar una recomendación real.

---

# 35. Limpieza

Para detener la solución contenerizada:

```bash
docker compose down
```

Para consultar el espacio utilizado por Docker:

```bash
docker system df
```

No se recomienda ejecutar comandos de eliminación global de imágenes o volúmenes en equipos que contengan otros proyectos Docker sin revisar previamente su contenido.

---

# 36. Documentación relacionada

Manual de usuario:

```text
docs/manual_usuario.md
```

README principal:

```text
README.md
```

Reporte de la Entrega 3:

```text
reportes/reporte03/
```

Código de la aplicación:

```text
src/app/
```

Paquete del modelo:

```text
model-package/
```

---

# 37. Estado de validación

Este manual describe el flujo reproducible utilizado por el proyecto.

Antes de cerrar definitivamente el issue de instalación, las instrucciones serán ejecutadas nuevamente desde un entorno limpio durante la auditoría final para comprobar que una persona externa puede reproducir la solución sin depender del entorno de desarrollo original.
