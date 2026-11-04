# Auditoría técnica: código, jueces LLM y reproducibilidad

Corte: 3 de noviembre de 2026, hora de Colombia. Documento de estado; **no** es un reporte de métricas científicas nuevas. Los resultados comunicados por el equipo se distinguen de las verificaciones realizadas en código.

## Arquitectura y estados verificables

| Componente | Fuente de código | Estado y advertencia |
|---|---|---|
| Recomendación de artículos | model-package/modelo_citas, src/app/recommender.py, src/app/main.py | TF-IDF y reordenador lineal. Recuperado en Windows, 91.170 pares de entrenamiento y 19.776 artículos expuestos por /api/estado; API en Docker saludable. Evidencia local reportada, no AWS. |
| Recuperación Top-3 de fragmentos del **citado** | PR #81; feature/corte-vertical-top3-s2 | BM25 léxico, no SciBERT. El PR fue fusionado a audit/preetiquetado-g0 y sus archivos **no están en main**. La rama incluye además trabajo posterior de evaluación humana Top-3. |
| Clasificación de nueve funciones | proyecto_de_grado, src/evaluation/commercial, SciBERT local | SciBERT C1 F1 Macro ~0,524 en validación de desarrollo; todavía no integrado en FastAPI. No es un resultado Gold independiente. |
| Jueces automáticos | proyecto_de_grado/src/data/preetiquetar_local.py y src/evaluation/commercial | Hay scripts y prompts genéricos, pero no una selección reproducible de 18.000 ni una corrida Haiku verificable de 2.700. El script local usa por defecto qwen3:4b-instruct; **no** documenta la corrida Haiku. |
| QLoRA | artefactos no versionados en main | No están qlora_citas_adapter, qlora_split.json, qlora_val_preds.jsonl en el repositorio inspeccionado. Pueden estar en almacenamiento externo; no concluir que no existen. |
| Wheel y Docker | PR #88, pyproject.toml y uv.lock | El PR #88 fue fusionado a main con nuevo bucket S3; la estación Windows usa una alternativa local con wheel 0.2.0. No mezclar soluciones ni asumir equivalencia del archivo solo por versión. |

## Respuestas que necesita el equipo

### 1. ¿Cómo fueron elegidas las 18.000 citas?

No existe en main un manifiesto de esos 18.000 IDs y sus filtros. El código preparar_preetiquetado.py selecciona **hasta 300** candidatos de ACL-200 train: conserva TARGETCIT, verifica citado y título, excluye IDs de práctica/piloto, ordena por ID, aleatoriza con semilla 42 y limita la muestra. Esto **no demuestra** cómo se escogió el lote de 18.000. Pedir CSV/JSONL de IDs, script y commit del selector, fuente, seed, reglas, exclusiones, conteos por filtro, duplicados, distribuciones por split y huella SHA-256.

### 2. ¿Qué versión de Haiku y qué prompt se utilizaron para clasificar 2.700?

No están identificados por una ejecución reproducible. Requerir proveedor, **ID exacto y versión/fecha de resolución de Haiku**, prompt completo y checksum, taxonomía/guía, parser, parámetros, fechas, IDs, corridas, responsables y evidencia de revisión humana. Se comunicaron 2.700 casos iniciales de train, 2.642 etiquetados y 58 no evaluables. **No debe inferirse que los 2.700 satisfacen automáticamente el requisito de revisión humana del 15 %.**

### 3. ¿Dónde están los artefactos QLoRA?

Proveer qlora_citas_adapter, qlora_split.json, qlora_val_preds.jsonl, modelo base y revisión, tokenizer, script de entrenamiento/inferencia, seed, split, hiperparámetros, librerías CUDA/PEFT/Transformers/bitsandbytes, versión de guías, IDs y hashes. Versionar código y metadatos en Git; pesos grandes en DVC/S3/almacenamiento aprobado con permisos y checksum.

### 4. ¿Quién usó la RTX 4070 Super?

No hay evidencia en main que identifique responsable, máquina o ejecución. Solicitar comando de entrenamiento, commit, run-id, salida nvidia-smi y versiones GPU/VRAM/driver/CUDA. **No atribuirle** la RTX 4060 Laptop utilizada en el entrenamiento local de SciBERT C1 a esa corrida de QLoRA.

### 5. ¿Las 595 citas de 1980–1999 cuentan como train?

