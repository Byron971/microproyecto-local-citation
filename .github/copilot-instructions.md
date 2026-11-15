# Instrucciones para GitHub Copilot — proyecto de grado

## Distinguir los dos productos
Este repositorio contiene (1) un microproyecto histórico de recomendación de ARTÍCULOS mediante TF-IDF y reordenador lineal, en model-package/ y src/app/, y (2) una tesis de recuperación de Top-3 FRAGMENTOS dentro del artículo citado y clasificación de la función de la cita en nueve categorías, en proyecto_de_grado/, packages/recuperacion-densa/ y packages/clasificacion-funcion/.
No confundir recomendación de artículos con recuperación de evidencia textual. La API de main usa por defecto packaged_tfidf_linear y bm25_lexical. No afirmar que SciBERT, SPECTER ni el clasificador de nueve funciones están integrados hasta demostrar inferencia real.

## Fuentes de verdad y rigor científico
- Revisar proyecto_de_grado/docs/retroalimentacion_propuesta_V3.md, docs/matriz_rubricas_100_distribucion_2026_11.md, docs/protocolo_experimental_grado_2026_11.md.
- ACL-200 provee contextos/IDs/splits; ACL OCL provee texto completo del citado, enlazado por ID. No convertir MultiCite en supuestas etiquetas equivalentes.
- Respetar taxonomía en docs/guia_anotacion_funcion_cita.md. Hay nueve clases. Ambiguo/No evaluable son abstenciones, no una décima clase.
- Gold humano: docs/acta_decision_test_gold_canonico_issue_100.md. Sigue SIN CERTIFICACIÓN hasta completar doble anotación humana independiente, adjudicación, no-leakage, cuota humana del 15% y manifiesto congelado. No usar el Test Gold para entrenar, hacer tuning, seleccionar prompts o checkpoints.
- A4: proyecto_de_grado/docs/clasificacion_funcion_a4.md. Resultados PROVISIONALES con etiquetas Haiku; no presentarlos como evaluación final humana. Comparar SciBERT-A/B y SPECTER-A/B con mismos IDs, semillas y protocolo. Procedencia de etiquetas Haiku/Jurado es factor aparte.
- A1/Top-3: proyecto_de_grado/docs/recuperacion_densa_scibert_a1.md. Acuerdo SciBERT/BM25 NO es relevancia. No informar Hit@3, Recall@3 ni MRR@3 sin Gold independiente de relevancia por pareja (contexto, chunk), ver issue #127.

## Ubicación de componentes y comprobaciones
- API FastAPI: src/app/main.py. Configuración: src/app/settings.py. Docker: docker-compose.yml.
- Benchmark A4: src/evaluation/commercial/a4_factorial_benchmark.py.
- Clasificación: packages/clasificacion-funcion/. Pruebas: cd packages/clasificacion-funcion && uv sync --locked && uv run pytest -q.
- Recuperación: packages/recuperacion-densa/. Pruebas: cd packages/recuperacion-densa && uv sync --locked && uv run pytest -q.
- Auditoría: packages/auditoria-corpus/. Pruebas: cd packages/auditoria-corpus && uv sync --locked && uv run pytest -q.
- Evaluación adicional: tests/ y proyecto_de_grado/tests/; workflow .github/workflows/evaluacion-citas.yml.
- Interfaz React puede estar en ramas de desarrollo y NO existe en main actualmente. Al integrarla, usar Node >=22.12, npm ci, npm run build, npm test y E2E pertinentes.

## Reglas de ejecución obligatorias
1. Partir de main actual, una rama y un PR pequeño por issue. Jamás modificar directamente main ni fusionar automáticamente.
2. Leer código, PR y workflows existentes antes de escribir; evitar duplicar endpoints, modelos o pipelines.
3. Mantener hashes SHA-256 y verificaciones estrictas, trazabilidad DVC, splits por documento/par y comportamiento fail-closed. No desactivar validaciones para dejar CI verde.
4. NO alterar anotaciones Gold, etiquetas humanas, predicciones históricas, resultados publicados ni manifiestos para aparentar cumplimiento. Si faltan insumos privados, documentar bloqueos y entregar scripts verificables, sin inventar resultados.
5. Nunca inventar métricas, citas, cobertura, URLs públicas ni despliegues. Cada cifra debe incluir procedencia, n, split, modelo, semilla y advertencia provisional si aplica.
6. No agregar secretos, credenciales AWS, tokens o .env reales. No ejecutar terraform apply/destroy, ni provisionar AWS con costos, sin autorización explícita. CI debería poder validar sintaxis sin credenciales.
7. La integración del producto requiere inferencia real y tests E2E de éxito/error. No presentar BM25 como SciBERT ni puntajes de similitud como probabilidades.
8. Ejecutar pruebas locales y de CI pertinentes; añadir test de regresión. Si GPU/AWS/DVC no son accesibles, declarar exactamente lo omitido.
9. Cada PR debe explicar problema, enfoque, archivos, comandos y resultados reales, comportamiento antes/después, riesgos y dependencias. No cerrar issues antes de verificar criterios de aceptación.

## Tres niveles distintos de cumplimiento
Separar: (a) código escrito, (b) experimento ejecutado/reproducible y (c) objetivo académico validado. Tests sintéticos y CI verde no certifican Gold humano ni resultados científicos.
