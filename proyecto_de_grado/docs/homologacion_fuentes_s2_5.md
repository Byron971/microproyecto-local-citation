# S2.5 — Auditoría metodológica de fuentes y puerta de homologación

**Fecha:** 2026-10-10  
**Estado:** análisis documental y **decisión de no fusionar automáticamente**. No se ha descargado ni incorporado ninguna fila de MultiCite o ILCiteR. S2.4 se mantiene como antecedente exploratorio.
**Dependencia de rama:** `feature/s2-4-auditoria-enriquecimiento-multifuente`. Este trabajo no modifica `main` ni los PR anteriores.

## 1. Motivación desde la propuesta y la retroalimentación de Haydemar

La propuesta de grado contiene **dos tareas**: (i) recuperar el Top-3 de fragmentos relevantes dentro del artículo citado, y (ii) clasificar la **función principal de la cita** entre nueve categorías. La revisión R4.1 del profesor pide explicar explícitamente cómo se homologarán fuentes distintas; R5.4 exige demostrar si se pueden obtener **2.000 ejemplos por función** y R5.5 definir una contingencia si faltan datos. La política G0 exige **15 % de validación humana del dataset final**, separada del nuevo Test Gold, y prohíbe contaminar splits y adjudicaciones.

La integración actual **ACL-200 + ACL OCL** es legítima como enriquecimiento documental porque usa IDs de ACL Anthology para conservar citas y recuperar el texto del citado. Eso **no crea automáticamente etiquetas de función de cita**. La evidencia local al cerrar S2.4 incluye 14 artículos citados utilizables en caché, 2.140 contextos train elegibles, 39 seleccionados de 11 artículos, e inferencias de 5 casos con Qwen 4B sin Gold; por tanto **no tenemos aún frecuencias verificadas de ninguna de las nueve funciones**.

## 2. Catálogo de fuentes y semántica real

| Fuente | Unidad de observación | Supervisión de función de cita | Relación con la propuesta | Veredicto hoy |
| --- | --- | --- | --- | --- |
| ACL-200 (nianlonggu) | Contexto de cita con TARGETCIT; IDs citante/citado; split temporal | No hay nueve etiquetas revisadas | Dataset central; verificar IDs, pares y exclusiones | **Admitido para contexto**, no como Gold de función |
| ACL OCL | Texto completo GROBID, párrafos y secciones ACL | No hay nueve etiquetas de función | Texto del **citado** para Top-3; reconstrucción del citante bajo controles | **Admitido para evidencia candidata**, no Gold |
| MultiCite (Lauscher et al., NAACL 2022) | Contextos de múltiples oraciones y múltiples funciones por referencia | Sí, **multietiqueta**, taxonomía propia | Referencia de anotación, posible fuente auxiliar condicionada a adjudicación | **No fusionar como etiquetas 1:1** |
| ILCiteR (Ghosh Roy y Han, LREC-COLING 2024) | Consulta, fragmento de evidencia y artículo candidato | El resumen revisado **no demuestra** nueve etiquetas retóricas | Referencia metodológica para recuperación de evidencia | **No usar como etiquetas de función** |

Fuentes verificadas:

- Gu et al. / código y datos ACL-200: https://github.com/nianlonggu/Local-Citation-Recommendation
- ACL Anthology para MultiCite: https://aclanthology.org/2022.naacl-main.137/
- Esquema, nombres de clases y licencia MultiCite: https://github.com/allenai/multicite/blob/master/README.md
- ACL Anthology para ILCiteR: https://aclanthology.org/2024.lrec-main.757/
- Licencias de materiales ACL: https://aclanthology.org/faq/copyright/

**Limitación de verificación:** no se verificó aquí que exista un archivo descargable y con licencia apropiada de ILCiteR que contenga etiquetas de funciones, ni una correspondencia masiva comprobada entre IDs MultiCite/S2ORC y ACL-200. No inventar repositorios, cuotas ni tasas de join.

## 3. MultiCite NO comparte nuestra taxonomía

El README de MultiCite enumera exactamente los **identificadores externos**:
`@BACK@`, `@MOT@`, `@FUT@`, `@SIM@`, `@DIF@`, `@USE@`, `@EXT@`, `@UNSURE@`. `@EXT@` aparece documentado como `Extention` (grafía de la fuente); no corregir el ID ni asumir sinónimos idénticos. Su artículo informa aproximadamente **12.6K contextos** de aproximadamente **1.2K artículos**, anotados con **múltiples etiquetas** y contextos de **varias oraciones**. La fuente declara licencia **CC BY-NC 2.0** porque deriva de S2ORC.

La propuesta propia exige una **función principal exclusiva** entre:

1. Background
2. Gap
3. Basis
4. Comparison
5. Application
6. Improvement / Modification
7. Evidence
8. Identification of the Originator
9. Further Reading

### Matriz de relaciones *candidatas* (NO reglas de recodificación)

