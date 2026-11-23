# Selector de ejemplos del dataset — 22 de noviembre de 2026

> Decisión posterior: se unifican las acciones en «Explorar ejemplos», con 40 artículos distintos de ocho subtemas y ayuda global en modal. Véase [ejemplos variados y ayuda](ejemplos_variados_ayuda_modal.md). Los 33 ejemplos y las dos acciones descritas abajo son estado histórico.

Ampliación de T03 solicitada por el usuario después de publicar T09.

Se conserva «Usar ejemplo público» y se añade «Explorar ejemplos del dataset».
El modal reutiliza ExampleDialog, permite buscar por contexto, título e IDs,
muestra el número de coincidencias y señala el ejemplo en uso. Elegir una cita
carga su contexto original con TARGETCIT y su artículo citado. No dispara una
inferencia: borra resultados anteriores y consentimiento, y consulta cobertura.
Escape, cierre y selección devuelven el foco; no alteran el modelo elegido.

## Procedencia y reproducción

frontend/src/scientificExamples.json contiene 33 contextos de validación ACL-200
correspondientes a nueve artículos del catálogo preparado. No contiene etiquetas
de función, predicciones, fragmentos precalculados ni casos TRAIN/test/Gold.
Los textos e IDs se contrastaron con data/raw/contexts.json y val.json.
El exportador excluye IDs de train, test y los archivos *gold*.jsonl de
annotations/citation_function. Conserva los hashes de las fuentes y la versión
del catálogo. El corpus y los modelos no se modifican.

Para regenerar con los datos locales disponibles:

```sh
python3 scripts/exportar_ejemplos_cientificos.py
```

La procedencia de validación se muestra en la interfaz. Son ejemplos de uso,
no una evaluación científica ni una garantía de la función predicha. El ejemplo
público sintético sigue disponible para comprobar proveedores externos.

## Comprobaciones

- Build de TypeScript y Vite correcto.
- 32 pruebas unitarias aprobadas.
- 38 casos existentes de cobertura, recorrido y comercial aprobados.
- Dos casos nuevos aprobados en escritorio y móvil tras corregir foco y Escape.
- Búsqueda por texto, título e ID; vacío, selección, cobertura y consentimiento.
- Las pruebas de interfaz interceptan la API: no consumen llamadas comerciales.
- Capturas revisadas en escritorio y móvil.
- Frontend publicado mediante make publish-frontend. Las dos pruebas del selector
  también pasaron sobre https://proyectocitas-grupo19.click, con API interceptada.
  No se reconstruyeron imágenes ni se modificó infraestructura.

Seguimiento: T01–T03 completas (selector ampliado); T04 pendiente de cuota;
T05–T06 suspendidas; T07–T08 disponibles para M/S y comercial, QLoRA suspendido;
T09 completa; T10 parcial; T11 aceptada para M/S y comercial, QLoRA suspendido;
T12 y cierre de T13 pendientes. No se avanza T10 dentro de esta ampliación.
