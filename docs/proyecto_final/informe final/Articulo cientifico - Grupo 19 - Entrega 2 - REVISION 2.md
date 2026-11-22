Recomendación de fragmentos y clasificación de funciones de cita: evidencia provisional con SciBERT y SPECTER en ACL-200

Artículo científico · Versión corregida y contrastada con código y manifiestos · Evidencia provisional, sin Gold humano certificado

Autores: Carlos Eduardo Duque Lugo, John Byron Arias Sanz, Gabriel Gustavo Pinzón Páez, José María Zambrana Arze, Carlos Alfredo Caicedo Bermúdez

Afiliación: Maestría en Inteligencia Artificial, Universidad de los Andes, Bogotá, Colombia.

Correos: c.duquel@uniandes.edu.co · jb.arias@uniandes.edu.co · gg.pinzon@uniandes.edu.co · j.zambrana@uniandes.edu.co · c.caicedob@uniandes.edu.co

CORTE DE EVIDENCIA: 16 de noviembre de 2026 (hora Colombia). GitHub main fd335b0893f664308cedb6bc81ea19ea421b2a91; reproducción SciBERT-A/Jurado documentada mediante ejecución local del 15-nov y issue #186. Las autorías y contribuciones requieren validación institucional.
# Resumen
Este estudio integra dos tareas relacionadas en artículos científicos: recuperación local de hasta tres fragmentos del artículo citado y clasificación de su función discursiva en nueve categorías. Sobre ACL-200 y ACL OCL se distinguen dos líneas de evidencia no intercambiables. (i) Se recuperó el clasificador histórico SciBERT-A/Jurado, entrenado con pseudoetiquetas de un jurado automático: conjuntos de 2.518/630 (train/val) y checkpoint-945 identificados mediante SHA-256, sin intersecciones observadas por contexto, citante ni par citante–citado dentro de la partición; la inferencia local con tokenización v3 reprodujo exactamente F1 macro = 0,5709355717 y accuracy = 0,7634920635 en los 630 ejemplos de desarrollo. (ii) La matriz A4/Haiku registró 12 corridas SciBERT/SPECTER × entradas A/B × tres semillas y seis ablaciones; en 732 casos de evaluación provisional los F1 macro medios fueron 0,4669, 0,4723, 0,3298 y 0,3024 para SciBERT-A, SciBERT-B, SPECTER-A y SPECTER-B. La entrada B conserva una cobertura de 53,71 % en evaluación. El Gold humano de funciones y el Gold de relevancia de chunks no están certificados; los cuatro checkpoints históricos A4 siguen sin recuperarse. Los resultados muestran reproducibilidad de una validación pseudoetiquetada y un contraste experimental provisional, no desempeño final frente a juicios humanos.

Palabras clave: recuperación local de fragmentos; funciones de cita; SciBERT; SPECTER; pseudoetiquetado; ACL-200.
# 1. Introducción
Las citas académicas cumplen funciones retóricas distintas: contextualizar antecedentes, fundamentar métodos, comparar resultados o señalar vacíos. Su clasificación automática requiere distinguir el sentido discursivo de la simple coincidencia temática, especialmente ante fronteras ambiguas entre Basis y Evidence [1], [2].

El proyecto integra (i) recuperación local de tres fragmentos del artículo citado, mediante SciBERT y un baseline BM25, y (ii) clasificación retórica en nueve funciones usando SciBERT y SPECTER. En la matriz A4, la entrada A usa contexto, título y resumen; la entrada B usa contexto y tres fragmentos Top-3 con perfil heurístico de sección. De forma independiente se recuperó y reejecutó el clasificador histórico SciBERT-A/Jurado, cuya evaluación de desarrollo coincide exactamente con su registro original. Los cuatro clasificadores A4/Haiku mantienen evidencia de entrenamiento provisional versionada, pero sus pesos originales no han sido recuperados y no hay evaluación final sobre Gold humano.

