# Runbook — experimentos SciBERT/SPECTER (issue #104)

> **Todo es provisional** hasta evaluar contra el Test Gold humano. Las métricas son contra la
> validación fija V (`val`), `dev_haiku` y `ref_gpt`; las etiquetas no son humanas.

## Qué hace
`notebooks/04_experimentos_scibert_104.ipynb` orquesta (la lógica está en
`clasificacion_funcion.{seleccion_datos,experimento_104,registro_mlflow}`): datos limpios →
TF-IDF → SciBERT-A en D1–D6 → variantes de pérdida → SPECTER → semillas → smoke test →
manifiesto. Todo queda en MLflow, experimento `clasificacion-funcion-104`.

## Regla anti-fuga
Se excluyen los citantes de **2014 y 2015** (todo `val` y `test` de `data/raw`: el Test Gold
mezcla 1.299 casos de 2014 y 1.379 de 2015), el manifiesto v2, TG2700, taller y piloto, más los
citantes y textos de esos casos. `verificar_fugas` falla cerrado y el resultado queda en
`manifiesto_datos.json`.

## Insumos (no versionados; sha256 en `evidencias_experimentos_104/manifiesto_datos.json`)
- `local_workflows/qlora_18000_preds_v2.jsonl` y `local_workflows/subconjuntos_qlora/*_qlora_v2_preds.jsonl`
- `v3_Jueces/jurado_18000_v3.csv`, `v3_Jueces/referencia_gpt_200.jsonl`
- `local_workflows/ANOTACION_UNICA_2700_CITAS_REALES_ANOTADO.csv`, `local_workflows/qlora_split_v2.json`
- `data/raw/*.json`; encoders SciBERT y SPECTER ya descargados (sin red de noche).

## Instalación
```bash
cd packages/clasificacion-funcion
uv sync --group modelo --group experimentos
uv run python -m ipykernel install --user --name clasificacion-funcion
```

## Prueba en seco (~2 min)
Con `DRY = True` en la celda de parámetros (64 casos, 1 época; usa el experimento
`clasificacion-funcion-104-dry` y carpetas `*_dry`, que se pueden borrar):
```bash
cd notebooks
uv run --project ../packages/clasificacion-funcion jupyter nbconvert --to notebook --execute \
  --output-dir /tmp --output dry.ipynb 04_experimentos_scibert_104.ipynb
```

## Corrida nocturna (~5 h)
Poner `DRY = False` y lanzar:
```bash
cd notebooks
nohup uv run --project ../packages/clasificacion-funcion jupyter nbconvert --to notebook --execute \
  --inplace --ExecutePreprocessor.timeout=-1 04_experimentos_scibert_104.ipynb > ../noche_104.log 2>&1 &
```
- `HORAS_MAX` (def. 7) omite las fases restantes.
- Cada run va en try/except: queda FAILED en MLflow y el notebook sigue (ver `FALLAS`).
- **Reanudable**: se salta todo run FINISHED con el mismo tag `config_sha`. Si se corta, relanzar igual.

## Resultados
- MLflow: `uv run mlflow ui --backend-store-uri sqlite:///mlflow.db` (desde la raíz).
- Checkpoints (~440 MB c/u): `proyecto_de_grado/artifacts/experimentos_104/corridas/<run>/` (ignorado por git; MLflow guarda ruta y sha).
- Evidencias: `proyecto_de_grado/docs/evidencias_experimentos_104/` — `manifiesto_datos.json`,
  `auditoria_fuentes.json`, `smoke_inferencia.json`, `manifiesto_experimentos.csv/json`.
- Los 18 runs de #103 se registran sin reentrenar con `registro_mlflow.registrar_corridas_a4`.

## Fases opcionales
- **7 (entrada B)** y **8 (D7 Sonnet)** quedan registradas como omitidas mientras no existan
  `artifacts/experimentos_104/entrada_b/` ni `artifacts/anotacion_sonnet/etiquetas_sonnet.csv`.

