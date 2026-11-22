INFORME DE EJECUCIÓN Y AVANCES DEL PROYECTO DE GRADO

Recomendación local de citas y clasificación de funciones en artículos científicos con modelos de lenguaje

Autores: Carlos Eduardo Duque Lugo, John Byron Arias Sanz, Gabriel Gustavo Pinzón Páez, José María Zambrana Arze, Carlos Alfredo Caicedo Bermúdez

Afiliación: Maestría en Inteligencia Artificial, Universidad de los Andes, Bogotá, Colombia.

Correos: c.duquel@uniandes.edu.co · jb.arias@uniandes.edu.co · gg.pinzon@uniandes.edu.co · j.zambrana@uniandes.edu.co · c.caicedob@uniandes.edu.co

CORTE TÉCNICO: 16 de noviembre de 2026 (hora Colombia). GitHub main fd335b0893f664308cedb6bc81ea19ea421b2a91 y evidencias locales del 15–16 de noviembre documentadas en issue #186. Documento de trabajo, sin Gold humano certificado. Autoría propuesta pendiente de ratificación institucional.
# Resumen ejecutivo
El proyecto integra la recuperación Top-3 de fragmentos del citado y la clasificación de nueve funciones retóricas sobre ACL-200/ACL OCL. El repositorio conserva la auditoría del jurado QLoRA/Qwen/Llama (18.000 contextos) y 18 ejecuciones A4 provisionales (12 factoriales SciBERT/SPECTER × A/B × tres semillas y 6 ablaciones). Además, se RECUPERÓ y reprodujo localmente el clasificador histórico SciBERT-A/Jurado: checkpoint-945, 2.518 ejemplos train y 630 val, hashes verificados e inferencia CUDA equivalente al registro original (F1 macro = 0,5709355717, accuracy = 0,7634920635). En la matriz A4, los F1 macro medios sobre 732 pseudoetiquetas Haiku son 0,4669, 0,4723, 0,3298 y 0,3024. Las dos validaciones usan datos/protocolos diferentes. Los cinco archivos de data/raw se restauraron con integridad y se verificaron las 2.700 pseudoetiquetas Haiku; no se recuperó aún el split histórico qlora_split_v2.json ni los cuatro checkpoints A4. La API FastAPI/React dispone de rutas científicas opcionales, pero su inferencia requiere pesos válidos. No se dispone de Gold humano adjudicado ni de Gold de relevancia de chunks; ninguna métrica se presenta como resultado Gold.
# 1. Propósito, alcance y respuesta a la evaluación previa
Problema central: comprender por qué se cita una publicación exige clasificar la función retórica del contexto [1]–[3] y, como posible entrada complementaria, localizar evidencia puntual del artículo citado. El alcance de grado se centra en las nueve funciones; el microproyecto precedente abordaba recuperación local como objetivo independiente. La propuesta original contempló arXiv (PDF/LaTeX), pero la implementación utilizó ACL-200 con sus splits oficiales y ACL OCL [6] para texto citado estructurado. Este cambio metodológico facilita el control de citas y documentos, pero debe ratificarse frente a la propuesta aprobada.

| **Crítica del docente (informe de avance)** | **Respuesta incorporada al documento actual** |
| --- | --- |
| Propuesta poco alineada y excesiva atención a recuperación | Se ubica el jurado LLM, la taxonomía y el clasificador como eje; la recuperación es entrada complementaria. |
| Falta precisión sobre datos y 12 contextos | Se desglosan ACL-200, ACL OCL, splits, muestras piloto y reserva Gold; los 12 casos se reconocen como factibilidad, no test. |
| Sistema de votación con un solo LLM | Se describe el jurado abierto QLoRA/Qwen/Llama y el consenso 2/3; se distinguen otros experimentos con Qwen. |
| Conclusiones solo con 67 contextos | Se reproduce SciBERT-A/Jurado con 2.518/630 y checkpoint-945; los 67 casos quedan como piloto exploratorio. |
| Ausencia de declaración de IA y trazabilidad | Se añade declaración de herramientas/uso y se exigen hashes, entorno, código, checkpoints y límites de reproducibilidad. |
# 2. Objetivos y entregables de investigación
Objetivos de la propuesta: (i) recuperar fragmentos Top-3 con modelos densos; (ii) construir un dataset de nueve clases, objetivo ≥2.000 ejemplos por clase y ≥15 % revisado por humanos; (iii) ajustar clasificadores supervisados; (iv) comparar modelos comerciales y prompting; y (v) demostrar el flujo integrado. La meta de datos balanceados, la adjudicación humana y el benchmark definitivo NO están cumplidos. La implementación ha sustituido la fuente primaria arXiv prevista por ACL-200/ACL OCL; no debe describirse como extracción arXiv terminada.
# 3. Datos, procesamiento y control de calidad
## 3.1. Fuentes y particiones