| Código MultiCite | Función externa | Relación con nuestras clases | Riesgo y acción requerida |
| --- | --- | --- | --- |
| `@BACK@` | Background | Background, coincidencia nominal aproximada | Revisar definición, unidad y anotación del objetivo antes de considerar equivalencia |
| `@MOT@` | Motivation | A veces Gap/Basis, pero ninguna equivalencia directa | No convertir |
| `@FUT@` | Future Work | No equivale a Further Reading | No convertir |
| `@SIM@` | Similar | Relación parcial con Comparison | No convertir automáticamente |
| `@DIF@` | Difference | Relación parcial con Comparison y a veces Gap | No convertir automáticamente |
| `@USE@` | Uses | Relación parcial con Application | Distinguir uso directo frente a Basis |
| `@EXT@` | Extention | Relación parcial con Improvement / Modification | Exige confirmar la modificación real del método citado |
| `@UNSURE@` | Unsure | No es una función retórica positiva | Abstención / revisión humana, nunca forzar Background |

**Ningún código externo se considera equivalente automáticamente**. No se deben combinar etiquetas multietiqueta en una sola clase utilizando `argmax`, el primer código, o reglas arbitrarias; tampoco se puede adjudicar una categoría que MultiCite nunca distinguió (Evidence, Identification of the Originator, etc.). Cualquier uso supervisado requeriría relabeling específico y revisión humana independiente.

## 4. Controles obligatorios antes de incorporar otra fuente

El registro estructurado `proyecto_de_grado/config/fuentes_citas_s2_5.json` documenta **estado, tarea, taxonomía, licencia y permiso de uso**, mientras `validar_fuentes_s2_5.py` **bloquea importaciones automáticas** y verifica categorías. Este control de configuración NO sustituye auditoría semántica ni legal.

**Puertas de decisión** (todas deben tener evidencia antes de cambiar `incorporacion_automatica=false`):

1. **Pertinencia de tarea:** distinguir evidencia Top-3, identidad de artículo y función retórica; no confundir recomendación de artículos con fragmentos relevantes.
2. **Derechos y procedencia:** revisar licencia del dataset y de los textos subyacentes; en especial CC BY-NC 2.0 de MultiCite. No subir textos completos al repositorio público.
3. **Identidad y alineación:** resolver `citing_id`, `cited_id`, mención concreta de la referencia, `TARGETCIT` y posibles citas agrupadas; evaluar % de enlaces reales, **no inferirlo por títulos similares**.
4. **Compatibilidad semántica:** mapa con definiciones, diferencias de unidad (multi-oración vs ventana ACL-200), casos ambiguos y adjudicación humana ciega; ninguna equivalencia sin evidencia.
5. **Particiones y duplicados:** colocar ampliaciones solo en **train** mientras se diseñan los experimentos, excluir IDs ya usados para escoger prompts, bloquear solapamientos de citantes/pares/contextos y duplicados o casi duplicados.
6. **Calidad y representatividad:** doble anotación en muestra de calibración, desacuerdos y acuerdo reportados, revisión del 15 % real sobre el dataset final; análisis por clases minoritarias, sesgo por artículos muy citados y **sección del citante frente a sección del citado**.
7. **Versionado reproducible:** snapshot, checksum, licencia, transformaciones y registro del adjudicador; no sobrescribir datasets v1–v3 ni Test Gold.

## 5. Hoja de ruta inmediata para minimizar reprocesos

**S2.5.a — Cerrado por este documento:** contrastar taxonomías y tareas en las publicaciones y catálogos oficiales, versionar la matriz y bloquear técnicamente recodificación automática.

**S2.5.b — Pendiente:** construir una muestra de 20–30 registros externos solo si la licencia lo permite y existe acceso verificable, con IDs y anotaciones multietiqueta; ejecutar análisis **sin fusionar filas** de cuántos pueden mapearse a ACL-200 y qué clases requieren adjudicación. No hacer esto antes de decidir fuente y licencia.

**S2.5.c — Pendiente:** revisión del equipo de los casos ambiguos y aprobación de tabla de homologación por docente; si no es viable, conservar MultiCite e ILCiteR como antecedentes sin aumentar artificialmente cuotas.

**S2.5.d — Pendiente:** paralelamente ampliar con **citas adicionales genuinas de ACL OCL** usando el mismo esquema y reconstrucción de TARGETCIT, deduplicando y asignando split sin contaminar el test. No declarar que las 2.000 etiquetas/clase o el 15 % humano están cumplidos hasta auditar conteos definitivos.

## 5.b. Instrumento de inspección de una muestra REAL, sin mezclar datos

**Verificación de los archivos oficiales de MultiCite (GitHub):**

- El dataset completo es `data/full-v20210918.json`, **46.307.631 bytes**. Su esquema incluye el código `@UNSURE@` y estructura `x/y` por artículo e intención.
- La versión simplificada `data/classification_1_context/train.json` tiene **1.667.641 bytes** en el commit `120671924b5ab968b98c7f696c4b67b4f8118948`, blob Git `fdb9dfe5aa5de396e687924a4da1c5dbd62f6255`. Su estructura documentada es una lista con `id`, `x`, `y`. El lector oficial `classification/citances_processor.py` transforma `y.split(" ")` en múltiples etiquetas y enumera **siete** nombres de clasificación: `motivation, background, uses, extends, similarities, differences, future_work`. Esto **no contradice** las ocho intenciones del esquema completo: `Unsure` no es una clase normal del clasificador.
- Otros tamaños y ventanas de contexto tienen distribuciones distintas; la muestra de **una oración** es apropiada para examinar el formato con mínimo tráfico, **no** demuestra equivalencia con nuestras ventanas ACL-200.

