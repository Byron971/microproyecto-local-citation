# G1.3 — Reproducción independiente y revisión del equipo

**Estado:** listo para comparación técnica independiente, **no** validación humana completada.  
**Rama:** `audit/preetiquetado-g0`. No fusionar a `main` hasta superar las puertas acordadas.

## Qué está y qué no está en GitHub

Disponibles y versionados:
- Reconstructor `proyecto_de_grado/src/data/reconstruir_oraciones.py` y sus pruebas.
- Inspector `proyecto_de_grado/src/data/inspeccionar_alineacion.py`.
- Baseline de **cinco** casos `proyecto_de_grado/anotacion/baseline_reconstruccion_g1_2.jsonl`.
- Reproductor independiente `proyecto_de_grado/scripts/reproducir_g1_3_equipo.py`.
- Protocolo `proyecto_de_grado/docs/protocolo_validacion_reconstruccion_g1_3.md`.
- Plantilla `proyecto_de_grado/anotacion/plantilla_revision_reconstruccion_g1_3.csv`.
- Evidencias originales compartidas por el equipo, en `proyecto_de_grado/docs/evidencias_g1/`:
  `g1_1_inspeccion_cinco_casos.txt`, `g1_2_reconstruccion_inicial.txt` y
  `g1_2_reconstruccion_corregida.txt`. Son reportes históricos **de desarrollo**
  y contienen extractos de publicaciones académicas; no son etiquetas Gold.
  Se conservan para transparencia y comparación, con fines académicos
  y respetando los derechos de las fuentes ACL/ACL OCL.

No publicados intencionalmente:
- `data/raw/` (se recupera con DVC, descriptor `data/raw.dvc`).
- Caché completa `cache_ocl/` (JSON derivados de artículos, excluidos por Git).
- Reportes locales `proyecto_de_grado/artifacts/auditoria_acl_ocl/`, también ignorados.

**No usar git add -f para subir la caché o los datos crudos**: tienen tamaño considerable y restricciones de procedencia/licencias. El baseline contiene únicamente estados y las dos oraciones enmascaradas necesarias para comparar.

## Para la persona encargada de reproducir

Desde la raíz del repositorio, con entorno Python activo:

```powershell
git fetch origin
git switch -c audit/preetiquetado-g0 --track origin/audit/preetiquetado-g0
# Si la rama ya existe: git switch audit/preetiquetado-g0
# Recuperar data/raw desde el remoto DVC autorizado, si no está presente:
dvc pull data/raw.dvc
# Ejecutar pruebas locales sin proveedor de IA:
python -m pytest -q proyecto_de_grado/tests/test_reproducir_g1_3_equipo.py proyecto_de_grado/tests/test_reconstruir_oraciones.py
# Descargar SOLO los 8 JSON citantes/citados necesarios si no hay caché:
python -m proyecto_de_grado.scripts.reproducir_g1_3_equipo --descargar-faltantes
```

El comando final no utiliza el CSV local ni los resultados de la máquina original; reconstruye la ubicación de cada contexto desde ACL-200, aplica el mismo código G1.2 y compara cada registro con el baseline. **Requiere acceso al remoto DVC del proyecto.** La descarga de hasta ocho documentos de ACL OCL es explícita; si ya están en caché se reutilizan.

El reporte se escribe localmente en `proyecto_de_grado/artifacts/auditoria_acl_ocl/reproduccion_g1_3_equipo.jsonl` (ignorados por Git). Si hay diferencias de estado, motivo, ID bibliográfico o oración enmascarada, se registran. Si el script falla por falta de DVC o red, reportarlo como problema de **entorno**, no como evidencia científica de que la alineación es incorrecta.

## Revisión independiente (humana)

1. Leer `protocolo_validacion_reconstruccion_g1_3.md`. Analizar los cinco `context_id` desde sus contextos originales y JSON OCL; **primero juzgar la correspondencia sin utilizar como respuesta la opinión de IA**.
2. Marcar en una copia de `plantilla_revision_reconstruccion_g1_3.csv` (NO sobreescribir la plantilla) para cada caso: aprobar/rechazar/corregir/pendiente; `cited_id`, `BIBREF`, offsets del `cite_span`, oración exacta, observaciones y justificación.
3. Comparar la reproducción del compañero con el baseline y el informe de revisión preliminar. Notificar diferencias, si las hay, con evidencia puntual; crear PR con su revisión, **sin incluir caché ni datos crudos**.
4. Mantener todos estos casos fuera del nuevo Test Gold independiente. Una validación de **oraciones** no equivale a validar la **función retórica** (objetivo del 15 % humano).

## Resultado preliminar publicado (NO humano)

Basado en los archivos locales de inspección y reconstrucción compartidos por el equipo, un revisor de IA observa:

| ID | Reconstrucción G1.2 | Revisión técnica preliminar de IA |
| --- | --- | --- |
| `P14-1048_P12-1007_0` | candidata | Coherente: Feng & Hirst 2012, `BIBREF4`, oración con `(TARGETCIT).`; confirmar identidad contra bibliografía original |
| `W09-0704_E89-1009_0` | candidata | Coherente: Evans & Gazdar 1989, `BIBREF4`, oración con `(TARGETCIT).`; confirmar identidad contra bibliografía original |
| `P14-1048_P12-1007_2` | revisión manual | Abstención justificada por grupo `(OTHERCIT; TARGETCIT; OTHERCIT)` |
| `D15-1288_P09-2086_0` | revisión manual | Abstención justificada por grupo con `OTHERCIT` |
| `W15-2710_P11-1082_0` | revisión manual | Abstención justificada por grupo con `OTHERCIT` |

**Límite del juicio de IA:** no se han cotejado independientemente los PDF/JSON completos en esta revisión. Las dos reconstrucciones son **plausibles y estructuralmente consistentes**, no aprobaciones humanas; una referencia `BIBREF` válida por similitud de título y offsets no prueba infaliblemente la identidad de TARGETCIT. Las tres abstenciones son conservadoras; el compañero puede proponer desambiguación sustentada.

## Criterio de terminación de la tarea del compañero

Reproducción de 5/5 con reporte, hoja de revisión humana de 5 casos, identificación de divergencias/errores y evidencia bibliográfica. No asumir "todo correcto" solo por obtener 5/5 coincidencias: la comparación técnica y la validación científica son controles distintos.