Los objetivos técnicos al corte son consolidar corpus con procedencia; examinar el acuerdo de pseudoetiquetado, comparar SciBERT/SPECTER sobre entradas A/B y mantener separadas las dos fuentes de evaluación: Haiku provisional y Gold humano futuro. La pregunta científica final —si recuperar evidencia específica mejora de modo fiable la clasificación— sigue abierta, pese a que el sistema ya dispone de componentes de inferencia y demostración.
# 2. Estado del arte
La literatura diferencia la intención retórica de la relación temática. Teufel et al. [1] propusieron una clasificación funcional; Jurgens et al. [2] estudiaron marcos de citación y dinámica de comunidades; Cohan et al. [3] utilizaron señales estructurales para clasificar la intención de citas y presentaron SciCite. Estos antecedentes justifican definiciones operativas estables y controles de calidad sobre las etiquetas.

SciBERT [4] incorpora preentrenamiento sobre publicaciones científicas y sirve como encoder de clasificación y recuperación. SPECTER [5] utiliza señales de citas para aprender representaciones de documentos; en este proyecto se ajusta como clasificador sobre contextos, no se evalúa directamente como recuperador de chunks. ACL OCL [6] proporciona textos científicos y estructura seccional; la disponibilidad del artículo citado y la calidad de fragmentación condicionan la entrada B.

En contraste con trabajos que parten de etiquetas humanas ya consolidadas, este estudio examina un flujo de construcción de datos mediante acuerdo entre modelos de pesos abiertos, seguido de un protocolo de auditoría y evaluación humana. La hipótesis de trabajo es que esa separación puede facilitar el desarrollo a escala sin confundir pseudoetiquetas y referencia Gold. La contribución todavía debe verificarse sobre anotaciones humanas independientes y en una comparación pareada de entradas A y B.
# 3. Metodología
## 3.1. Diseño, fuentes y particiones
Se utiliza ACL-200 (63.768 contextos; 19.776 artículos; splits oficiales train = 30.390, val = 9.381 y test = 9.585) y ACL OCL como fuente de texto estructurado de artículos citados [6]. La propuesta original planteaba extracción desde arXiv (PDF/LaTeX); la implementación documentada migró a ACL-200/ACL OCL para disponer de identificadores de cita, particiones oficiales y enlaces citante–citado. Esta decisión es una adaptación metodológica del corpus, no el cumplimiento literal del objetivo de arXiv y debe ser ratificada académicamente. La corrida histórica SciBERT-A/Jurado tiene una partición de desarrollo propia de 2.518 train y 630 val, diferente de la matriz A4/Haiku; sus métricas no son comparables directamente.
## 3.2. Pseudoetiquetado mediante jurado abierto
El mecanismo de preetiquetado reunió predicciones de un clasificador ajustado con QLoRA, Qwen y Llama sobre 18.000 contextos únicos. Se exigió mayoría de al menos dos de tres votos, junto con pertenencia a las nueve clases válidas: Background, Gap, Basis, Comparison, Application, Improvement / Modification, Evidence, Identification of the Originator y Further Reading. Se identificaron 14.576 ejemplos con acuerdo de mayoría, de los cuales 14.525 recibieron una clase válida y 51 se consideraron ambiguos o no evaluables. Los restantes 3.424 no alcanzaron consenso. Las etiquetas resultantes se consideran pseudoetiquetas y no mediciones Gold.
## 3.3. Prevención de fugas y construcción del desarrollo
El proceso histórico documenta 6.509 candidatos; al retirar 3.361 cruces por citante quedaron 3.148 ejemplos (2.518 train, 630 val). El script local v3 auditó 0 intersecciones por context_id, citing_id y par citante–citado entre esos dos archivos. La procedencia declarada de las etiquetas es jurado_automatico_no_gold. Este control interno no prueba por sí solo aislamiento respecto a QLoRA, evaluaciones exploratorias o posibles conjuntos Gold. A4/Haiku tiene 2.245 train y 397 val evaluables, reducidos por la intersección A/B a 1.241 y 213, y un conjunto provisional de evaluación de 732 casos; no debe confundirse con el desarrollo Jurado.