## Pendiente tras la corrida
La interpretación breve de resultados que pide el issue se escribe después, con los números reales.

---

# Parte 2: pista Sonnet, grilla de hiperparámetros, épocas y arreglo de la pérdida

Notebook `notebooks/05_experimentos_104_part2.ipynb` (orquestador; el 04 queda como registro de la Parte 1).
Mismo experimento MLflow, así que los runs de la Parte 1 con la misma configuración se reanudan.

## Pistas de etiquetas
- **Pista M («mixta»)**: entrenamiento D1–D6 (QLoRA, jurado, Haiku); V con la mejor etiqueta disponible.
- **Pista S («sonnet»)**: entrenamiento D7 `sonnet` (todas las citas de D1 con etiqueta Sonnet), D8 `sonnet_alta`
  (solo confianza Alta) y D9 `sonnet_cap` (tope por clase, Alta primero); V con etiquetas Sonnet (`v_sonnet`, las mismas citas).
- Dentro de una pista, early stopping y elección usan **su** `val`. **`val` no es comparable entre pistas**: todo run
  también se evalúa en `val_mixta`, `val_sonnet`, `dev_haiku` y `ref_gpt`. La comparación final espera al Test Gold.
- Las etiquetas Sonnet se consolidan en `proyecto_de_grado/anotacion/sonnet/etiquetas_sonnet.csv`
  (`scripts/anotar_sonnet.py consolidar`; el notebook lo hace en la fase 0).

## Runs de la Parte 1 inválidos
`preparar_ejemplos` descartaba `objetivo` y `peso`, así que `scibert-A-natural-kd-s42` y
`scibert-A-natural-ponderado-s42` fueron copias del run duro. Ya está corregido; la fase 0 los marca
(`registro_mlflow.invalidar`: tag `invalido=<motivo>` + KILLED) junto con `tfidf-lr-d1` (se re-corre para tener los
conjuntos nuevos). No se reanudan y se excluyen de las tablas.

## Fases
| Fase | Qué corre |
|---|---|
| 0 | Datos (D1–D9, V, V_sonnet), fugas = 0, manifiesto, invalidar los 3 runs |
| 1 | Re-evaluar 10 checkpoints de la Parte 1 en `val_mixta`/`val_sonnet` (`ex.reevaluar_checkpoint`, sin reentrenar) |
| 2 | Pista M: TF-IDF, `kd` y `ponderado` sobre `natural` (s42) |
| 3 | Pista S: TF-IDF y SciBERT en D7, D8, D9 (s42) |
| 4 | Grilla por pista sobre su mejor configuración: lr {1e-5, 3e-5, 5e-5} × épocas {4, 10}, paciencia 3 (alterna pistas) |
| 5 | Semillas 1234 y 2026 de la mejor configuración de cada pista |
| 6 | SPECTER con la mejor configuración de cada pista |
| 7 | Smoke test de inferencia de los 2 ganadores |
| 8 | Tablas por pista, media ± std entre semillas, bootstrap pareado, `resumen_part2.csv` y manifiesto |

Regla de elección: dentro de una pista, mayor macro-F1 en su propia `val`. Micro-lote (8) y `max_len` (512) no cambian
en la grilla; ante `OutOfMemoryError` se reintenta una vez con micro-lote 4 y acumulación 4. El pico de memoria queda
en MLflow (`gpu_mem_pico_gb`).

## Comandos
Primero `DRY = True` en la celda de parámetros (experimento `-dry`, 64 casos, 1 época):
```bash
cd notebooks && uv run --project ../packages/clasificacion-funcion jupyter nbconvert --to notebook --execute \
  --output-dir /tmp --output dry_part2.ipynb 05_experimentos_104_part2.ipynb
```
Luego `DRY = False` y la noche (`HORAS_MAX = 10`):
```bash
cd notebooks
nohup uv run --project ../packages/clasificacion-funcion jupyter nbconvert --to notebook --execute \
  --inplace --ExecutePreprocessor.timeout=-1 05_experimentos_104_part2.ipynb > ../part2_104.log 2>&1 &
```
Vigilar `nvidia-smi` en el primer run. Disco: ~25 checkpoints nuevos × 440 MB ≈ 11 GB.