| Fuente | Volumen verificado | Uso / límite |
| --- | --- | --- |
| ACL-200 contexts.json | 63.768 contextos | masked_text, citing_id, refid; incluye marcas de cita |
| ACL-200 papers.json | 19.776 artículos | title y abstract; texto completo no garantizado por este archivo |
| Split ACL-200 train | 30.390 citas (2009–2013) | Entrenamiento oficial; se usó para construir el desarrollo |
| Split ACL-200 val | 9.381 (2014) | Split original; no confundir con el holdout interno de 630 |
| Split ACL-200 test | 9.585 (2015) | Origen reservado para anotación humana |
El informe anterior consignó un enlace exploratorio ACL OCL de 500 casos, 411 pares completos (82,2 %), sin equivalencia con la cobertura A4. La intersección elegible A/B de A4 comprende 1.241/2.245 train (55,28 %), 213/397 val (53,65 %), 732/1.363 eval_2015 provisional (53,71 %) y 839/1.533 Gold v2 ciego candidato (54,73 %). El umbral interno de aceptación es 60 %, por lo que permanece un bloqueo de cobertura. La regla de chunks V1, incluido el rechazo de párrafos de más de 300 palabras, genera selección no aleatoria; una V2 debe probarse como experimento nuevo y no mezclarse con los resultados versionados.
## 3.2. Jurado automático y selección conservadora
Se auditaron 18.000 registros únicos procedentes de un jurado de tres modelos de pesos abiertos: una variante ajustada con QLoRA, Qwen y Llama. La regla preliminar exigió acuerdo de al menos dos de tres predicciones y pertenencia a una de las nueve funciones. Se identificaron 14.576 casos de acuerdo (14.525 dentro de las nueve clases y 51 ambiguos/no evaluables), y 3.424 sin consenso. Esta decisión crea pseudoetiquetas, no juicios humanos.

El documento histórico describe 6.509 candidatos y una selección de 3.148 contextos tras retirar 3.361 solapamientos por artículo citante (2.518 train, 630 val). Esta corrida SciBERT-A/Jurado fue RECUPERADA en una estación local: archivos de train/val y checkpoint-945 con SHA-256, tokenizador y script v3; se reejecutó inferencia sobre los 630 ejemplos y se reprodujeron sin diferencia las métricas de trainer_state.json. El código de esa corrida no está versionado dentro de main, de modo que su evidencia procede de archivos locales y del registro issue #186. No sustituye la matriz A4/Haiku: 2.245/397 evaluables y 1.241/213 para comparación A/B.

| Clase | Train | Desarrollo val |
| --- | --- | --- |
| Background | 878 | 214 |
| Application | 593 | 149 |
| Evidence | 325 | 79 |
| Comparison | 278 | 67 |
| Improvement / Modification | 203 | 53 |
| Gap | 155 | 44 |
| Basis | 51 | 15 |
| Further Reading | 30 | 8 |
| Identification of the Originator | 5 | 1 |
| TOTAL | 2518 | 630 |
## 3.3. Reserva Test Gold y anotación humana
El manifiesto PR #91 identifica 1.533 contextos de test 2015 (tandas de 519, 441 y 573), con doble asignación planificada, pero sin prueba de dos decisiones humanas efectivas por caso. La documentación registra, además, 20 contextos separados de calibración de 2014: 1.533 + 20 = 1.553. La cifra 1.553 podría referirse al conjunto combinado y NO implica automáticamente 20 IDs de test extraviados; su comunicación original debe cotejarse. Otro candidato PR #92 contiene 2.700 registros de validación/test y la conciliación histórica identifica 832 IDs comunes, 701 exclusivos de PR #91 y 547 exclusivos de PR #92. Ninguna lista ha sido aprobada como Gold canónico final.

