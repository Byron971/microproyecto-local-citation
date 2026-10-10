# S2.4 — Cobertura y enriquecimiento multifuente: ACL-200 + ACL OCL

**Estado:** primer incremento offline para **auditar y preparar candidatos sin etiquetas**. No añade todavía MultiCite ni ILCiteR como filas, ni produce el dataset final de 9 clases. No modifica `main`, el dataset DVC, el Test Gold, el frontend ni el paquete de modelo.

## Por qué este desarrollo

La propuesta del proyecto de grado tiene dos resultados conectados:

1. **Recuperación local de evidencia**: contexto del artículo citante y fragmentos del artículo citado.
2. **Enriquecimiento con función de cita**: nueve categorías, una etiqueta principal, procedencia verificable y revisión humana de al menos 15 % del dataset final.

Ya se probó S2.2 con un artículo por contexto, pero el exportador era una **demo** que dejaba solo un contexto por artículo citado. S2.4 permite **varios contextos que citan el mismo paper**, con un límite configurable por paper para no concentrar un lote pequeño en uno solo.

## Fuentes y roles (sin mezclar clases incompatibles)

| Fuente | Función aquí | Estado |
| --- | --- | --- |
| ACL-200 | IDs de citante/citado, contexto `TARGETCIT`, splits originales, título y resumen | Fuente primaria validada |
| ACL OCL | Texto completo del **citado**, secciones, párrafos e índices, huella SHA-256 | Solo documentos ya descargados en caché |
| MultiCite | Estudio metodológico de funciones y anotación | Referencia; NO fusionada ni homologada aún |
| ILCiteR | Estudio metodológico de evidencias y recuperación de fragmentos | Referencia; NO fusionada ni homologada aún |
| Otras fuentes | Posible ampliación futura condicionada a licencia, IDs y mapa de etiquetas | Ninguna integrada en este incremento |

No derivamos una función de cita de la sección textual, del título, del Top-3 BM25 ni de la cercanía entre citas. `funcion_cita.etiqueta_principal` y `evidencia_top3.fragmentos_relevantes_adjudicados` permanecen **null**.

## Qué hace el script

`proyecto_de_grado/src/data/preparar_enriquecimiento_s2_4.py`:

- Reutiliza `load_split_index` y sus verificaciones de separación de citantes/pares, sin reescribir datos.
- Audita **todos los contextos supervisados** por partición, en conteos agregados; nunca exporta texto de `val` ni `test`.
- Distingue documentos citados no descargados de códigos `.404` conocidos, archivos corruptos, `paper_id` incorrectos, documentos sin párrafos y fragmentación no válida.
- Registra la presencia local de artículos **citantes** por separado; tener el JSON en caché no prueba que la cita haya podido reconstruirse.
- Detecta textos de contexto **exactamente iguales tras normalizar espacios y minúsculas** compartidos entre particiones y los excluye de la exportación train por precaución. Esta prueba NO es deduplicación semántica de casi duplicados.
- Reutiliza `fragmentar()` con máximo dos párrafos, 300 palabras y sin cruzar secciones.
- Selecciona una muestra determinista de `train` mediante `--seed`; `--max-per-cited` evita que un solo documento domine el primer lote.
- Comprueba la identidad nuevamente mediante `integrar_contexto()`, guarda la huella SHA-256 del texto ACL OCL y los índices originales de cada fragmento.
- Genera registros con el mismo contrato básico de `preparar_preetiquetado.py` (`id`, `split`, `citing_id`, `cited_id`, `citation_context`, título y resumen), con campos nuevos de fuente, fragmentos, etiqueta nula y evidencia pendiente.
- Nunca usa un LLM ni infiere clases; ningún resultado es **Gold** ni evaluación final.

## Reproducir en Windows

Desde el repositorio local, tras actualizar la rama correspondiente (no cambiar de rama si hay cambios sin guardar):

```powershell
python -m pytest -q proyecto_de_grado/tests/test_preparar_enriquecimiento_s2_4.py

python -m proyecto_de_grado.src.data.preparar_enriquecimiento_s2_4 --limit 40 --seed 42 --max-per-cited 4
```

**Prerequisitos:** `data/raw` disponible a través de DVC, caché local ACL OCL ya descargada y archivos de exclusión en `proyecto_de_grado/anotacion/`. No hace peticiones de red ni descarga artículos.

Salida (no se versiona en Git):