| Función | Train | Val |
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
Tabla 1. Distribución de las nueve categorías en el conjunto de desarrollo (fuente: manifiestos de auditoría del proyecto).
## 3.4. Representación, modelo y entrenamiento
En A4, la entrada A usa contexto con TARGETCIT, título y abstract; la B usa contexto y tres fragmentos Top-3 con perfil heurístico de sección, sin añadir automáticamente título/abstract. Ambas se recortan a 512 tokens con reglas por segmento. La búsqueda de fragmentos emplea SciBERT base, mean pooling y coseno; la segmentación V1 descarta artículos con párrafos que superan el umbral de 300 palabras. La intersección A/B abarca 55,28 % del train y 53,71 % de la evaluación 2015, por debajo del umbral interno de 60 %, con posible sesgo de selección.

La corrida histórica SciBERT-A/Jurado utiliza el modelo base declarado allenai/scibert_scivocab_uncased y BertForSequenceClassification (9 clases). La tokenización reconstruida v3 es BERT por pares: [CLS] contexto [SEP] título + resumen [SEP], preservando contexto y título al truncar el abstract a un máximo global de 512 tokens. Se declararon 3 épocas, lr 2×10⁻⁵, batch físico 2, acumulación 4 y semilla 42; no está confirmado si FP16 estuvo activo en la ejecución original. Se midieron 121 abstracts truncados en train y 23 en val. En CUDA se cargó checkpoint-945 y se reejecutó inferencia de 630 ejemplos: F1 macro y exactitud coincidieron exactamente con trainer_state.json; no se repitió el entrenamiento. Por separado, los manifiestos A4 registran batch 8, acumulación 2, máximo 6 épocas, bfloat16 y semillas 42/1234/2026 sobre RTX 4070 SUPER. Sus pesos originales no están disponibles en el equipo auditado.
## 3.5. Reserva humana, recuperación y despliegue
El manifiesto candidato PR #91 reúne 1.533 IDs de test 2015 (tandas 519, 441 y 573) y 20 IDs de calibración 2014 separados. PR #92 aporta otro archivo histórico de 2.700 anotaciones sin evidencia suficiente de doble adjudicación humana, y la conciliación documenta 832 IDs comunes. La doble asignación planificada no equivale a dos anotaciones realizadas. No hay aprobación de un Gold humano canónico. Además, eval_2015 y Gold v2 se solapan por construcción: 826 de 1.363 casos candidatos, y 442 de los 732 de la intersección elegible se encuentran en el Gold candidato de 839. Consultar eval_2015 para modificar hiperparámetros contaminaría una futura evaluación Gold sobre esos mismos IDs; la selección de modelos debe utilizar exclusivamente validación.

El experimento A1 comparó Top-3 SciBERT contra BM25 sobre 603 contextos TRAIN y 89 artículos citados, sin Gold humano de relevancia por chunk. FastAPI y React en main soportan baseline, Top-3 y clasificadores SciBERT/SPECTER opt-in, condicionados a pesos y snapshots auténticos. La evidencia de AWS del 8 de noviembre demuestra un servicio baseline en esa fecha, no necesariamente un servicio activo hoy ni una ejecución de los cuatro clasificadores. La ejecución offline A4 2×2, la verificación ACL/OCL y el smoke científico están implementados, pero los cuatro pesos model.safetensors históricos no están versionados.
## 3.6. Matriz A4 de encoders, entradas y ablaciones
El repositorio conserva 12 corridas factoriales SciBERT/SPECTER × A/B con semillas 42, 1234 y 2026, más seis entrenamientos de ablación SciBERT (B sin perfil de sección o con secciones barajadas). Todas utilizan pseudoetiquetas Haiku, 1.241 train y 213 val de la intersección A/B y evaluación provisional en 732 ejemplos de 2015. Estos números describen experimentos ejecutados y versionados, no disponibilidad local de sus checkpoints históricos ni desempeño ante Gold humano.
## 3.7. Estado de restauración y trazabilidad de datos
La restauración local del 15–16 de noviembre no altera los resultados A4 históricos. El corpus ACL-200 (5 archivos) y la fuente de 2.700 pseudoetiquetas Haiku conservaron los SHA esperados; los IDs evaluables se reconstruyen con listas versionadas de 2.245 train y 397 val. De 58 abstenciones, 29 se adscriben a train y 4 a val por citante; 25 proceden de 25 citantes sin ejemplos evaluables asociados. Respetando las distribuciones históricas 44/6 (train) y 7/1 (val) para Ambiguo/No evaluable, hay 5.320 asignaciones compatibles; ninguna identifica por sí sola el split v2 original. El archivo derivado no estaba creado al corte y los experimentos A4 no han sido reentrenados tras la restauración.
# 4. Resultados