Se mantienen pendientes: acta de Gold canónico, evidencia de dos juicios humanos independientes por ejemplo, acuerdo interanotador, adjudicación, exclusiones y congelación final. Las sugerencias generadas por IA no son evaluación humana. Además, eval_2015 provisional y Gold v2 se solapan (826/1.363 candidatos; 442/732 elegibles), por lo cual cualquier decisión de hiperparámetros basada en eval_2015 comprometería la independencia de una futura puntuación Gold sobre los casos compartidos. La lista de cinco autores y su participación deben corroborarse frente a la política institucional de grupos de cuatro.
## 3.4. Restauración de datos y reconstrucción parcial del split A4
En el repositorio actualizado se restauró data/raw desde un segundo directorio local: cinco archivos copiados y comprobados mediante SHA-256 origen–destino. contexts.json (4725714f53cd6e1f2efca883761dc252ac19be1489b699f4d14d1e7b9dcc3a73) y papers.json (999d6b77fed44d6bb6ed1c49c532c02aaa19f21b9e6d65e569201c2a2c7ee749) coinciden además con el manifiesto de recuperación A4. Las 2.700 pseudoetiquetas Haiku de notebooks/qlora-training coinciden con su SHA histórico (523b48d59de716dc7dbf5abe6ad7586600cc6201a503e2af03d378c71e7041ee). De los 2.700, los archivos versionados ids_train.txt e ids_val.txt identifican 2.245 y 397 registros evaluables; quedan 58 abstenciones, de las cuales 33 se asignan por artículo citante y 25 permanecen ambiguas. Exigiendo conteos históricos por categoría y separación documental resultan 5.320 distribuciones compatibles. No apareció el qlora_split_v2.json original; la derivación reproducible y comprobación de hashes de los conjuntos evaluables siguen pendientes. No se utilizaron etiquetas Gold humanas en esta auditoría.
# 4. Métodos y arquitectura de la solución
Flujo científico: ACL-200 + ACL OCL [6] → índices y validación de splits/corpus → pseudoetiquetas Haiku o jurado → particiones aisladas → recuperador SciBERT base (comparado descriptivamente con BM25) → entradas A o B → clasificador SciBERT [4] o SPECTER [5] → métricas provisionales → futuro Gold humano. A emplea contexto TARGETCIT + título + abstract; B usa contexto + tres chunks y perfil heurístico de sección, sin sumar automáticamente el título/abstract. La evaluación de relevancia de chunks sigue sin Gold; las rutas experimentales del servidor requieren snapshots y pesos auténticos.
## 4.1. Clasificador SciBERT-A/Jurado: modelo local recuperado y validación reproducida
En el equipo local se recuperó el clasificador histórico SciBERT-A/Jurado (allenai/scibert_scivocab_uncased, BertForSequenceClassification, 9 clases) con tokenizer, model.safetensors de checkpoint-945, trainer_state.json, training_args.bin y scripts v1/v2/v3. La ejecución de inferencia con tokenización v3 en CUDA cubrió los 630 ejemplos originales de validación. Las huellas SHA-256 coinciden con la auditoría y las métricas reproducidas con el historial: F1 macro 0,5709355717095655 y accuracy 0,7634920634920634, diferencias 0,0. Se verificó ausencia de cruces internos por context_id, citante y par entre 2.518 train y 630 val; esto no demuestra aislamiento respecto a otros conjuntos. La receta declarada es 3 épocas, batch físico 2, acumulación 4, lr 2×10⁻⁵, semilla 42 y límite 512; el uso real de FP16 durante el entrenamiento original no se ha podido confirmar. No se reentrenó ni se consultó Gold humano.