- `proyecto_de_grado/artifacts/enriquecimiento_s2_4/resumen_cobertura.json`: conteos originales por split y motivos de disponibilidad; cantidad seleccionada y estado explícito de etiquetas.
- `proyecto_de_grado/artifacts/enriquecimiento_s2_4/candidatos_train_enriquecidos.jsonl`: contexto ACL-200, fragmentos del **artículo citado** ACL OCL y campos de procedencia por candidato.

La salida es reproducible para **los mismos datos/caché/exclusiones y semilla**. Si vuelve a ejecutarse sin cambios conserva el archivo byte a byte; si los datos cambian **no sobrescribe** la evidencia: se indica usar otra carpeta `--out`.

`--limit 40` es un **máximo**, no una obligación: si solamente hay dos documentos ACL OCL en caché y pocas citas elegibles, podrían seleccionarse menos registros. El resumen separa la selección local de cualquier afirmación de cobertura global.

## Esquema de etiqueta preparado (no anotación efectiva)

```json
{
  "funcion_cita": {
    "etiqueta_principal": null,
    "etiqueta_secundaria": null,
    "estado": "no_etiquetado",
    "origen_etiqueta": null,
    "validacion_humana": false
  },
  "evidencia_top3": {
    "fragmentos_relevantes_adjudicados": null
  }
}
```

Los nombres exactos de las nueve categorías permanecen en `ETIQUETAS` de `preparar_preetiquetado.py`. Una función principal es nuestra decisión operativa vigente, con posibilidad de registrar ambigüedad más adelante.

## Qué NO demuestra aún

- No se descargó ni integró masivamente ACL OCL. **Cobertura del cache ≠ cobertura de ACL OCL**.
- No se han homologado categorías de MultiCite ni importado anotaciones de otros corpus.
- No hay 18.000 citas clasificadas, no hay validación humana del 15 % ni distribución real de nueve categorías.
- No hay cálculos válidos de Recall@3, MRR@3 o F1 de nueve categorías sobre un conjunto independiente.
- No se han resuelto citas agrupadas ni demostrado ausencia de casi duplicados entre particiones.
- La selección balanceada por documento es una medida de ingeniería del **primer lote**, no un muestreo estadísticamente representativo.

## Evidencia local del primer lote (10-oct-2026)

En la máquina del equipo, la auditoría S2.4 terminó con **9 pruebas locales aprobadas** y estos datos:

| Observación | Conteo | Qué significa |
| --- | ---: | --- |
| Contextos supervisados ACL-200 | 49.356 | Universo original supervisado |
| Documentos citados utilizables en la caché actual | 3 | Documentos distintos, **no** contextos |
| Candidatos de entrenamiento elegibles | 5 | Casos tras filtros, con esa caché |
| Candidatos exportados | 5 | Lote local, no dataset final |
| Textos normalizados idénticos compartidos entre splits | 6 | Huellas distintas; no son 6 pares demostrados con fuga |
| Contextos con documento citado no descargado, train | 30.320 | Casos, no artículos distintos |
| Contextos con fragmentación inválida, train/val/test | 64 / 27 / 16 | **107 contextos** vinculados a artículos problemáticos, no 107 documentos |

Esta evidencia muestra un cuello de botella fuerte: la disponibilidad/fragmentación del texto completo. **No multiplicar** 49.356 por porcentajes derivados de la caché pequeña. Tampoco interpretar 107 contextos con fragmentación fallida como 107 artículos distintos.

Para diagnosticar sin modificar el corpus se añadió `diagnosticar_cache_s2_4.py`. Lee solo metadatos técnicos y longitudes del contenido, muestra cuántos **documentos distintos** están detrás de los rechazos y prioriza archivos citados ausentes usando únicamente contextos de `train` no excluidos. No incluye textos ni IDs de validación/prueba.

```powershell
python -m pytest -q proyecto_de_grado/tests/test_diagnosticar_cache_s2_4.py
python -m proyecto_de_grado.src.data.diagnosticar_cache_s2_4 --top 12
```

Informe local generado: `proyecto_de_grado/artifacts/enriquecimiento_s2_4/diagnostico_cache_train.json`. **No descargar** automáticamente lo que aparece priorizado: primero decidir estrategia de lotes, límites, fuente autorizada y tamaño.

## Ajuste de fragmentación v2 — modo S2.4 (posterior al diagnóstico)

