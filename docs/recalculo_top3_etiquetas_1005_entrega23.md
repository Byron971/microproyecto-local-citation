# Recalcular Top-3 con las anotaciones A/B completas — entrega 23 de noviembre

## Evidencia disponible
Dos libros privados `Anotador_A_19_resueltos.xlsx` y
`Anotador_B_19_resueltos.xlsx` contienen 1005 pares, 30 contextos,
96 positivos y 909 negativos. Se verificó intersección completa de
IDs, cero duplicados y cero desacuerdos entre libros. A tiene 45 campos
de sección vacíos; B los tiene llenos. Las etiquetas y su integridad
pueden usarse para puntuar los rankings, pero **no prueban independencia
de anotación inicial**.

El JSON histórico anterior contiene 99 positivos y 906 negativos; por
ello **sus promedios no deben trasladarse a las etiquetas actuales**.
Los libros incluyen justificaciones privadas que no se incorporan al
CSV reducido.

## Reproducción local
El archivo `top3_etiquetas_pareadas_1005.csv` se entrega al
investigador como adjunto de conversación y debe ubicarse
en `artifacts/top3_etiquetas_pareadas_1005.csv` del clon limpio.
No subirlo a GitHub hasta revisar permisos del equipo y derechos del corpus.

```powershell
git pull --ff-only
$original = "C:\Users\juan sanz\Downloads\IAandes\microproyecto-local-citation-actualizado"
$rank = Join-Path $original "proyecto_de_grado\artifacts\top3_test_preparacion\evaluacion_modelos_reservada"
.\.venv-ms\Scripts\python.exe scripts/recalcular_top3_etiquetas_finales.py --etiquetas artifacts\top3_etiquetas_pareadas_1005.csv --bm25 "$rank\ranking_bm25.json" --scibert "$rank\ranking_scibert.json" --salida artifacts\top3_recalculado_1005.json
```

El script valida formato, unicidad y cobertura de contextos en los dos
rankings, rechaza chunks del Top-3 fuera del universo etiquetado y
exige que la salida no exista. Si los rankings tienen una estructura
no reconocida, informa las claves del archivo para ajustar el lector
sin modificar resultados.

## Puertas metodológicas no cerradas
1. Verificar que la lista de 1005 pares corresponda al universo **exhaustivo**
   de chunks para las 30 consultas, no solo a un pool.
2. Inspeccionar `resumen_independencia_acl_original.json` y las
   condiciones de selección de la submuestra.
3. El acuerdo A/B sobre etiquetas consolidadas no permite declarar κ
   de dos anotaciones ciegas iniciales.
4. Congelar el nuevo reporte y citar sus hashes, sin reemplazar
   silenciosamente el informe histórico de 99 positivos.

Para la entrega del 23, priorizar reproducibilidad y límites
transparentes sobre entrenamientos nuevos o expansión del muestreo.


## Auditoría de exhaustividad del corpus de 30 consultas

El corpus privado `lote_estricto_30_anotacion/corpus_test_estricto_30.json`
contiene las propiedades superiores `version`, `tipo`,
`fragmentador`, `casos`. El repositorio genera fragmentos por consulta
con `chunks[].chunk_id`. Se incorporó
`scripts/auditar_cobertura_top3_1005.py` con pruebas unitarias para
contrastar **la totalidad** de pares corpus vs. anotación, además de
verificar que los Top-3 recuperados pertenecen al corpus.

```powershell
git pull --ff-only
$original = "C:\Users\juan sanz\Downloads\IAandes\microproyecto-local-citation-actualizado"
$base = Join-Path $original "proyecto_de_grado\artifacts\top3_test_preparacion"
$rank = Join-Path $base "evaluacion_modelos_reservada"
.\.venv-ms\Scripts\python.exe scripts/auditar_cobertura_top3_1005.py --corpus "$base\lote_estricto_30_anotacion\corpus_test_estricto_30.json" --etiquetas "artifacts\top3_etiquetas_pareadas_1005.csv" --bm25 "$rank\ranking_bm25.json" --scibert "$rank\ranking_scibert.json" --salida "artifacts\auditoria_cobertura_top3_1005.json"
```

Estado `exhaustivo`, faltantes/sobrantes 0 y `rankings_validos=true`
demuestran únicamente exhaustividad **respecto del corpus
fragmentado de estos 30 casos**, no respecto a artículos fuera del
archivo, ni doble anotación ciega. No cambiar ni sobreescribir el
resultado Top-3 previo.
