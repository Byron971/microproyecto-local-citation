# clasificacion-funcion

Clasificacion supervisada de la funcion de la cita (9 clases, entropia cruzada)
con dos encoders cientificos (SciBERT y SPECTER) y dos entradas (A: contexto +
titulo/abstract del citado; B: contexto + seccion + chunks Top-3), evaluados
sobre el mismo Test Gold (issue #103, A4).

Todo resultado es **PROVISIONAL** mientras el Gold humano v2 no este congelado
(#100): las etiquetas de entrenamiento son de Haiku.

Paquete hermano de `recuperacion-densa` (no lo extiende: su validacion bloquea
todo lo que no sea split train).

## Uso

```bash
uv sync --locked          # sin torch
uv run pytest -q
uv sync --group modelo    # opt-in: instala torch (CUDA 12.8)
```

## Trazabilidad: campo `git` de los manifiestos

Cada manifiesto (`manifiesto_preparacion.json`, `manifiesto_recuperacion.json`,
`manifiesto_entradas.json` y el de cada corrida) registra el estado de git:

| Campo | Significado |
|---|---|
| `head` | Commit sobre el que se ejecuto el paso. |
| `dirty` | `true` solo si habia cambios en el **codigo** (todo salvo `proyecto_de_grado/docs/evidencias_clasificacion_a4/`). |
| `evidencia_sin_commit` | `true` si habia evidencia generada por el propio flujo sin commitear. |

Cada paso del flujo escribe archivos nuevos en la carpeta de evidencias, asi que
`evidencia_sin_commit: true` es lo normal cuando se commitea al final. Para una
reproduccion limpia basta con `dirty: false`.

**Manifiestos generados el 2026-11-06 (antes de este cambio).** Registraban un unico
`dirty` que incluia la evidencia; por eso casi todos dicen `dirty: true`. El codigo en el
`head` registrado no difiere del HEAD actual: `git diff <head> HEAD -- packages scripts src
proyecto_de_grado/src` esta vacio (verificado con `81634c5` y `21496e0`). No se editaron
esos manifiestos a mano porque otros archivos referencian sus SHA.

## Flujo completo

Desde la raiz del repo. Todo paso que escribe evidencia **nunca sobrescribe** (borre antes lo que quiera regenerar).

| Paso | Comando | Red / GPU |
|---|---|---|
| 1. Conjuntos y fugas | `bash scripts/preparar_clasificacion_a4.sh` (envuelve `cli preparar`, `descarga_ocl`, `cli recuperar`, `cli entradas`) | red (OCL; los modelos se bajan antes con `descarga_modelo --encoder`), GPU para Top-3 |
| 2. Entrenar y predecir | `bash scripts/entrenar_clasificacion_a4.sh` (12 corridas + sondeo de secciones barajadas) | GPU |
| 3. Ablaciones | `ENTRADAS="" ENCODERS=scibert ABLACIONES=1 bash scripts/entrenar_clasificacion_a4.sh` | GPU |
| 4. Evaluar | `PYTHONPATH=. uv run --project packages/clasificacion-funcion python -m clasificacion_funcion.cli evaluar` | no |
| 5. Gold v2 | `... cli evaluar --gold-v2 <ruta privada>` (puntua las predicciones ciegas, sin reentrenar) | no |

`DRY=1` ensaya el entrenamiento con 64 casos y 1 epoca en `/tmp`. Los scripts exigen arbol git limpio (o `PERMITIR_SUCIO=1`).

## Modulos (`src/clasificacion_funcion/`)

| Modulo | Funcion | torch |
|---|---|---|
| `dominio.py` | taxonomia de 9 clases, abstenciones, metricas, fugas, construccion de entradas A/B/ablaciones, hash de especificacion | no |
| `servicio.py`, `comparacion.py`, `exportar.py` | casos, Top-3, interseccion A/B, comparacion y config `a4_factorial_v1` | no |
| `cli.py` | `preparar`, `recuperar`, `entradas`, `evaluar` | no |
| `adaptador_proyecto_grado.py` | unico modulo que importa `proyecto_de_grado.*`/`src.*` | no |
| `revision.py`, `descarga_modelo.py`, `descarga_ocl.py` | revisiones fijadas (SciBERT, SPECTER) y descargas | no |
| `clasificador_torch.py`, `cli_modelo.py` | clasificador `[CLS]` + `Linear(768, 9)`, `entrenar` y `predecir` | si |

Instalar el grupo `modelo` (torch) solo para entrenar y predecir; el resto, y la CI, corren sin torch.

## Evidencia y resultados

- Evidencia versionada: `proyecto_de_grado/docs/evidencias_clasificacion_a4/` (por corrida: `manifiesto.json`, `metricas_{val,eval}.json`, `predicciones_{eval,gold_v2}.jsonl`). Checkpoints y entradas con texto, en `proyecto_de_grado/artifacts/clasificacion_a4/` (gitignored).
- Informe: `proyecto_de_grado/docs/clasificacion_funcion_a4.md`. Analisis: `notebooks/03_clasificacion_funcion_a4.ipynb`.
- Resumen provisional (F1 macro, eval 2015 con etiquetas Haiku, 3 semillas): SciBERT-A 0,467, SciBERT-B 0,472, SPECTER-A 0,330, SPECTER-B 0,302. A frente a B no se distingue del ruido; SciBERT supera a SPECTER.
- **Bloqueo de cobertura:** la Entrada B cubre ~54 % de los casos (umbral 60 %), por parrafos largos que descarta A1.
- Las predicciones nunca incluyen la etiqueta verdadera.