| Época | F1 macro (desarrollo) | Exactitud | Eval loss |
| --- | --- | --- | --- |
| 1 | 0,4373 | 0,7048 | 0,8660 |
| 2 | 0,5314 | 0,7508 | 0,7236 |
| 3 | 0,5709 | 0,7635 | 0,7223 |
Tabla 2. Historial recuperado del entrenamiento histórico SciBERT-A/Jurado sobre 630 pseudoetiquetas de validación. El checkpoint-945 y su tokenizador se recuperaron del equipo local; sus archivos, junto con ambos conjuntos JSONL, se verificaron mediante SHA-256. La inferencia reejecutada sobre los 630 casos usando tokenización v3 produjo F1 macro 0,5709355717095655 y accuracy 0,7634920634920634, exactamente iguales a los valores de trainer_state.json (diferencias 0,0). No se repitió el entrenamiento ni se utilizó Test Gold. El tiempo histórico de entrenamiento (661,8 s) no se volvió a medir.

El diagnóstico histórico comunica 431/630 ejemplos de val con artículo citado visto en train y 199/630 con artículo no visto; debe acompañarse del archivo fuente para confirmación. No debe combinarse con el análisis del subconjunto A4 de 732 casos, que presenta distinta elegibilidad y distribución de clases.

En 67 ejemplos exploratorios se comunicaron 55 coincidencias y 12 diferencias de salida Qwen con y sin Top-3; el acuerdo no estima precisión sin Gold. El experimento A1 independiente comparó SciBERT y BM25 en 603 contextos TRAIN y reportó coincidencia Top-1 de 19,07 % y solape Top-3 como medidas descriptivas, NO Recall@3 ni MRR@3.
## 4.1. Reproducción de la validación SciBERT-A/Jurado
La comprobación se efectuó sin entrenamiento ni acceso al Test Gold. Antes de ejecutar inferencia se validaron los SHA-256 de train, val y checkpoint-945. Se cargaron pesos model.safetensors y tokenizador locales, se aplicó tokenize_preserving_context del script v3 a los 630 ejemplos de val, y se calculó F1 macro (media no ponderada sobre nueve categorías, zero_division=0) y exactitud con scikit-learn. Ambas métricas coincidieron sin diferencia numérica con las consignadas en trainer_state.json. La ejecución local usó CUDA; los valores expresan acuerdo con pseudoetiquetas, no precisión frente a humanos.

Tabla 3. Evaluación por función de cita en la reproducción de SciBERT-A/Jurado (630 ejemplos de validación pseudoetiquetados). Valores redondeados a dos decimales. El soporte no corresponde a un Gold humano.