> **Entorno**: `mlflow.db` fue migrado con mlflow 3.18 (`local_workflows/.venv`); el entorno del paquete fija 3.15.1 y
> **no puede abrir esa base** («out-of-date database schema»). Antes de lanzar, alinear versiones (p. ej. subir `mlflow`
> en el grupo `experimentos`) o ejecutar con el entorno con el que se corrió la Parte 1. No migrar la base sin respaldo.

---

# Parte 3: Entrada B (contexto + Top-3 chunks) sobre los datos de #104

Notebook `notebooks/06_experimentos_104_entrada_b.ipynb` (orquestador; la lógica nueva está en
`clasificacion_funcion.entrada_b_104` y en `experimento_104`). Experimento MLflow aparte:
`clasificacion-funcion-104-b` (no toca las tablas ni la reanudación del notebook 05).

## Por qué
A4 (#103) comparó A vs B con solo 1.241 casos (SciBERT A→B = +0,005, IC95 [−0,021; +0,032]). Los notebooks 04/05 armaron
~13k casos por pista pero solo corrieron la Entrada A. Aquí se entrena **A y B** con exactamente las mismas citas, etiquetas,
hiperparámetros y semillas, y se deja listas las predicciones ciegas para el Test Gold.

**Los modelos de #104 no se prueban con inputs B**: fueron entrenados con A, y darles chunks mide el desajuste de formato, no el
efecto de los chunks. Sus `predicciones_val.jsonl` (entrada A) restringidas a V_B solo sirven de referencia.

## Diseño (preregistrado en `evidencias_experimentos_104_b/preregistro_b.json` antes de cualquier run)
- Pistas: **M** `natural` + `kd`; **S** `sonnet` + pérdida dura. Hiperparámetros: lr 3e-5, 4 épocas, paciencia 3, batch 8 (×2), `max_len` 512; **sin ajuste con B**.
- Semillas 42, 1234, 2026. Núcleo: 2 pistas × {A, B} × 3 semillas = 12 corridas. Opcionales (`HORAS_MAX`): `B_barajada` y SPECTER A/B s42.
- Train = train ∩ cobertura B ∩ filtros de fuga. **V_B = V ∩ cobertura B**, para el early stopping en A y en B.
- Regla de decisión: «B ayuda en la pista X» solo si las 3 parejas de semillas tienen el mismo signo **y** el IC95 (bootstrap por citante) excluye 0.

## Controles de fuga (todos fallan cerrado; resultado en `fugas_b.json`)
| # | Control |
|---|---|
| L1 | Reglas de contexto de #104 (`sd.construir_todo`/`verificar`): 0 |
| L2 | **Fuga propia de B**: se descartan de train (en A y en B) las citas cuyo citado es citante de V ∪ Gold v2 ∪ TG2700 ∪ excluidos. Con B su input llevaría texto completo de esos citantes (frases de citas de V/Gold). 388 `natural` / 392 `sonnet` citan citantes de V; con Gold/TG2700/excluidos suman 538 / 561 |
| L3 | Ninguna cita de V cita a un citante del Gold: 0 |
| L4 | Ningún chunk que entra a un input comparte ≥50 % de shingles de 8 palabras con un contexto de V o del Gold (\|chunk ∩ contexto\| / min de ambos). Detecta el mismo artículo bajo otro ID (p. ej. `P97-1063` en el train y su gemelo `E97-1063` como citante de V) o texto reutilizado por los mismos autores; en una prueba a escala real, con los 3 primeros chunks como sustituto del Top-3, ya aparecen 3 chunks de train frente a V y 1 frente al Gold. **Con `L4_DESCARTAR = True` (def.) se descartan del train/V, en A y en B, todas las citas cuyo citado tiene algún chunk que solapa (conteo por clase en `fugas_b.json`) y L4 se re-ejecuta: lo que entra a los inputs debe quedar en 0.** `L4_DESCARTAR = False` aborta en su lugar |
| L5 | A y B usan exactamente los mismos ids (sha de ids por pista, train y V_B) |
| L6 | Recuperador sin ajustar (SciBERT base, revisión de A1) y heurística `perfil_seccion`: no ven etiquetas. Regresión contra los `top3_*.csv` de A4: mismos `chunk_id` y orden |
| L7 | Nada se elige con datos de test: `TEST_GOLD_2700_ANOTADO.csv` no se carga nunca; del Gold solo ids; las predicciones del Gold se escriben sin etiquetas (`{context_id, pred, probs}`) |
| L8 | Solo reporte: estratos citado visto/no visto en train; citas del Gold que citan a citantes de V/train |

## Fases del notebook
| Fase | Qué hace |
|---|---|
| 0 | Datos de #104 (se comprueba que coinciden por sha con `evidencias_experimentos_104/manifiesto_datos.json`), L1–L3, preregistro |
| 1 | Citados requeridos y **descarga con red** (`DESCARGAR = True`, solo de día) |
| 2 | Chunks + Top-3 en GPU (`top3_<conjunto>.csv`), regresión L6 contra A4 |
| 3 | `servicio.interseccion` (cobertura por conjunto y clase, ≈55 %), L4, L5, `fugas_b.json`, `manifiesto_datos_b.json` |
| 4 | Núcleo: 12 corridas, alternando pista/entrada dentro de cada semilla |
| 5 | Referencia: ganadores de #104 (entrada A) sobre V_B, sin reentrenar |
| 6 | Opcionales: `B_barajada` y SPECTER (sujetos a `HORAS_MAX`) |
| 6b | Smoke test: un checkpoint B (y `B_barajada`) por pista reproduce sus predicciones de `val` guardadas |
| 7 | Predicciones ciegas sobre Gold v2: B y A sobre Gold ∩ cobertura (pareado) y A sobre todo el Gold v2; sha256 en `manifiesto_gold_b.json` |
| 8 | Bootstrap por clústeres, tablas secundarias, F1 por clase, estratos, truncamiento, `resumen_b.csv`, `bootstrap_b.json`, manifiesto MLflow |

## Comandos
1. **Descarga (de día, con red).** En la celda de parámetros poner `DESCARGAR = True` y ejecutar hasta la fase 1. Baja de HuggingFace (ACL-OCL,
   público) los ~1.830 citados que faltan en `proyecto_de_grado/scripts/spike_enlace_datos/cache_ocl`; solo se envían ids de artículos ACL. 30–60 min.
   Deja `citados_requeridos_b.txt` y `manifiesto_ocl_b_<n>.json` en la carpeta de evidencias. Luego volver a `DESCARGAR = False`.
2. **Prueba en seco** (`DRY = True`; ≤300 citas por conjunto, 64 casos y 1 época por run; experimento `clasificacion-funcion-104-b-dry`,
   carpetas `*_b_dry`, borrables). Debe terminar todas las fases con `fugas_b.json` en ceros, shas de ids A/B iguales y la regresión L6 sin discrepancias:
   ```bash
   cd notebooks && uv run --project ../packages/clasificacion-funcion --group modelo --group experimentos \
     jupyter nbconvert --to notebook --execute --output-dir /tmp --output dry_b.ipynb 06_experimentos_104_entrada_b.ipynb
   ```
3. **Corrida real de noche** (`DRY = False`, `HORAS_MAX = 8`; sin red):
   ```bash
   cd notebooks
   nohup uv run --project ../packages/clasificacion-funcion --group modelo --group experimentos jupyter nbconvert --to notebook --execute \
     --inplace --ExecutePreprocessor.timeout=-1 06_experimentos_104_entrada_b.ipynb > ../b_104.log 2>&1 &
   ```
   Reanudable: se salta todo run FINISHED con el mismo `config_sha`, y `top3_*.csv` ya calculados no se recalculan.

Tiempos (RTX 4070 SUPER): descarga 30–60 min · embeddings 20–40 min · núcleo ≈ 2 h (train ≈ 7k casos; A ≈ 7 min, B ≈ 12 min por run) · opcionales ≈ 1,5 h.
Disco: 12 corridas del núcleo + 10 opcionales (6 `B_barajada` + 4 SPECTER) × 440 MB ≈ 10 GB.

## Dónde queda todo
- Artefactos (ignorados por git): `proyecto_de_grado/artifacts/experimentos_104_b/` — `corridas/<run>/` (checkpoint, `predicciones_val.jsonl`) y `gold_v2/<run>/pred_gold_v2_{cob,todo}.jsonl`.
- Evidencias: `proyecto_de_grado/docs/evidencias_experimentos_104_b/` — `preregistro_b.json`, `fugas_b.json`, `manifiesto_datos_b.json`,
  `manifiesto_recuperacion_b.json`, `top3_*.csv`, `excluidos_b.csv`, `manifiesto_gold_b.json`, `bootstrap_b.json`, `analisis_b.json`, `resumen_b.csv`, `manifiesto_experimentos.csv/json`.

## Salvedades
- Los resultados valen para citas cuyo citado es fragmentable (~55 %: la regla de A1 descarta artículos con párrafos de más de 300 palabras); la mezcla de clases cambia.
- La relevancia del Top-3 no está validada (#127): un resultado nulo de B puede reflejar la calidad de la recuperación.
- Sobre Gold ∩ cobertura (~839 citas) el IC pareado será de ±0,04–0,06; un efecto pequeño (A4 vio +0,005) no se podrá resolver allí.
- V_B sigue siendo fidelidad al maestro (QLoRA/Haiku/Sonnet), no verdad humana: decide el Test Gold.
- **Entorno**: igual que en la Parte 2, el `mlflow.db` real tiene el esquema de mlflow 3.18 y el entorno del paquete (3.15.1) no lo abre. Alinear versiones antes
  de la corrida real; para la prueba en seco basta `MLFLOW_TRACKING_URI=sqlite:////ruta/temporal.db`.

---

# Parte 3 v2: Entrada B corregida (dev propio, brazo AB, grilla de lr, 5 semillas y controles)

El mismo notebook `notebooks/06_experimentos_104_entrada_b.ipynb`, corregido en su lugar. La v1 (commit `63a3604`) queda en
`evidencias_experimentos_104_b/` y en git. La v2 escribe en `artifacts/experimentos_104_b_v2/`, `docs/evidencias_experimentos_104_b_v2/`
y en el experimento MLflow `clasificacion-funcion-104-b-v2`. El diseño completo está en la celda 0 del notebook y queda fijado en
`preregistro_b_v2.json`.

## Diseño
- **Primario: AB − A** (A intacta + `perfil : chunk` × 3 en los tokens sobrantes), por pista (M: `natural` + `kd`; S: `sonnet` + `duro`).
  Secundario: B − A, con la salvedad de constructo (las etiquetas se formaron con la información de A).
- **Dev** para la parada temprana: `sha256("dev-104-b-v2:" + citing_id) % 100 < 15` sobre el train de cobertura B. V_B solo se evalúa.
- **Grilla de lr** {2e-5, 3e-5, 5e-5} × {A, B, AB} × 2 pistas × semillas {42, 1234}; 6 épocas, paciencia 2. Se elige la mayor media de
  F1-macro de dev (empate: lr menor) y queda en `seleccion_lr.json`.
- **Núcleo**: 5 semillas (42, 1234, 2026, 7, 31337) × {A, B, AB} × 2 pistas. **Controles** (42, 1234, 2026): AB_aleatorio, B_aleatorio,
  B_sin_seccion, B_barajada, C0; A-rep (A-M-s42 repetido); SPECTER A, B, AB s42.
- **Inferencia**: prueba t con varianza de semillas + artículos (bootstrap por citante, 5000 réplicas, semilla 2026), Holm sobre las 2
  primarias, TOST con δ = 0,02 en familia aparte. Veredicto: `incompleto` → `mejora`/`empeora` (p_Holm < 0,05 y ≥ 4 de 5 d_j con el signo
  de d̄) → `equivalente` (p_TOST,Holm < 0,05) → `no_concluyente`. Poder declarado: MDE ≈ 0,023–0,027 (M) y ≈ 0,029–0,034 (S).
- **Controles de fuga nuevos**: L2-dev, L1 sobre {train, dev, V, Gold}, L10 (contextos casi duplicados entre train, dev y V), L4 sobre
  todos los chunks de cada citado, L5 entre A y cada una de las 7 entradas restantes, L9 (A es prefijo de AB salvo ≤ 3 tokens del abstract).

## Flujo
La corrida real se hace en 2 tandas de ejecución con un commit en medio:

1. **Prueba en seco** (`DRY = True`, ≤ 300 citas por conjunto, 64 casos y 1 época por run, grilla de 2 lr, núcleo = semillas de la grilla,
   controles con s42; carpetas `*_b_v2_dry` y experimento `-dry`, borrables). El gate se omite y el preregistro DRY se reescribe.
   El notebook versionado lleva `DRY = False`: para la prueba en seco se ejecuta una copia con `DRY = True` (y `DESCARGAR = False` si la
   caché de ACL-OCL ya está completa):
   ```bash
   cd notebooks
   python3 -c "import json; nb = json.load(open('06_experimentos_104_entrada_b.ipynb')); c = nb['cells'][2]; s = ''.join(c['source']).replace('DRY = False', 'DRY = True', 1); c['source'] = s.splitlines(keepends=True); json.dump(nb, open('_dry_06_v2.ipynb', 'w'), ensure_ascii=False, indent=1)"
   uv run --project ../packages/clasificacion-funcion --group experimentos jupyter nbconvert --to notebook --execute \
     --ExecutePreprocessor.kernel_name=qlora --ExecutePreprocessor.timeout=-1 --output-dir /tmp --output dry_b_v2.ipynb _dry_06_v2.ipynb
   rm _dry_06_v2.ipynb
   ```
   El kernel `qlora` es `local_workflows/.venv-qlora` (mlflow 3.18, el esquema de `mlflow.db`).
2. **Preparación** (`DRY = False`): revisar δ = 0,02 y los flags `CORRER_*` en la celda 2 y ejecutar el notebook. Descarga los citados
   que faltan, recalcula los `top3_*.csv` en la carpeta v2, escribe `fugas_b.json`, `manifiesto_datos_b.json` y `preregistro_b_v2.json`
   y **se detiene en el gate** (≈ 15 min) con «el preregistro, el manifiesto o el código difieren de HEAD».
3. **Commit** de `preregistro_b_v2.json`, `manifiesto_datos_b.json`, el código de `packages/clasificacion-funcion/src` y el notebook.
   El gate exige que esos archivos estén en HEAD sin cambios y que `huella_codigo()` coincida con la del preregistro y con la del
   notebook de HEAD (los outputs no cuentan).
4. **Primera tanda** de la corrida real (`HORAS_MAX = 14`; al superarlo, `correr()` omite los runs restantes):
   ```bash
   cd notebooks
   nohup uv run --project ../packages/clasificacion-funcion --group experimentos jupyter nbconvert --to notebook --execute \
     --ExecutePreprocessor.kernel_name=qlora --inplace --ExecutePreprocessor.timeout=-1 06_experimentos_104_entrada_b.ipynb > ../b_104_v2.log 2>&1 &
   ```
5. **Segunda tanda**: el mismo comando. Todo run FINISHED con el mismo `config_sha` se reanuda, los `top3_*.csv` no se recalculan y el
   preregistro se recalcula y compara (si el diseño cambió, el notebook se detiene). Repetir hasta que no queden runs omitidos.
6. Revisar `seleccion_lr.json`, `bootstrap_b.json` y `analisis_b.json`, y agregar al final del notebook la celda «Conclusiones»
   (distinguir `no_concluyente` de `equivalente` y citar el poder declarado).

Si la grilla queda incompleta (falta algún run), `seleccionar_lr` lanza «grilla de lr incompleta: faltan …» y el notebook se detiene;
la siguiente ejecución reanuda los runs hechos y corre los que faltan.

## Tiempos y disco
RTX 4070 SUPER, runs de 6 épocas: A ≈ 7,5 min; B, AB y variantes ≈ 12 min; C0 ≈ 5 min.

| Bloque | Runs | Horas |
|---|---|---|
| Grilla | 36 | ≈ 6,3 |
| Núcleo (2026, 7, 31337) | 18 | ≈ 3,2 |
| AB_aleatorio, B_aleatorio, B_sin_seccion, B_barajada | 24 | ≈ 4,8 |
| C0 y A-rep | 7 | ≈ 0,6 |
| SPECTER | 6 | ≈ 1,1 |
| Top-3, datos, V completo, Gold y análisis | — | ≈ 0,8 |
| **Total** | **91** | **≈ 17 h (2 tandas)** |

Disco: ≈ 40 GB en `artifacts/experimentos_104_b_v2/` (91 × 440 MB), más la prueba en seco (10–25 GB, borrable).

**Borrado opcional** de los checkpoints de los lr no elegidos (después de revisar `seleccion_lr.json`; ≈ 10,5 GB). Las predicciones y
los manifiestos se conservan:
```bash
cd proyecto_de_grado/artifacts/experimentos_104_b_v2/corridas
python3 - <<'PY'
import json
import re
from pathlib import Path
elegido = {k: v["lr"] for k, v in json.loads(Path("../../../docs/evidencias_experimentos_104_b_v2/seleccion_lr.json").read_text()).items()}
for d in sorted(Path(".").iterdir()):
    m = re.fullmatch(r"scibert-(A|B|AB)-(M|S)-lr(.+)-s(\d+)", d.name)
    if m and float(m[3]) != elegido[f"{m[2]}:{m[1]}"] and (d / "model.safetensors").is_file():
        print("borra", d / "model.safetensors")
        (d / "model.safetensors").unlink()
PY
```

## Dónde queda todo
- Artefactos (ignorados por git): `proyecto_de_grado/artifacts/experimentos_104_b_v2/` — `corridas/<run>/` (checkpoint,
  `predicciones_val.jsonl`, `predicciones_vcompleto.jsonl` en A del núcleo, `manifiesto_entrenamiento.json` con `metricas_parada`) y
  `gold_v2/<run>/pred_gold_v2_{cob,todo}.jsonl`.
- Evidencias: `proyecto_de_grado/docs/evidencias_experimentos_104_b_v2/` — `preregistro_b_v2.json`, `gate_preregistro.json`,
  `fugas_b.json`, `manifiesto_datos_b.json`, `manifiesto_recuperacion_b.json`, `top3_*.csv`, `excluidos_b.csv`, `seleccion_lr.json`,
  `smoke_inferencia_b.json`, `manifiesto_gold_b.json`, `bootstrap_b.json`, `analisis_b.json`, `resumen_b.csv`, `manifiesto_experimentos.csv/json`.
- Nombres de run: `{encoder}-{entrada}-{pista}-lr{lr}-s{semilla}` (`-rep1` en A-rep).