El diagnóstico de caché mostró **cinco documentos citados disponibles** en `train`: dos inicialmente utilizables y **tres rechazados solo por fragmentación**. Se trata de `P11-1082` (32 contextos train; dos párrafos extensos), `N04-1019` (29 contextos; tres párrafos) y `D10-1033` (dos contextos; dos párrafos). Los párrafos más largos tienen 488, 524 y 372 palabras respectivamente. **No se han descargado archivos nuevos.**

Se añadió a `fragmentar()` un modo opcional `dividir_parrafos_largos=True` que **solo usa el enriquecimiento S2.4**. Conserva todos los caracteres originales del párrafo mediante rangos `paragraph_char_spans` (inicio inclusivo, fin exclusivo). Los fragmentos generados reciben IDs `p00012-s000`, `p00012-s001` y `fragmentacion=division_conservadora_palabras_v1`. No se agregan fragmentos a diferentes secciones. Un texto indivisible mayor de 5.000 caracteres sigue rechazándose.

**Regla importante:** el corte se hace en límites de palabras, **no es una segmentación semántica por oraciones**. Esto recupera cobertura sin perder evidencia, pero los fragmentos partidos deben ser revisados metodológicamente antes de tratarse como referencia final. El modo anterior de S2.2 y las 57 anotaciones de calibración S2.3 quedan **inalterados**; por defecto, `fragmentar()` sigue rechazando párrafos largos y conserva los IDs anteriores.

Para comparar la nueva versión con el primer lote histórico, **NO sobrescribir los archivos anteriores**:

```powershell
python -m pytest -q proyecto_de_grado/tests/test_exportar_corpus_top3.py proyecto_de_grado/tests/test_preparar_enriquecimiento_s2_4.py proyecto_de_grado/tests/test_diagnosticar_cache_s2_4.py

python -m proyecto_de_grado.src.data.preparar_enriquecimiento_s2_4 --limit 40 --seed 42 --max-per-cited 4 --out proyecto_de_grado/artifacts/enriquecimiento_s2_4/v2_segmentos
```

Se esperan **tres artículos adicionales potencialmente recuperables** si sus restantes invariantes cumplen las condiciones. Al existir `--max-per-cited 4`, esto no significa exportar automáticamente los 63 contextos asociados: se seleccionan como máximo cuatro por artículo en este lote. La cobertura real la determina el resultado local y debe contrastarse contra el resumen v1.

## Adquisición incremental de ACL OCL — planificación controlada

El repositorio ya tenía un descargador exploratorio (`medir_enlace.py`, del *spike* de 500 casos). Ese estudio mezclaba descargas ACL OCL, perfilado y consultas Semantic Scholar. Para **no repetir el experimento histórico ni ejecutar cientos de peticiones de golpe**, el incremento S2.4 incorpora `adquirir_ocl_incremental_s2_4.py`, que reutiliza la URL ACL OCL existente pero separa explícitamente planificación y descarga.

**Primero, exclusivamente sin red** (usar ruta nueva para no sobrescribir el diagnóstico anterior de los 12 primeros IDs):

```powershell
python -m proyecto_de_grado.src.data.diagnosticar_cache_s2_4 --top 100 --out proyecto_de_grado/artifacts/enriquecimiento_s2_4/diagnostico_cache_train_top100.json
python -m proyecto_de_grado.src.data.adquirir_ocl_incremental_s2_4 --limite 6
```

El segundo comando es **dry-run por defecto**, muestra exactamente seis IDs (o menos) y el número de contextos train potencialmente enlazables; **no crea archivos ni hace peticiones de red**. El lote selecciona la mitad por número de contextos y el resto diversifica por década cuando hay disponibilidad; es una heurística de desarrollo, no un muestreo estadísticamente representativo.

**Solo tras aprobar la lista, la fuente/licencia y el tamaño del lote**, realizar una adquisición explícita:

```powershell
python -m proyecto_de_grado.src.data.adquirir_ocl_incremental_s2_4 --limite 6 --execute --pausa 2 --max-bytes 5000000
```

La adquisición real está limitada a máximo diez documentos por lote, hasta 5 MB por JSON, solicitudes secuenciales con pausa, tres intentos ante errores HTTP transitorios, lectura acotada por archivo, `paper_id` comprobado y guardado atómico; conserva `.404` solamente en respuestas HTTP 404 verificadas. No vuelve a consultar documentos en caché. Las pruebas usan transportes falsos y no requieren Internet.