| **Función** | Precisión | Recall | F1 | Soporte |
| --- | --- | --- | --- | --- |
| Background | 0,79 | 0,89 | 0,84 | 214 |
| Gap | 0,65 | 0,68 | 0,67 | 44 |
| Basis | 0,50 | 0,07 | 0,12 | 15 |
| Comparison | 0,69 | 0,67 | 0,68 | 67 |
| Application | 0,86 | 0,90 | 0,88 | 149 |
| Improvement / Modification | 0,67 | 0,64 | 0,65 | 53 |
| Evidence | 0,66 | 0,53 | 0,59 | 79 |
| Identification of the Originator | 0,00 | 0,00 | 0,00 | 1 |
| Further Reading | 0,83 | 0,62 | 0,71 | 8 |
La clase Identification of the Originator presenta soporte uno y F1 = 0; Basis presenta F1 = 0,12 (soporte 15). Por ello, una exactitud de 0,7635 no debe interpretarse como rendimiento homogéneo. El check de fugas contempla únicamente las dos particiones locales, no una auditoría cruzada con corpus externos de Gold o QLoRA.
## 4.2. Comparación factorial A4 versionada (no Gold humano)
Tabla 4. Media y desviación muestral entre tres semillas sobre los mismos 732 casos de evaluación 2015, etiquetados provisionalmente por Haiku. Fuente: proyecto_de_grado/docs/evidencias_clasificacion_a4/comparacion.json (versionado en main).

| **Condición** | **F1 macro (media ± DE)** | **Accuracy media** | **Referencia** |
| --- | --- | --- | --- |
| SciBERT-A | 0,4669 ± 0,0331 | 0,6097 | Haiku, n = 732 |
| SciBERT-B | 0,4723 ± 0,0287 | 0,6107 | Haiku, n = 732 |
| SPECTER-A | 0,3298 ± 0,0315 | 0,5392 | Haiku, n = 732 |
| SPECTER-B | 0,3024 ± 0,0441 | 0,5255 | Haiku, n = 732 |
El efecto medio A→B fue +0,0054 puntos de F1 macro para SciBERT y −0,0274 para SPECTER. La desviación entre tres semillas expresa variabilidad entre entrenamientos, no incertidumbre muestral ni significación estadística. El documento técnico A4 comunica intervalos bootstrap pareados, pero el script externo con que se calcularon aún no está versionado: por tanto estos intervalos deben considerarse análisis complementario pendiente de reproducción y no prueba concluyente de superioridad. Tampoco existe Gold independiente de relevancia que permita atribuir a Top-3 una mejora semántica.
## 4.3. Ablaciones de sección y límites interpretativos
En el conjunto Haiku A4 (n = 732) las ablaciones SciBERT registraron delta medio de F1 macro B→B_sin_seccion = −0,0091 y B→B_barajada = +0,0064, con desviaciones entre semillas de 0,0381 y 0,0076. La evidencia no muestra una mejora robusta por el perfil heurístico de sección. El análisis de sensibilidad por citado visto en entrenamiento documenta 87/732 casos en el estrato visto de la intersección y cambios de composición por clase; estos resultados son exploratorios y no demuestran memorización.
## 4.4. Integridad y alcance del respaldo local
El 15 de noviembre de 2026 se copiaron y comprobaron 39 archivos del experimento SciBERT-A/Jurado, incluyendo conjuntos, checkpoint, tokenizador, metadatos y scripts, mediante SHA-256 de origen y copia; se registró un manifiesto privado. Esta verificación no equivale a una segunda copia independiente del dispositivo. Posteriormente se restauraron 5 archivos de data/raw en el repositorio de trabajo actualizado, todos cotejados por SHA-256 origen–destino; contexts.json y papers.json coincidieron además con las huellas históricas A4. Las 2.700 pseudoetiquetas Haiku versionadas también coincidieron con su SHA histórico. Estos avances no restauran los cuatro checkpoints A4/Haiku.
# 5. Discusión
La reejecución SciBERT-A/Jurado muestra reproducibilidad computacional de una validación pseudoetiquetada (F1 macro 0,5709; accuracy 0,7635) sin reentrenar ni consultar test Gold. El error varía entre categorías: Application F1 = 0,88 y Background = 0,84 frente a Basis = 0,12 (n = 15) e Identification of the Originator = 0,00 (n = 1). La brecha accuracy–F1 macro refleja desbalance y soportes raros. En A4, SciBERT supera a SPECTER bajo una receta compartida, pero los tokenizadores/vocabularios difieren y algunos modelos SPECTER alcanzaron el límite de seis épocas sin mejora estabilizada; no se concluye superioridad intrínseca. La cobertura de B inferior al 60 % y la falta de Gold de chunks restringen cualquier inferencia de mejora por evidencia.

