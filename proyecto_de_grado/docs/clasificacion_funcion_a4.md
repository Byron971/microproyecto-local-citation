# Clasificación de la función de la cita: SciBERT/SPECTER × Entrada A/B (A4, issue #103)

> **Estado: PROVISIONAL.** Entrenamiento y evaluación usan etiquetas de **Haiku**; el Gold humano v2 **no está congelado** (#100). Ninguna cifra de este documento es un resultado final ni debe llamarse «Gold humano».
>
> **¿A4 cumplida? No.** La matriz 2×2 y las ablaciones de sección están *ejecutadas* en modo provisional, pero A4 no se da por cumplida hasta que: (1) el Gold v2 esté congelado (#100) y se puntúen sobre él las predicciones ciegas; (2) el bloqueo de cobertura (§4) se resuelva o el equipo lo acepte; (3) se revisen los hiperparámetros por encoder (§6) y (4) se ejecute, o se declare definitivamente fuera de alcance, la fuente de etiquetas Jurado.

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

A y B usan **exactamente los mismos IDs** (intersección controlada). `fugas.json` reporta 0 intersecciones por `context_id`, `citing_id`, par citante–citado y texto TARGETCIT entre train, val y eval (y, en su bloque `gold_v2`, entre train, val y Gold v2). El `cited_id` compartido solo se reporta (no bloquea), igual que en `validar_splits`: hay artículos citados presentes en varios conjuntos (119 entre train y eval completos; 63 artículos y 87 de los 732 casos tras la intersección; ver el estrato «visto en train» en la sección 5).

**Eval 2015 y Gold v2 no son independientes.** Ambos son test 2015 y se solapan **por construcción**: 826 de los 1.363 contextos del eval 2015 están en el Gold v2 (442 de los 732 casos de la intersección están entre los 839 del Gold v2). Las claves `eval_2015~gold_v2:*` del bloque `principal` de `fugas.json` salen en 0 solo porque `cargar_conjuntos` no pasa `gold_v2` a esa comprobación; no deben leerse como ausencia de solapamiento. No es una fuga hacia train, pero **cualquier decisión tomada mirando el eval 2015** (p. ej. ampliar épocas, §9) contaminaría la futura evaluación sobre el Gold v2.

**Abstenciones.** «Ambiguo» y «No evaluable» se cuentan aparte (`abstenciones.csv`) y nunca forman una décima clase.

## 3. Protocolo de entrenamiento (fijado antes de mirar el eval)
`max_len` 512; AdamW lr 2e-5, weight decay 0,01 (sin decay en bias/LayerNorm); warmup 10 % y decaimiento lineal; batch 8 × acumulación 2; máximo 6 épocas con parada temprana (paciencia 2) sobre F1 macro de val; bf16; clip 1,0; semillas 42, 1234 y 2026. Se conserva el checkpoint de la mejor época en val (`checkpoint_sha256` en cada manifiesto). Hardware: RTX 4070 SUPER; torch 2.11.0+cu128, transformers 5.22.2. Cada corrida de entrada B tarda ~160 s y cada A ~100 s.

## 4. Bloqueo de cobertura (a registrar en #103)
La Entrada B exige texto de chunks del citado, y la cobertura queda **bajo el umbral del 60 %** en todos los conjuntos:

| Conjunto | Cobertura | Excluidos por párrafo largo |
|---|---|---|
| train | 55,28 % | 991 |
| val | 53,65 % | (ver `excluidos.csv`) |
| eval 2015 | **53,71 %** | 629 |
| Gold v2 | 54,73 % | 693 |

La causa dominante es la regla de A1, que descarta los artículos con párrafos de más de 300 palabras. **No se modificó esa regla.** Queda por abrir un issue aparte para evaluar otro fragmentador. Consecuencias: la intersección **no es una muestra aleatoria** y no conserva las clases por igual (en eval, Identification of the Originator conserva 7 de 21 casos, 33 %, mientras otras clases conservan entre 49 y 67 %; la retención depende de la clase, χ²(8) = 16,0, p ≈ 0,04). En train no se detecta esa dependencia (p ≈ 0,57), pero sí cambia la composición: Evidence es el 6 % de train (74/1.241) y el 13 % de eval (97/732). Las conclusiones valen para la subpoblación de citados sin párrafos largos; **no se sabe cómo rinde A sobre los 1.363 casos completos**, porque A tampoco se entrenó ni evaluó fuera de la intersección (el protocolo §3 pedía no descartar la comparación sobre corpus completos).

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

La «Desv.» es la desviación **muestral** (ddof = 1) entre las 3 semillas del delta pareado. Esa desviación solo recoge la varianza de entrenamiento, **no** la de muestreo del conjunto de evaluación, así que no se usa como criterio de significación.

**Bootstrap pareado por casos** (1.000 réplicas sobre los 732 casos, media de las 3 semillas; IC95 %):

| Contraste | Delta F1 macro | IC95 % |
|---|---|---|
| A → B, SciBERT | +0,005 | [−0,021; +0,032] |
| A → B, SPECTER | −0,027 | [−0,057; +0,003] (p ≈ 0,08) |
| SciBERT → SPECTER, entrada A | −0,137 | [−0,177; −0,098] |
| SciBERT → SPECTER, entrada B | −0,170 | [−0,211; −0,127] |
| B → B_sin_seccion | −0,009 | [−0,028; +0,010] |
| B → B_barajada | +0,006 | [−0,007; +0,022] |

Estos intervalos se calcularon con un script externo a la revisión del PR (no versionado todavía); `comparacion.json` y el notebook solo traen deltas ± desviación entre semillas. Agrupando por documento citante (489 grupos) los intervalos apenas cambian.

### Interpretación breve (para el informe)
1. **Encoder:** SciBERT supera a SPECTER por 0,14 a 0,17 de F1 macro con ambas entradas, y el intervalo bootstrap excluye el 0 con holgura. Pero con la misma cabeza y los mismos hiperparámetros no se puede atribuir toda la brecha al encoder: SPECTER quedó menos entrenado (pérdida final 0,49–0,61 frente a 0,22–0,30; su mejor época fue la última en 3 de 6 corridas) y usa un vocabulario *cased* con texto en minúsculas (§6).
2. **Entrada A vs B:** no hay diferencia detectable en SciBERT (+0,005, IC95 % [−0,021; +0,032]). En SPECTER la entrada B es algo peor, pero el efecto está en el límite (IC95 % [−0,057; +0,003]). Con estos datos, añadir los Top-3 y la sección no mejora al título/abstract. Que el delta pareado sea positivo en las 3 semillas en SciBERT no cambia esta lectura: es un efecto de ~0,005 muy inferior al error de muestreo.
3. **Sección:** ni quitarla, ni barajarla en entrenamiento, ni barajarla solo en eval cambia el F1 más que el ruido. **No hay evidencia de que `perfil_seccion` aporte señal**, pero el diseño (3 semillas, 732 casos, heurística sin validar) **tampoco tiene potencia para descartar un efecto pequeño**: no se debe leer como «la sección no importa».
4. **Por clase:** el rendimiento se concentra en las clases frecuentes (Background y Application, F1 ≈ 0,73 a 0,77 en SciBERT) y en Further Reading. Gap, Basis, Improvement / Modification e Identification of the Originator quedan en F1 ≈ 0,15 a 0,27 en SciBERT, con soporte de 7 a 42 casos y desviaciones entre semillas de hasta 0,12.
5. **Citado visto en train:** solo 87 de los 732 casos (11,9 %) citan un artículo presente en la intersección de train; en ese estrato el F1 macro es menor en las cuatro celdas (p. ej. SciBERT-B 0,343 frente a 0,472) y la accuracy cae de ~0,65 a ~0,34. Es una caída mucho mayor que el error de muestreo esperable con n = 87, y las 9 clases tienen soporte, así que **no es un artefacto del F1 macro**. La composición de clases del estrato difiere (Evidence 24 %, Background 26 %), lo que apunta a un confusor de clase o de etiquetado. Es un **hallazgo a investigar**, no ruido ignorable; no autoriza conclusiones sobre memorización. («Visto» se define sobre la intersección de train; sobre los conjuntos completos son 119 citados compartidos.)
6. **Alcance de la comparación entre encoders:** estos datos muestran que, con esta receta compartida y etiquetas Haiku, SPECTER rinde menos que SciBERT; no demuestran que SPECTER sea peor encoder para la tarea.

## 6. Hallazgos técnicos
- **Los vocabularios de SciBERT y SPECTER difieren** (31.090 frente a 31.116 tokens; SHA de `vocab.txt` distinto). El plan suponía el mismo scivocab y pedía verificarlo; el código solo registra la huella. No invalida la comparación (el hash de la especificación de entrada es independiente del tokenizer y es idéntico entre encoders), pero los ids y el truncamiento difieren.
- **SPECTER: vocabulario *cased* con minúsculas.** Su `config.json`/`tokenizer_config.json` apuntan a `allenai/scibert_scivocab_cased` con `do_lower_case: true`, de modo que 6.881 de las 31.116 entradas (las que tienen mayúsculas) nunca se generan. En 300 casos de train produce ~2 % más tokens que SciBERT. Es la configuración oficial publicada, no un fallo del código, pero conviene tenerla presente al interpretar la brecha entre encoders (que influya en ella es una inferencia, no está medido).
- **Selección de época ruidosa.** Val tiene 213 casos, con Improvement / Modification = 2 y Further Reading = 4, y la mejor época se elige con `>` estricto sin delta mínimo (`scibert_A_42` se detuvo por una diferencia de 0,0002). No es una fuga, pero la elección del checkpoint es sensible al ruido.
- **SPECTER** carga desde `pytorch_model.bin` (no hay `model.safetensors`), verificado contra `manifiesto_modelo_specter.json`.
- **Épocas:** 17 de las 18 corridas ejecutaron las 6 épocas permitidas y solo `scibert_A_42` paró antes (mejor época 3). En 14 de las 18 corridas la mejor época fue la 5 o la 6, así que el tope de 6 épocas podría estar limitando el entrenamiento; no se exploró.
- **Truncamiento (B, eval):** en SciBERT entre el 36 y el 40 % de los casos pierden tokens en cada chunk (media de 21 a 28 tokens recortados) y la longitud media es 477 tokens frente a 237 en A; en SPECTER-B son 40–43 %, 24–31 tokens y 481 frente a 243. El contexto casi no se trunca (0,08 % en train, 2 tokens como máximo). B pierde parte del texto de los chunks que debía aportar.
- **Latencia:** el primer lote de cada corrida incluye el calentamiento (máximos de 16–19 ms frente a medianas de 2,5 ms en A y 5,0 ms en B); si se reporta latencia, usar la mediana.

## 7. Amenazas a la validez
- **Etiquetas Haiku** en train y eval: se mide el acuerdo con Haiku, no la función real de la cita. Un sesgo sistemático de Haiku se hereda y se mide como acierto.
- **Gold no congelado:** las predicciones sobre el Gold v2 (839 IDs) se generaron a ciegas y se podrán puntuar con `cli evaluar --gold-v2 <ruta privada>` sin reentrenar, cuando #100 lo congele.
- **Cobertura y selección:** la intersección conserva ~54 % y excluye artículos con párrafos largos; puede sesgar clases y tipo de artículo.
- **Tamaño y semillas:** 732 casos, 3 semillas; los IC bootstrap de §5 no forman parte de la evidencia versionada; clases con 7 a 42 casos.
- **Un único recuperador** (SciBERT base de A1, Top-3 sin validar su relevancia, protocolo §10.5): la entrada B está confundida con la calidad de recuperación y con el truncamiento de chunks. La regresión contra A1 solo comparó 42 de 603 contextos (`manifiesto_recuperacion.json`) y se omite en silencio si falta el archivo de referencia.
- **Val pequeño** (213 casos) para parada temprana y elección de checkpoint; **tope de 6 épocas** posiblemente limitante (§6).
- **Desbalance:** Background y Application suman el 56 % del eval; el F1 macro castiga a las clases raras, cuyo F1 es inestable.
- **Hiperparámetros compartidos**, no ajustados por encoder (SPECTER pudo quedar penalizado).
- **`perfil_seccion`** es heurística (35–42 % de los chunks caen en «otra» según los `top3_*.csv`; 37 % en eval); las ablaciones miden esa heurística, no la sección retórica real.
- **Eval 2015** es un subconjunto de `TEST_GOLD_2700` y no el Gold v2 de 1.533 IDs; la comparación pareada por `example_id` es válida dentro de él. Ambos se solapan (§2), así que no son evaluaciones independientes.
- **Procedencia git:** 17 de los 24 manifiestos de corrida/sondeo dicen `dirty: true` (generados antes del arreglo de `_git`, ver README del paquete). El código de entrenamiento no cambió entre esas corridas y HEAD, y una reproducción de `scibert_A_42` en HEAD dio el mismo `checkpoint_sha256` y el mismo historial, pero el criterio «HEAD limpio» no puede comprobarse a posteriori.
- **Etiquetas Haiku versionadas:** `excluidos.csv` incluye la columna `etiqueta` de casos de train, val y eval excluidos, y `gold_eval_2015_haiku.jsonl` las del eval. El plan pedía confirmar con el equipo antes de versionarlas; **pendiente de confirmar**.
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
- Versionar el script del bootstrap pareado (hoy los IC de §5 no son reproducibles desde el repo) e incorporarlo a `comparacion.*` y al notebook.
- Valorar más de 6 épocas **usando solo val**, no el eval 2015 (solapa con el Gold v2).
- Confirmar con el equipo el versionado de las etiquetas Haiku.
- Decidir si repetir una celda en HEAD limpio para cerrar la procedencia de los manifiestos `dirty: true`.