El script local v3, que reproduce la entrada pareada [CLS] contexto [SEP] título + abstract [SEP], contabilizó 121 abstracts truncados en train (4,81 %) y 23 en val (3,65 %), preservando contexto y título. Los scripts previos concatenaban campos y tenían otro truncamiento; el historial por sí solo no demuestra qué script generó el checkpoint, aunque la reproducción de las métricas con v3 respalda fuertemente esa correspondencia. Esta arquitectura y esos recortes no deben atribuirse a la matriz A4/Haiku.
## 4.2. Recuperación Top-3 y demostrador
La recuperación SciBERT vs BM25 fue ejecutada sobre 603 contextos de train y 89 artículos citados; el informe de A1 registra integridad sin violaciones, comparaciones de solape y latencia, pero NO Recall@3/MRR@3 con Gold humano de chunks. La prueba Qwen C1/C2 de 67 contextos mantiene valor exploratorio histórico (55 acuerdos, 12 diferencias) y no permite determinar mejora en precisión. Los PR #180, #182 y #183 integraron rutas opcionales SciBERT/SPECTER, controles SHA, exportación ciega, FastAPI, React y verificaciones CI; su existencia no prueba que cuatro clasificadores estén activos sin checkpoints. Se documentó una API baseline en AWS el 8 de noviembre, pero la disponibilidad actual del sitio y una demostración científica 2×2 aún requieren validación externa.
## 4.3. Experimento A4 factorial, posterior y diferente de SciBERT-A histórico
El repositorio conserva 18 entrenamientos A4: 12 factoriales SciBERT/SPECTER × A/B × semillas 42, 1234 y 2026, y 6 ablaciones SciBERT. Las entradas A/B utilizan exactamente 1.241 ejemplos de train y 213 de val elegibles; las predicciones se evaluaron contra 732 casos 2015 pseudoetiquetados por Haiku. La receta A4 es batch 8, acumulación 2, máximo 6 épocas, bfloat16 en CUDA y selección por F1 macro de val, originalmente en RTX 4070 SUPER. Los cuatro pesos semilla 42 esperados por SHA no se han recuperado del entorno inspeccionado: los manifiestos y predicciones versionados no prueban disponibilidad actual del servicio 2×2. La fragmentación V1 reduce la cobertura y es una amenaza científica.
# 5. Resultados reproducidos localmente y evidencia A4 versionada


| Época | F1 macro de desarrollo | Exactitud | Pérdida de validación |
| --- | --- | --- | --- |
| 1 | 0,4373 | 0,7048 | 0,8660 |
| 2 | 0,5314 | 0,7508 | 0,7236 |
| 3 | 0,5709 | 0,7635 | 0,7223 |
Los tres valores de época corresponden a evaluaciones de desarrollo sobre 630 pseudoetiquetas, NO a Gold humano. El 15-nov-2026 se reejecutó inferencia en CUDA usando checkpoint-945, tokenización v3 y los archivos originales; se obtuvo F1 macro = 0,5709355717095655 y accuracy = 0,7634920634920634, idénticos a trainer_state.json. Los archivos train/val/checkpoint tienen SHA-256 cotejado; se respaldaron 39 archivos privados. El tiempo histórico informado (661,8 s) no se midió nuevamente y el entrenamiento no fue repetido. La reproducción está documentada en issue #186, aunque falta versionar un script independiente de reproducción que no publique datos ni pesos.

El diagnóstico histórico comunica 431/630 ejemplos de validación con citado visto y 199/630 con citado no visto; esta separación queda como cifra histórica por contrastar con el CSV que la generó, no como conclusión replicada. En cambio, la auditoría local sí verificó el F1 por función de los 630 casos: Background 0,84 (214), Application 0,88 (149), Basis 0,12 (15) e Identification of the Originator 0,00 (1). El resultado confirma rendimiento heterogéneo, con categorías escasas y considerable desbalance.
## 5.1. Matriz A4 — métricas provisionales verificadas en GitHub
Fuente: proyecto_de_grado/docs/evidencias_clasificacion_a4/comparacion.json y metricas_eval.json por corrida. Misma evaluación Haiku 2015 (n = 732), media y desviación muestral de tres semillas; no Gold humano.