El jurado de tres modelos escala el pseudoetiquetado pero no reemplaza revisiones humanas independientes. El dataset v1 documenta seis de nueve clases por debajo de la meta de 2.000 consensos; el Gold debe permanecer fuera del entrenamiento, selección de checkpoints y ajuste de prompts. La fuente Haiku tiene 2.700 casos: 2.245 train y 397 val evaluables, más 58 abstenciones; 33 de estas se adscriben por citante y 25 quedan indeterminadas. Incluso exigiendo las cifras históricas de abstención por clase hay 5.320 asignaciones admisibles de esos 25 registros. El split original qlora_split_v2.json no se recuperó; no se ha creado aún un split derivado validado. Este bloqueo afecta la reproducción exacta de los metadatos de preparación, aunque los IDs evaluables históricos están versionados.
# 6. Conclusiones y trabajo futuro
Se recuperó SciBERT-A/Jurado con checkpoint-945, tokenizador, conjuntos 2.518/630 y scripts locales. La inferencia v3 sobre 630 pseudoetiquetas reprodujo exactamente F1 macro = 0,5709355717 y accuracy = 0,7634920635; no acredita validación humana ni independencia ante corpus externos. A4 conserva 12 corridas factoriales y 6 ablaciones con n = 732 Haiku: SciBERT-A/B 0,4669/0,4723 y SPECTER-A/B 0,3298/0,3024 de F1 macro medio. Se preservaron los datos originales de ACL-200 y las pseudoetiquetas con hashes verificados, pero persisten la ausencia del split v2 auténtico, de pesos A4, de Gold certificado y de relevancia Gold de chunks.

El cierre requiere respaldar fuera del dispositivo los datos privados, versionar un protocolo reproducible de verificación sin publicar pesos ni anotaciones, resolver el split A4 con un derivado expresamente rotulado (sin sustituir su SHA histórico) y recuperar o reentrenar con nueva procedencia los cuatro modelos A4. Se debe congelar un Gold humano canónico con revisión independiente y adjudicación, evaluar relevancia de chunks, revisar cobertura de B, presupuestos de entrenamiento por encoder, costos/latencia y funcionamiento del despliegue. La presente versión usa referencias numéricas IEEE de trabajo; antes del envío deben ratificarse cinco autorías/contribuciones y cualquier excepción frente a la regla institucional de grupos de cuatro.
# Declaración de uso de IA generativa
Se emplearon modelos generativos para pseudoetiquetar, asistentes de IA para programación, revisión y redacción, y herramientas para auditorías automáticas. Ninguna pseudoetiqueta se presenta como juicio humano; las hojas originales, revisores, fechas, adjudicación y cuota humana deben verificarse antes de certificar Gold. Los cinco nombres consignados corresponden a la autoría propuesta histórica; es indispensable confirmar la conformación oficial del grupo, contribuciones y autorizaciones institucionales antes del envío.
# Referencias
[1] S. Teufel, A. Siddharthan y D. Tidhar, «Automatic classification of citation function», en Proc. EMNLP, pp. 103–110, 2006. https://aclanthology.org/W06-1613/

[2] D. Jurgens, S. Kumar, R. Hoover, D. McFarland y D. Jurafsky, «Measuring the Evolution of a Scientific Field through Citation Frames», Transactions of the Association for Computational Linguistics, vol. 6, pp. 391–406, 2018. doi: 10.1162/tacl_a_00028.

