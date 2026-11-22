# Revisión manual y Excel de resultado

La plantilla original tiene cuatro campos de anotación: **¿Evaluable?**, **Función principal (una)**, **Confianza** y **Justificación / duda**. La aplicación captura solo esos campos. Estado y Control siguen siendo fórmulas del Excel; no se capturan manualmente. Las fechas, versiones e historial de guardado son internos y no se agregan a las columnas de la plantilla.

## Excel con las 179 aceptadas

`notebooks/anotaciones/TestGold_T1_v2_Zambrana__resultado.xlsx` conserva las 207 entradas, hojas, traducciones, formato, fórmulas y orden del original. Las 179 entradas aceptadas tienen I–L completadas y las 28 pendientes quedan en blanco. Excel recalcula Estado y Control al abrir.

La función es la aceptada por las reglas de consenso. Para confianza y justificación se copia una respuesta original que apoye esa función, en prioridad Opus, Sol, Sonnet, GPT-5.4 mini, Luna y GPT-4o mini. El archivo auxiliar `.procedencia.json` registra qué respuesta se utilizó en cada caso. No se atribuyen estas anotaciones automáticas a una persona.

## Revisar las 28 pendientes

Desde la raíz del proyecto:

```bash
.venv/bin/python -m src.revision_manual
```

Abrir <http://127.0.0.1:8765>. La aplicación usa el consolidado más reciente al arrancar. Leer TARGETCIT, elegir evaluabilidad y función, indicar confianza y justificación y pulsar **Guardar y continuar**. Para Ambiguo o No evaluable, la función queda vacía. No se solicita nombre de revisor ni otros campos fuera de la plantilla.

Se puede regresar a una decisión guardada y corregirla. El progreso persiste en `revision_humana_<hash>.sqlite3`, junto al consolidado, después de cerrar el navegador o reiniciar el servidor. No se llama a ningún modelo.

## Exportar el CSV y rellenar el resultado

El enlace **CSV para completar las pendientes** exporta solo las revisiones guardadas, en el orden de la plantilla, con estos encabezados exactos:

```text
context_id,¿Evaluable?,Función principal (una),Confianza,Justificación / duda
```

`context_id` permite unir por identificador, sin asumir que las 28 pendientes son filas consecutivas. No pegar todo el CSV directamente sobre I–L del Excel completo: sus filas están intercaladas entre las ya aceptadas.

Después de descargar el CSV, completar el Excel con:

```bash
.venv/bin/python -m src.resultado_anotaciones \
  --dataset "notebooks/anotaciones/consolidado/20261116T145111641819Z/dataset_consolidado.json" \
  --csv "/ruta/al/revision_revisiones.csv" \
  --output "notebooks/anotaciones/TestGold_T1_v2_Zambrana__resultado_actualizado.xlsx"
```

Se comprueba que los IDs sean pendientes válidas, sin duplicados, y que los valores cumplan la plantilla. El programa conserva las 179 aceptadas, añade las revisiones del CSV en su fila original y deja en blanco cualquier pendiente todavía no revisada. Indica cuántas automáticas, humanas y pendientes quedan. El original nunca se sobrescribe. Usar un nombre de salida nuevo para conservar versiones anteriores.

El enlace **Excel de resultado · 179 aceptadas** descarga la base automática. Las revisiones se incorporan con el comando anterior, no al guardar en la aplicación.

Para detener el servidor, usar Ctrl+C en la terminal donde se inició.