| **Encoder y entrada** | **F1 macro (media ± DE)** | **Accuracy (media)** | **N / origen** |
| --- | --- | --- | --- |
| SciBERT-A | 0,4669 ± 0,0331 | 0,6097 | 732 · Haiku |
| SciBERT-B | 0,4723 ± 0,0287 | 0,6107 | 732 · Haiku |
| SPECTER-A | 0,3298 ± 0,0315 | 0,5392 | 732 · Haiku |
| SPECTER-B | 0,3024 ± 0,0441 | 0,5255 | 732 · Haiku |
Las medias A→B son +0,0054 F1 macro para SciBERT y −0,0274 para SPECTER, en la misma evaluación Haiku de 732 casos. B→B_sin_seccion = −0,0091 y B→B_barajada = +0,0064 en promedio SciBERT. Con tres semillas y cobertura de B de aproximadamente 54 %, estas diferencias no demuestran mejora causal por Top-3 o por sección. La documentación técnica menciona IC bootstrap pareados, pero su script de cómputo aún no está versionado; deben tratarse como análisis complementarios por reproducir. SPECTER usa tokenizer y vocabulario distintos de SciBERT y puede requerir optimización propia de hiperparámetros.
## 5.2. Recuperación de fragmentos y estado del demostrador
El experimento A1 recuperó fragmentos con SciBERT base mediante mean pooling y coseno, contrastado con BM25 en 603 contextos TRAIN pertenecientes a 89 artículos. El Top-1 coincide entre ambos métodos en 19,07 % de esos contextos (métrica descriptiva micro). Sin juicios de relevancia por chunk no existe evaluación válida de Hit@3, Recall@3 o MRR@3. La API y React ya están en main y los endpoints científicos son opt-in, con 503 si faltan pesos. Los cuatro checkpoints históricos A4 no están en Git; por tanto el flujo científico 2×2 no está demostrado en el despliegue actual.
## 5.3. Reproducción por clase y límites estadísticos de A4
La reejecución de SciBERT-A/Jurado sobre 630 ejemplos logró F1 macro 0,5709355717, con F1 por clase: Background 0,84 (soporte 214), Gap 0,67 (44), Basis 0,12 (15), Comparison 0,68 (67), Application 0,88 (149), Improvement / Modification 0,65 (53), Evidence 0,59 (79), Identification of the Originator 0,00 (1) y Further Reading 0,71 (8). A4 ofrece por separado métricas reproducibles archivadas en comparacion.json, pero sin checkpoints originales para repetir inferencia en esta estación. Las ablaciones de sección no ofrecen evidencia sólida de aumento de F1; la diferencia de encoders está confundida por configuración y selección de épocas. Un bootstrap documentado con script externo aún no debe reportarse como evidencia completamente reproducible.
# 6. Discusión crítica y amenazas a la validez
La diferencia entre accuracy = 76,35 % y F1 macro = 57,09 % en el experimento SciBERT-A/Jurado ya reproducido muestra el efecto del desbalance y las clases poco frecuentes: F1 de Application 0,88 y Background 0,84 frente a Basis 0,12 e Identification of the Originator 0,00. El control de fugas local cubre el train/val 2.518/630, no todos los corpus externos. En A4, el manifiesto reporta 0 solapamientos train/val/eval por contexto, citante, par y hash de texto; pero eval_2015 y Gold v2 sí comparten IDs y no son benchmarks independientes. El desempeño A4 es provisional contra Haiku.