Este procedimiento **no debe ejecutarse automáticamente por CI** ni confundirse con haber descargado artículos reales. Los textos completos proceden de PDFs académicos con licencias potencialmente restrictivas: **no hacer commit de la caché ni redistribuir el contenido sin revisar licencias de artículos individuales**. El objetivo inicial es medir viabilidad de cobertura, no alimentar el corpus completo de una vez.

Después del primer lote real, generar una **tercera** salida versionada distinta de las anteriores (`--out proyecto_de_grado/artifacts/enriquecimiento_s2_4/v3_adquisicion`) y comparar el número de casos elegibles, identidades válidas y motivos de exclusión. `--limit 40 --max-per-cited 4` son cuotas del **lote** y no evidencian una mejor cobertura global.

## Primera comparación de prompts de funciones de cita (10-oct-2026)

Sobre el lote v3 (**39 contextos de train de 11 artículos citados**, SHA-256 verificado y ninguna anotación humana), Qwen 4B produjo el mismo vector de nueve puntajes en los **3 casos reales del piloto**: `[0.95, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01]`, que implicaba `Background` para todos. Los textos brutos fueron idénticos entre sí. **No interpretar 0,95 como probabilidad calibrada.**

En una prueba exploratoria **no persistida** que conservó el contexto, título, resumen, modelo y definiciones de las nueve clases, pero cambió el formato solicitado a un **único nombre literal**, los dos controles sintéticos respondieron `Application` y `Comparison`; los tres casos reales respondieron `Application`, `Basis` y `Background`. Este contraste de solo tres ejemplos **no demuestra precisión de clasificación** ni constituye F1, Gold o validación humana. Los controles artificiales tampoco se añaden al dataset.

Para reproducir el cambio sin editar a mano el código, `preetiquetar_local.py` ahora admite `--format label`. El modo por defecto `scores`, el prompt y el fingerprint histórico se conservaron idénticos; `label` usa un **prompt/fingerprint nuevo** y guarda archivos en una subcarpeta `etiqueta_directa_v1` para evitar mezclar el antiguo experimento con el nuevo. El campo `raw_response` mantiene la salida original y `suggested_label` solo admite **una categoría literal exacta**; una respuesta con dos clases o explicaciones queda como `parse_error`. En modo `label`, tanto `scores` como `top1_top2_margin_uncalibrated` son `null`, porque el modelo no emitió puntuaciones.

Tras validar las pruebas, ejecutar un piloto muy pequeño en una **carpeta nueva** (requiere Ollama local ya instalado, no descarga modelos ni usa API de pago):

```powershell
python -m pytest -q proyecto_de_grado/tests/test_preetiquetar_local.py

python -m proyecto_de_grado.src.data.preetiquetar_local --format label --input proyecto_de_grado/artifacts/enriquecimiento_s2_4/v3_adquisicion/candidatos_train_enriquecidos.jsonl --out proyecto_de_grado/artifacts/enriquecimiento_s2_4/piloto_qwen4b_directo_v1 --model qwen3:4b-instruct --limit 5
```

Se guardará `piloto_qwen4b_directo_v1/qwen3_4b-instruct/etiqueta_directa_v1/predicciones.jsonl`, archivo local ignorado por Git; **no** se toca `piloto_qwen4b_v3` ni se modifica `funcion_cita.etiqueta_principal` del dataset. Comparar los mismos contextos con el piloto anterior; estimar distribución de etiquetas solo de manera descriptiva. **No continuar a 39 ni a 2.140 casos** hasta que exista un protocolo de anotación independiente y una decisión documentada sobre el modelo. Este clasificador todavía **no consume `cited_chunks`**: la comparación con/ sin evidencia OCL es un experimento distinto por diseñar.

## Puerta de salida para siguiente incremento

1. Ejecutar en `data/raw` real y documentar cobertura por split, total utilizable en caché y número de candidatos `train` generado.
2. Elegir estrategia de adquisición incremental ACL OCL basada en **IDs de documentos citados faltantes**, con rate limiting, caché, estimación de tamaño y licencias; no realizar descargas masivas sin esa planificación.
3. Revisar viabilidad de las nueve clases y el esquema de homologación de fuentes adicionales **antes** de fusionar anotaciones externas.
4. Alimentar luego el pre-etiquetado con los registros enriquecidos, sin usar `val/test` para escoger prompts.
5. Mantener en paralelo S2.3 de calibración humana y la redacción del informe de avance.

**No modificar todavía el PR #80, #81 o #82 ni fusionarlos hasta completar sus revisiones.**
