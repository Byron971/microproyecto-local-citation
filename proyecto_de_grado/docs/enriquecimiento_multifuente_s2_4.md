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

## Puerta de salida para siguiente incremento

1. Ejecutar en `data/raw` real y documentar cobertura por split, total utilizable en caché y número de candidatos `train` generado.
2. Elegir estrategia de adquisición incremental ACL OCL basada en **IDs de documentos citados faltantes**, con rate limiting, caché, estimación de tamaño y licencias; no realizar descargas masivas sin esa planificación.
3. Revisar viabilidad de las nueve clases y el esquema de homologación de fuentes adicionales **antes** de fusionar anotaciones externas.
4. Alimentar luego el pre-etiquetado con los registros enriquecidos, sin usar `val/test` para escoger prompts.
5. Mantener en paralelo S2.3 de calibración humana y la redacción del informe de avance.

**No modificar todavía el PR #80, #81 o #82 ni fusionarlos hasta completar sus revisiones.**