Las etiquetas Basis/Evidence requieren criterios más estables; los jueces automáticos pueden propagar errores sistemáticos. SciBERT supera a SPECTER bajo esta receta, no necesariamente como encoder general. La diferencia media SciBERT A→B (+0,0054) es menor que la variabilidad esperable de la evaluación, mientras SPECTER A→B (−0,0274) podría reflejar tokenización, poca adaptación o truncamiento, además de diferencias de contenido. Los 732 casos pertenecen a una intersección no aleatoria de disponibilidad de chunks; no es legítimo extrapolar a toda la población ACL-200 ni afirmar eficacia frente a Gold humano.
# 7. Entrega pendiente y plan para cierre


| **Dependencia** | **Acción mínima verificable** | **Estado** |
| --- | --- | --- |
| Gold humano | Confirmar 20 IDs; completar doble anotación; calcular kappa; adjudicar; congelar test | Pendiente |
| Clasificación | A4: recuperar pesos originales o entrenar nuevas corridas y archivar SHA; Jurado: conservar reproducción local de 630 casos. | Jurado reproducido; A4 provisional, sin pesos |
| Entrada B / Top-3 | A/B ya comparadas sobre 732 casos Haiku; corregir cobertura ~54 %, validar Gold chunks y repetir si cambia fragmentación. | Comparación provisional |
| Proveedores comerciales | Congelar modelos, prompts, costos y métricas sobre Gold | Pendiente |
| Despliegue | API baseline AWS histórica 08/11; React/FastAPI y contratos A4 en main; verificar URL actual y cuatro modelos reales. | Parcial; servicio por verificar |
| Artículo científico | Conciliar con reproducción local; actualizar bibliografía, metodología ACL-200/ACL OCL y límites Gold. | Corregido como borrador; Gold pendiente |
| Split A4 y datos | Corpus restaurado y Haiku verificados. Construir split derivado con 2.642 IDs evaluables y documentar 25 abstenciones ambiguas. | Corpus íntegro; split original ausente |
# 8. Conclusiones al corte
El proyecto dispone de una base reproducible: corpus ACL-200 restaurado con hashes, auditoría del jurado automático de 18.000 contextos, recuperación Top-3 SciBERT/BM25, matrices y predicciones A4/Haiku versionadas y una validación SciBERT-A/Jurado reejecutada exactamente sobre 630 casos. Sus métricas locales (F1 macro 0,5709355717; accuracy 0,7634920635) son provisionalmente válidas solo frente a pseudoetiquetas. Los cuatro pesos originales A4 y el split qlora_split_v2.json no se han recuperado; la auditoría recuperó los IDs evaluables y detectó 5.320 asignaciones posibles para 25 abstenciones. La clasificación Gold, el Gold de relevancia de chunks, la meta por clase, la revisión humana del 15 %, el benchmark final y la ejecución completa del demostrador permanecen pendientes. Se debe conservar la procedencia histórica y no atribuir nuevas corridas a checkpoints desaparecidos.
# 9. Declaración de uso de IA generativa
Se utilizaron modelos abiertos para pseudoetiquetar y asistentes generativos para revisar código, apoyar depuración, preparar documentos y proponer anotaciones. Las propuestas de IA no son evaluaciones humanas; la adjudicación y el acuerdo entre humanos siguen pendientes de evidencia privada comprobable. Los documentos deben identificar commit, datasets, fuentes de pseudoetiquetas, hashes y limitaciones por experimento. Los cinco nombres de autor pertenecen a una lista histórica propuesta y requieren conformidad de contribuciones y aprobación del programa (cuya guía menciona grupos de cuatro).
# Referencias
[1] S. Teufel, A. Siddharthan y D. Tidhar, «Automatic classification of citation function», en Proc. EMNLP, pp. 103–110, 2006. https://aclanthology.org/W06-1613/

[2] D. Jurgens, S. Kumar, R. Hoover, D. McFarland y D. Jurafsky, «Measuring the Evolution of a Scientific Field through Citation Frames», Transactions of the Association for Computational Linguistics, vol. 6, pp. 391–406, 2018. doi: 10.1162/tacl_a_00028.

[3] A. Cohan, W. Ammar, M. van Zuylen y F. Cady, «Structural Scaffolds for Citation Intent Classification in Scientific Publications», en Proc. NAACL-HLT, pp. 3586–3596, 2019. doi: 10.18653/v1/N19-1361.