[3] A. Cohan, W. Ammar, M. van Zuylen y F. Cady, «Structural Scaffolds for Citation Intent Classification in Scientific Publications», en Proc. NAACL-HLT, pp. 3586–3596, 2019. doi: 10.18653/v1/N19-1361.

[4] I. Beltagy, K. Lo y A. Cohan, «SciBERT: A Pretrained Language Model for Scientific Text», en Proc. EMNLP-IJCNLP, pp. 3615–3620, 2019. doi: 10.18653/v1/D19-1371.

[5] A. Cohan, S. Feldman, I. Beltagy, D. Downey y D. S. Weld, «SPECTER: Document-level Representation Learning using Citation-informed Transformers», en Proc. ACL, pp. 2270–2282, 2020. doi: 10.18653/v1/2020.acl-main.207.

[6] S. Rohatgi, Y. Qin, B. Aw, N. Unnithan y M.-Y. Kan, «The ACL OCL Corpus: Advancing Open Science in Computational Linguistics», en Proc. EMNLP, pp. 10348–10361, 2023. doi: 10.18653/v1/2023.emnlp-main.640.

[7] Grupo 19, «microproyecto-local-citation: código y evidencias del proyecto de grado», repositorio GitHub, commit fd335b0893f664308cedb6bc81ea19ea421b2a91, corte 16-nov-2026. [En línea]. Disponible: https://github.com/Byron971/microproyecto-local-citation.
## Trazabilidad de este corte frente al código (referencias internas)
• Snapshot verificado: GitHub main fd335b0893f664308cedb6bc81ea19ea421b2a91 (PR #183 y #191 fusionados; PR #192 aún abierto en el corte). Ejecutar validaciones locales en ese commit para reproducir el entorno.

• Matriz A4/Haiku (diferente del experimento Jurado): proyecto_de_grado/docs/evidencias_clasificacion_a4/comparacion.json; manifiesto_entradas.json; scibert_A_42/metricas_eval.json y equivalentes.

• Preparación y fugas A4: proyecto_de_grado/docs/evidencias_clasificacion_a4/{manifiesto_preparacion.json,manifiesto_entradas.json,fugas.json,ids_train.txt,ids_val.txt}; fuentes Haiku con SHA-256 verificado y Gold humano todavía no certificado.

• Recuperación sin Gold: proyecto_de_grado/docs/evidencias_recuperacion_densa_a1/resumen.json.

• Doble anotación no certificada: docs/acta_decision_test_gold_canonico_issue_100.md y proyecto_de_grado/docs/dataset_funciones_v1.md.

• Software: packages/clasificacion-funcion/src/clasificacion_funcion/dominio.py, clasificador_torch.py, src/app/main.py y settings.py.

• SciBERT-A/Jurado: scripts locales entrenar_scibert_a_jurado_gpu_v3.py; artifacts/entrada_a_jurado_scibert/{entrada_a_train,entrada_a_val}.jsonl; artifacts/experimento_scibert_a_jurado_provisional_v1/checkpoints/checkpoint-945; registro reproducido en issue #186 (15-nov-2026). Solo el código y las huellas resumidas son públicos, no los datos/pesos.
# Anexos y disponibilidad de materiales
Repositorio técnico: https://github.com/Byron971/microproyecto-local-citation; main auditado fd335b0893f664308cedb6bc81ea19ea421b2a91. La reproducción local SciBERT-A/Jurado está registrada en issue #186. Huellas SHA-256 privadas: train 430e6834856a17fe186f7d5ebd23524b26ffb5c776d137a5f8df35864257d915; val 3a1a971d3f672b007017c87c076365f6749aed51ca2207d45466b6a3fb2f98dc; checkpoint-945 5f3193f8e3a97afd2304e261b08f45a56194edc19887fd3daa74d235e8b3f6e8. Se verificaron 39 archivos del respaldo privado; falta una copia externa independiente. Los cuatro modelos A4 tienen manifiestos y predicciones versionadas, pero no pesos locales recuperados. No emplear Gold humano para ajustar modelos ni convertir métricas Haiku en resultados Gold.