Las particiones ACL-200 son por **año del CITANTE**: train 2009–2013 (30.390 consultas), validación 2014 (9.381), test 2015 (9.585). Un artículo **CITADO** de 1980–1999 puede pertenecer a un contexto train. Para decidir, verificar los 595 context_id frente a train/val/test originales y leer citing_id y refid por separado. La antigüedad del citado, por sí sola, no justifica descartarlo.

## Validez de las cifras de jueces

El equipo comunicó **82 % de acuerdo entre Sonnet y GPT en 200 casos** y **93 % de acuerdo respecto a referencias cuando coinciden QLoRA, Qwen y Llama**. Estas cifras no se calcularon a partir de predicciones disponibles en este repositorio. Sin numerador, denominador, cobertura del consenso, abstenciones y predicciones por clase, **no** se pueden llamar precisión Gold ni exactitud global. Un subconjunto en que tres modelos coinciden puede tener sesgo de selección.

La política de evaluación G0 exige revisar por humanos al menos ceil(0,15*N) elementos del dataset final: para N=18.000, al menos 2.700. Esta cuota es distinta del **Test Gold humano independiente**, con doble anotación ciega y adjudicación. Los archivos históricos annotations/citation_function/test_gold.jsonl y provisional_test_gold.jsonl corresponden a **20 casos usados en desarrollo**, no a un test nuevo e independiente. La propuesta de 450–500 casos tomados de test 2015 necesita ratificación, exclusiones históricas y protocolo de adjudicación.

## Herramienta de auditoría entregada

Archivo: proyecto_de_grado/scripts/auditar_lotes_jueces.py. Lee ACL-200 original y archivos opcionales TXT/CSV/JSONL/JSON con context_id, id o citation_id (si hay Excel, exportar antes a CSV). **No modifica las fuentes, no ejecuta LLM, no produce etiquetas ni reconstruye filtros desconocidos.**

Desde la raíz del proyecto, una vez disponibles los archivos:

    python proyecto_de_grado/scripts/auditar_lotes_jueces.py --raw data/raw --lote-18000 ruta/lote_18000.csv --etiquetas-2700 ruta/etiquetas_2700.csv --antiguas-595 ruta/antiguas_595.csv --qlora-dir ruta/qlora --manifest-jueces ruta/manifest.json --out proyecto_de_grado/artifacts/auditoria_jueces/resultado.json

Si no existen los archivos de lotes, ejecutar con solo --raw. Informará el tamaño ACL supervisado y declarará cuáles insumos no fueron aportados. El reporte comprueba: IDs únicos/duplicados, pertenencia a train/val/test, año del citante y del citado, TARGETCIT, superposición entre los 18.000 y 2.700, pertenencia de las 595, exclusiones históricas de Gold y presencia de artefactos QLoRA en la ruta consultada. La presencia física no demuestra aún que los artefactos puedan reproducir la inferencia.

Pruebas sintéticas sin red: python -m pytest -q proyecto_de_grado/tests/test_auditar_lotes_jueces.py. Se ejecutaron siete pruebas en entorno aislado local; **no se ha ejecutado todavía este informe sobre los archivos reales de los compañeros**.

## Integración, controles y calendario

1. Conservar los cambios locales antes de cualquier git pull, merge o cambio de rama: Dockerfile, .dockerignore, pyproject.toml, uv.lock, modelos y scripts locales. Comparar hashes del wheel local y del nuevo S3 de PR #88; elegir un método de distribución verificable con prueba desde clon limpio.
2. Preparar PR específico para llevar Top-3 desde la rama feature/corte-vertical-top3-s2 a main, con revisión/CI. La rama divergió y contiene trabajo posterior al PR #81; no fusionar ciegamente. El corpus real en proyecto_de_grado/artifacts/top3_s2/casos_train.json es local: su ausencia produce 503 en el adaptador y requiere generación o montaje en Docker.
3. Integrar SciBERT C1 a FastAPI como módulo de **clasificación de función**, sin confundirlo con ranking de artículos ni con BM25 de fragmentos. Reportar F1 Macro de desarrollo separado de Gold.
4. Aportar manifiestos de selección, Haiku, QLoRA, hardware y Gold. Solo entonces recalcular los porcentajes y actualizar el artículo.
5. Fechas comunicadas por el equipo: 26 de noviembre informe de despliegue, 27 sustentación y 29 informe final (2026). Confirmarlas contra el cronograma oficial.

No convertir metas, mensajes del grupo o archivos faltantes en resultados científicos demostrados.