[4] I. Beltagy, K. Lo y A. Cohan, «SciBERT: A Pretrained Language Model for Scientific Text», en Proc. EMNLP-IJCNLP, pp. 3615–3620, 2019. doi: 10.18653/v1/D19-1371.

[5] A. Cohan, S. Feldman, I. Beltagy, D. Downey y D. S. Weld, «SPECTER: Document-level Representation Learning using Citation-informed Transformers», en Proc. ACL, pp. 2270–2282, 2020. doi: 10.18653/v1/2020.acl-main.207.

[6] S. Rohatgi, Y. Qin, B. Aw, N. Unnithan y M.-Y. Kan, «The ACL OCL Corpus: Advancing Open Science in Computational Linguistics», en Proc. EMNLP, pp. 10348–10361, 2023. doi: 10.18653/v1/2023.emnlp-main.640.

[7] Grupo 19, «microproyecto-local-citation: código y evidencias del proyecto de grado», repositorio GitHub, commit fd335b0893f664308cedb6bc81ea19ea421b2a91, corte 16-nov-2026. [En línea]. Disponible: https://github.com/Byron971/microproyecto-local-citation.
## Trazabilidad de este corte frente al código (referencias internas)
• GitHub main auditado: fd335b0893f664308cedb6bc81ea19ea421b2a91 (PR #182, #183 y #191 integrados; #192 abierto al corte). Estado de GitHub no certifica datos locales ni checkpoints.

• A4: proyecto_de_grado/docs/clasificacion_funcion_a4.md; evidencias_clasificacion_a4/comparacion.json; manifiesto_entradas.json.

• Split A4 y recuperación: proyecto_de_grado/docs/evidencias_clasificacion_a4/{manifiesto_preparacion.json,ids_train.txt,ids_val.txt,fugas.json}; corpus data/raw restaurado en la estación (5 archivos SHA verificados); 2.700 pseudoetiquetas versionadas en notebooks/qlora-training.

• A1: proyecto_de_grado/docs/evidencias_recuperacion_densa_a1/resumen.json; recuperacion_densa_scibert_a1.md.

• Gold: docs/acta_decision_test_gold_canonico_issue_100.md; proyecto_de_grado/docs/dataset_funciones_v1.md.

• Runtime: src/app/main.py; src/app/classifier_runtime.py; src/evaluation/a4_export_unlabeled.py; a4_infer_unlabeled.py.

• Disponibilidad: docs/registro_checkpoints_a4.md; docs/evidencias/despliegue_116/README.md.

• Reproducción SciBERT-A/Jurado (registro privado): artifacts/entrada_a_jurado_scibert/{entrada_a_train,entrada_a_val}.jsonl y artifacts/experimento_scibert_a_jurado_provisional_v1/checkpoints/checkpoint-945; SHA train 430e6834856a17fe186f7d5ebd23524b26ffb5c776d137a5f8df35864257d915; val 3a1a971d3f672b007017c87c076365f6749aed51ca2207d45466b6a3fb2f98dc; peso 5f3193f8e3a97afd2304e261b08f45a56194edc19887fd3daa74d235e8b3f6e8; registro https://github.com/Byron971/microproyecto-local-citation/issues/186.
# Anexo. Evidencias adicionales pendientes y fuentes de reproducción
Ya recuperado localmente, SIN publicación de datos o pesos: checkpoint-945, script v3, train/val 2.518/630, hashes SHA-256, 39 archivos respaldados y métricas reproducidas (issue #186). Aún por incorporar: protocolo y comando de reproducción públicamente versionable sin datos privados; split A4 derivado expresamente marcado (nunca presentar su SHA como el v2 histórico); pesos A4 genuinos o nuevas corridas con procedencia; acta Gold humano adjudicado; control de independencia del eval 2015; Gold de relevancia Top-3; análisis de cobertura B; benchmark final y prueba vigente de servicio HTTPS. Las referencias bibliográficas externas se verificaron frente a ACL Anthology; faltan ratificación de autores y aprobación institucional.
