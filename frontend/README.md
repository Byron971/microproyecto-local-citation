# Aplicación de citas académicas

La web tiene un único recorrido: contexto de cita → artículo citado → clasificador → resultados.
Recupera tres fragmentos del artículo confirmado y muestra la función de cita predicha.
Usa React, Vite, TypeScript, Outfit y DM Sans; las fuentes se incluyen en el build.

## Desarrollo local

```sh
npm --prefix frontend ci
npm --prefix frontend run dev
```

Vite sirve la web en `http://127.0.0.1:5173`. Envía `/api/analisis-cita-ms`
al servicio científico en el puerto 8001 y las demás rutas `/api` al servicio
ligero en el puerto 8000. Los modelos y el corpus deben estar preparados para
usar inferencia local; el frontend no los descarga.

Para usar otra API, configura `VITE_API_BASE_URL` en `frontend/.env.local`
y reinicia Vite. La API debe permitir el origen local en CORS. Las variables
`VITE_*` son públicas y no deben contener credenciales.

## Recorrido actual

1. Introducir un contexto en inglés con una única marca `TARGETCIT`, o explorar
   los 40 ejemplos de validación de ocho temas. Los ejemplos no ejecutan inferencia.
2. Buscar por título o ID, revisar las sugerencias SciBERT y confirmar un artículo.
   El catálogo contiene 19.776 artículos; 19.243 tienen texto preparado.
3. Elegir M, S o el clasificador comercial. El comercial requiere consentimiento
   antes de enviar contexto y metadatos a OpenAI.
4. Consultar el Top-3 del artículo confirmado, las puntuaciones de función,
   los detalles del análisis y la explicación de las nueve funciones.

M/S inicia un trabajo con un único POST y consulta su estado mediante GET.
No se repite la inferencia al consultar resultados. Las puntuaciones no
constituyen probabilidades calibradas de acierto ni una validación científica.
Las rutas de las pantallas anteriores redirigen al recorrido actual.

## Verificación

```sh
npm --prefix frontend test
npm --prefix frontend run build
npm --prefix frontend run test:e2e
```

Las pruebas habituales de interfaz usan mocks y cubren escritorio y móvil.
Los archivos de pruebas reales requieren activación explícita; no deben
activarse para comprobar presentación, especialmente los del proveedor comercial.
Se puede indicar un navegador instalado mediante
`PLAYWRIGHT_CHROMIUM_EXECUTABLE=/ruta/al/ejecutable`.

La publicación utiliza `make publish-frontend`. Los cambios de presentación
no requieren reconstruir imágenes de backend ni modelos.