Implementación `proyecto_de_grado/src/data/perfilar_multicite_s2_5.py`. El modo por defecto **no descarga, no crea archivos**. Para inspeccionar primero el plan:

```powershell
python -m proyecto_de_grado.src.data.perfilar_multicite_s2_5
```

Tras confirmar uso de investigación no comercial y licencia CC BY-NC 2.0, autorizar **solo una** petición de ~1,67 MB a un commit Git fijado; límite máximo 2 MB, comprobación obligatoria del SHA-1 de objeto Git:

```powershell
python -m proyecto_de_grado.src.data.perfilar_multicite_s2_5 --execute --sample 30 --seed 42
```

El resultado es un JSON de diagnóstico en `proyecto_de_grado/artifacts/multicite_s2_5/perfil_multicite_train.json` (**ignorado por Git**). **NO guarda el archivo fuente completo**, solo un resumen de conteos del train y hasta treinta muestras locales de 250 caracteres con sus IDs y *etiquetas externas*. Muestrea primero para cubrir códigos menos frecuentes y luego rellena aleatoriamente; **los porcentajes del subconjunto NO representan las frecuencias reales**. El perfil incluye el número de filas multietiqueta, los IDs con forma de ACL Anthology, la distribución real del **train externo** y la huella SHA-256 de la fuente consultada.

Antes de fusionar, queda pendiente un **cotejo de identidad** entre los IDs externos y los `context_id`/artículos originales de ACL-200, con una clave externa verificable (`S2ORC` ↔ `ACL Anthology`, si existiera), identificación de la **referencia concreta** y doble revisión humana de anotaciones inciertas. **Una coincidencia de título o un `id` que se parece a ACL no constituye un match válido**. No se ejecuta sobre `test`, no transfiere etiquetas, no actualiza modelos y no permite contabilizar ejemplos hacia la cuota de 2.000/clase o el 15 % humano.

### Incidencia detectada en la primera ejecución real (2026-10-10)

La primera ejecución `--execute` descargó el archivo indicado y **se detuvo sin generar perfil** en el registro de índice Python **833** (`264bdb348c13f167768fd859b047e8_7`) porque el lector anterior exigía que `x` tuviera al menos un texto. Inspeccionando directamente el **blob oficial de GitHub identificado por el SHA-1 fijado** se constató:

- Total train externo: **5.491 filas**, todas con `y` de tipo cadena;
- **17 filas con `x=[]`**, incluida la fila 833; **5.474 filas** con `x` no vacío;
- Identificadores repetidos detectados: **0**;
- Filas con más de una etiqueta externa: **746** en las 5.491 filas originales;
- Los códigos de clasificación observados son: `background`, `motivation`, `differences`, `uses`, `extends`, `similarities` y `future_work`.

Estos números son del **archivo train de una oración**, no del MultiCite completo ni de nuestro conjunto de nueve etiquetas. La cuenta `17/5.491` es una incidencia de formato del corpus externo: no autoriza inventar contenido, rellenar con título o copiar etiquetas a ACL-200.

**Corrección:** `cargar_y_validar` conserva y valida los IDs, las etiquetas y el índice original de todas las filas, pero identifica explícitamente las 17 sin contexto como `excluido_contexto_vacio`. `perfil_muestra` las excluye del muestreo, informa sus IDs/motivos, el denominador completo y el subconjunto utilizable; sigue **rechazando** etiquetas desconocidas, IDs duplicados, contextos de tipos inesperados y falta total de registros útiles. Se añaden pruebas de regresión con la estructura de la fila 833. No se modifican los datasets originales ni los experimentos S2.4.

Tras la actualización y la aprobación de GitHub Actions, la ejecución de inspección `--execute --sample 30 --seed 42` puede **repetirse una vez** porque el intento inicial no dejó el archivo fuente guardado ni generó perfil. La ejecución subsiguiente sigue siendo solo diagnóstico; **no fusiona ni homologa**. Comprobar que reporta 5.491 totales, 5.474 utilizables, 17 excluidos y 30 observaciones de muestra antes de proceder a cualquier otro paso.

## 6. Criterios de aceptación de este incremento

- Documentación basada en fuentes primarias del proyecto y publicaciones externas, con alcance y licencias verificables.
- Inventario exacto de códigos de MultiCite y nueve funciones internas.
- Ninguna función externa recodificada o importada a train/test por el pipeline.
- Validador offline y tests que **rechacen mapeos automáticos** o taxonomía cambiada accidentalmente.
- No descargar ni generar etiquetas; no modificar el comportamiento histórico del clasificador ni los artefactos de S2.4.

**Resultado científico defendible:** hemos definido qué fuentes aportan texto, qué fuentes aportan otras taxonomías y por qué ninguna puede contarse como nueva etiqueta de una de las nueve clases hasta superar el protocolo de homologación.
