# Clasificación de la función de la cita: SciBERT/SPECTER × Entrada A/B (A4, issue #103)

> **Estado: PROVISIONAL.** Entrenamiento y evaluación usan etiquetas de **Haiku**; el Gold humano v2 **no está congelado** (#100). Ninguna cifra de este documento es un resultado final ni debe llamarse «Gold humano».

## 1. Qué se hizo
Se entrenó un clasificador de 9 clases (`[CLS]` + dropout 0,1 + `Linear(768, 9)`, entropía cruzada con pesos inversos a la frecuencia) sobre **dos encoders** y **dos entradas**, con los mismos hiperparámetros, tres semillas y el mismo conjunto de evaluación:

| Encoder | Entrada A: contexto + título/abstract del citado | Entrada B: contexto + (sección : chunk) × Top-3 |
|---|---|---|
| SciBERT (`allenai/scibert_scivocab_uncased`, rev. `24f92d32`) | SciBERT-A | SciBERT-B |
| SPECTER (`allenai/specter`, rev. `81cbfb43`) | SPECTER-A | SPECTER-B |

Más las ablaciones de sección con SciBERT (refs #128): `B_sin_seccion`, `B_barajada` (secciones permutadas dentro de cada conjunto, sembradas) y un sondeo sin reentrenar (modelo B evaluado con secciones barajadas). En total **18 corridas** (12 de la matriz + 6 de ablación).

- Paquete: `packages/clasificacion-funcion` (ver su README). Orquestación: `scripts/preparar_clasificacion_a4.sh` y `scripts/entrenar_clasificacion_a4.sh`.
- Evidencia: `proyecto_de_grado/docs/evidencias_clasificacion_a4/`. Análisis: `notebooks/03_clasificacion_funcion_a4.ipynb`.
- «Sección» = `perfil_seccion` del chunk citado: una **heurística por palabras clave, no una etiqueta retórica validada**.

## 2. Datos
| Conjunto | Origen | Candidatos | Intersección A/B |
|---|---|---|---|
| train | Haiku Evaluable, split agrupado por citante (`qlora_split_v2.json`) | 2.245 | 1.241 |
| val | idem | 397 | 213 |
| eval 2015 (**provisional**) | `TEST_GOLD_2700`, año 2015, etiquetas Haiku | 1.363 | **732** |
| Gold v2 (ciego) | 1.533 IDs sin etiquetas | 1.533 | 839 |

A y B usan **exactamente los mismos IDs** (intersección controlada). `fugas.json` reporta 0 intersecciones por `context_id`, `citing_id`, par citante–citado y texto TARGETCIT entre train, val y eval. El `cited_id` compartido solo se reporta (no bloquea), igual que en `validar_splits`: hay artículos citados presentes en varios conjuntos (ver el estrato «visto en train» en la sección 5).

**Abstenciones.** «Ambiguo» y «No evaluable» se cuentan aparte (`abstenciones.csv`) y nunca forman una décima clase.

## 3. Protocolo de entrenamiento (fijado antes de mirar el eval)
`max_len` 512; AdamW lr 2e-5, weight decay 0,01 (sin decay en bias/LayerNorm); warmup 10 % y decaimiento lineal; batch 8 × acumulación 2; máximo 6 épocas con parada temprana (paciencia 2) sobre F1 macro de val; bf16; clip 1,0; semillas 42, 1234 y 2026. Se conserva el checkpoint de la mejor época en val (`checkpoint_sha256` en cada manifiesto). Hardware: RTX 4070 SUPER; torch 2.11.0+cu128, transformers 5.22.2. Cada corrida de entrada B tarda ~160 s y cada A ~100 s.

## 4. Bloqueo de cobertura (a registrar en #103)
La Entrada B exige texto de chunks del citado, y la cobertura queda **bajo el umbral del 60 %** en todos los conjuntos:

| Conjunto | Cobertura | Excluidos por párrafo largo |
|---|---|---|
| train | 55,28 % | 991 |
| eval 2015 | **53,71 %** | 629 |
| Gold v2 | 54,73 % | 693 |

La causa dominante es la regla de A1, que descarta los artículos con párrafos de más de 300 palabras. **No se modificó esa regla.** Queda por abrir un issue aparte para evaluar otro fragmentador. Consecuencias: la intersección **no es una muestra aleatoria** y no conserva las clases por igual (en eval, Identification of the Originator conserva 7 de 21 casos, 33 %, mientras otras clases conservan entre 49 y 67 %).

## 5. Resultados provisionales (eval 2015, n = 732, media ± desviación entre 3 semillas)

| Celda | F1 macro | F1 micro (= accuracy) |
|---|---|---|
| SciBERT-A | 0,467 ± 0,033 | 0,610 ± 0,015 |
| SciBERT-B | 0,472 ± 0,029 | 0,611 ± 0,018 |
| SPECTER-A | 0,330 ± 0,032 | 0,539 ± 0,026 |
| SPECTER-B | 0,302 ± 0,044 | 0,526 ± 0,046 |

**Contrastes** (delta de F1 macro por semilla, media ± desviación):

| Contraste | Delta | Desv. |
|---|---|---|
| A → B, SciBERT | +0,005 | 0,004 |
| A → B, SPECTER | −0,027 | 0,024 |
| SciBERT → SPECTER, entrada A | −0,137 | 0,012 |
| SciBERT → SPECTER, entrada B | −0,170 | 0,016 |
| B → B_sin_seccion | −0,009 | 0,038 |
| B → B_barajada | +0,006 | 0,008 |
| Sondeo: B con eval barajado (sin reentrenar), SciBERT | +0,003 | 0,002 |
| Sondeo: idem, SPECTER | +0,002 | 0,002 |

### Interpretación breve (para el informe)
1. **Encoder:** SciBERT supera a SPECTER por 0,14 a 0,17 de F1 macro, con ambas entradas. Es la única diferencia mayor que la dispersión entre semillas. Con la misma cabeza y los mismos hiperparámetros, la ventaja es de SciBERT; no se ajustó nada por encoder, así que no se puede atribuir toda la brecha al encoder.
2. **Entrada A vs B:** no hay diferencia detectable. En SciBERT, +0,005 queda muy por debajo de la desviación (~0,03); en SPECTER la entrada B es peor, pero con dispersión alta (0,044). Con estos datos, añadir los Top-3 y la sección no mejora al título/abstract.
3. **Sección:** ni quitarla, ni barajarla en entrenamiento, ni barajarla solo en eval cambia el F1 más que el ruido. **No hay evidencia de que `perfil_seccion` aporte señal**, pero el diseño (3 semillas, 732 casos, heurística sin validar) **tampoco tiene potencia para descartar un efecto pequeño**: no se debe leer como «la sección no importa».
4. **Por clase:** el rendimiento se concentra en las clases frecuentes (Background y Application, F1 ≈ 0,74 a 0,77 en SciBERT) y en Further Reading. Gap, Basis, Improvement / Modification e Identification of the Originator quedan en F1 ≈ 0,19 a 0,27, con soporte de 7 a 42 casos y desviaciones entre semillas de hasta 0,12.
5. **Citado visto en train:** solo 87 de los 732 casos (11,9 %) citan un artículo presente en el train; en ese estrato el F1 macro es menor en las cuatro celdas (p. ej. SciBERT-B 0,343 frente a 0,472), pero con 87 casos y 9 clases es ruidoso y no permite concluir nada sobre memorización.

## 6. Hallazgos técnicos
- **Los vocabularios de SciBERT y SPECTER difieren** (31.090 frente a 31.116 tokens; SHA de `vocab.txt` distinto). El plan suponía el mismo scivocab. No invalida la comparación (el hash de la especificación de entrada es independiente del tokenizer y es idéntico entre encoders), pero los ids y el truncamiento pueden diferir algo entre ambos.
- **SPECTER** carga desde `pytorch_model.bin` (no hay `model.safetensors`), verificado contra `manifiesto_modelo_specter.json`.
- **Épocas:** 17 de las 18 corridas ejecutaron las 6 épocas permitidas y solo `scibert_A_42` paró antes (mejor época 3). En 14 de las 18 corridas la mejor época fue la 5 o la 6, así que el tope de 6 épocas podría estar limitando el entrenamiento; no se exploró.
- **Truncamiento (B, eval):** entre el 36 y el 40 % de los casos pierden tokens en cada chunk (media de 21 a 28 tokens recortados); el contexto no se trunca nunca y la longitud media es 477 tokens frente a 237 en A. B pierde parte del texto de los chunks que debía aportar.

## 7. Amenazas a la validez
- **Etiquetas Haiku** en train y eval: se mide el acuerdo con Haiku, no la función real de la cita. Un sesgo sistemático de Haiku se hereda y se mide como acierto.
- **Gold no congelado:** las predicciones sobre el Gold v2 (839 IDs) se generaron a ciegas y se podrán puntuar con `cli evaluar --gold-v2 <ruta privada>` sin reentrenar, cuando #100 lo congele.
- **Cobertura y selección:** la intersección conserva ~54 % y excluye artículos con párrafos largos; puede sesgar clases y tipo de artículo.
- **Tamaño y semillas:** 732 casos, 3 semillas, sin intervalos bootstrap ni prueba de significación; clases con 7 a 31 casos.
- **Desbalance:** Background y Application suman el 56 % del eval; el F1 macro castiga a las clases raras, cuyo F1 es inestable.
- **Hiperparámetros compartidos**, no ajustados por encoder (SPECTER pudo quedar penalizado).
- **`perfil_seccion`** es heurística (~50 % de los chunks caen en «otra»); las ablaciones miden esa heurística, no la sección retórica real.
- **Eval 2015** es un subconjunto de `TEST_GOLD_2700` y no el Gold v2 de 1.533 IDs; la comparación pareada por `example_id` es válida dentro de él.
- **Fuente de etiquetas Jurado:** no ejecutada (DVC sin descargar). Las celdas Haiku vs Jurado quedan **declaradas como no ejecutadas**.

## 8. Reproducción
```bash
bash scripts/preparar_clasificacion_a4.sh                     # conjuntos, OCL, Top-3, entradas
bash scripts/entrenar_clasificacion_a4.sh                     # matriz 2×2 (12 corridas) + sondeo
ENTRADAS="" ENCODERS=scibert ABLACIONES=1 bash scripts/entrenar_clasificacion_a4.sh   # ablaciones
PYTHONPATH=. uv run --project packages/clasificacion-funcion python -m clasificacion_funcion.cli evaluar
```
`evaluar` nunca sobrescribe: para regenerar `comparacion.*` o `a4_config_semilla*.json` hay que borrarlos antes.

## 9. Pendientes
- Registrar el bloqueo de cobertura en #103 y abrir el issue del fragmentador.
- Coordinar con John: `inspect_gold` (rama del benchmark) rechaza nombres que contengan «provisional»; no se esquiva renombrando archivos.
- Puntuar el Gold v2 cuando #100 lo congele; ejecutar la fuente Jurado cuando haya datos.
- Valorar más de 6 épocas y bootstrap pareado por documento.
