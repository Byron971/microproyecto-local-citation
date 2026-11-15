# Plan de rescate técnico con Copilot cloud agent — 15/11/2026

Este documento contiene instrucciones de trabajo para asignar a Copilot desde Issues. NO equivale a aprobación del equipo, ni certifica resultados científicos. Cada bloque es un PR diferente, basado en el main actualizado. Antes de asignar tareas, fusionar tras revisión el PR de copilot-instructions y confirmar que el fix de CI #159 esté aprobado.

## Orden y reglas
- Prioridad 0: dejar CI verde y proteger el Gold.
- Prioridad 1: mejorar los fragmentos/recuperación y habilitar inferencia real.
- Prioridad 2: completar métricas de evaluación, despliegue y documentación.
- Cada tarea: crear rama desde main, ejecutar tests, PR en draft, no hacer merge. No modificar archivos de resultados existentes ni datos Gold.
- Si falta GPU, DVC o credenciales, hacer tests sintéticos y reportar qué no pudo ejecutarse; no fingir validación.

## Tarea Copilot A: issue #101 — fragmentación robusta V2, sin sustituir V1
Objetivo: bajar descartes por párrafos >300 palabras en el corpus sin alterar los experimentos ya reportados.
Instrucciones: estudiar packages/auditoria-corpus, proyecto_de_grado/src, la auditoría A1 y sus pruebas. Agregar un fragmentador configurable V2 que separe párrafos largos por oraciones o ventanas cuando sea necesario, mantenga procedencia de sección, IDs globalmente unívocos por (cited_id, chunk_id), límites de hasta 300 palabras/2 párrafos y fidelidad al texto salvo normalizaciones documentadas. No modificar el algoritmo V1 por defecto ni los artefactos previos. Medir sobre la misma muestra A1, publicar script y reportar antes/después incluyendo exclusiones y sesgo por clase. Si datos DVC faltan, aportar comando reproducible y marcar la medición no ejecutada.
Criterios: tests de cortes por fórmulas, encabezados omitidos, párrafos largos, IDs, reconstrucción, determinismo y protección de V1; CI sin fallos; informe sin cifras inventadas.

## Tarea Copilot B: issue #127 — evaluación Top-3 con Gold de chunks
Objetivo: poder puntuar BM25 y SciBERT sobre relevancia humana independiente.
Instrucciones: inspeccionar proyecto_de_grado/docs/politica_evaluacion_g0.md, paquetes de recuperación, issue #127. Crear protocolo y esquema de importación de dos evaluaciones humanas ciegas de cada (context_id, cited_id, chunk_id), validación de identidades, duplicados, cobertura del universo evaluado, consenso/adjudicación y abstenciones; implementar Hit@3, Recall@3 y MRR@3 con denominadores explícitos, separado del Gold de función de cita. No usar puntuaciones BM25/SciBERT como etiquetas humanas ni asumir que existen las 100 consultas anotadas. Excluir de tuning las consultas de evaluación final.
Criterios: tests pequeños con etiquetas ficticias verificables, métricas con cálculos manuales comprobados, CLI que rechaza Gold incompleto y documentación del esquema; sin métricas reales si no hay juicios humanos.

## Tarea Copilot C: issues #103 #104 #109 #110 — reproducibilidad del benchmark A4
Objetivo: obtener un benchmark único y fail-closed para SciBERT-A/B, SPECTER-A/B.
Instrucciones: estudiar src/evaluation/commercial/a4_factorial_benchmark.py, packages/clasificacion-funcion/, docs/protocolo_experimental_grado_2026_11.md y reporte A4. Integrar manifiestos reales checkpoint/train/input con SHA-256, mismas muestras para cada contraste y nueve clases. Incluir tablas por clase, matrices y delta pareado, abstenciones y chequeos anti-leakage; mantener las etiquetas Haiku como PROVISIONAL. No evaluar Gold humano ni seleccionar hiperparámetros usando eval 2015, que solapa candidatos de Gold v2. Registrar qué experimentos ya existen; no volver a entrenar ciegamente.
Criterios: pytest de ambas áreas verde, CLI demo con datos sintéticos, scripts reproducibles y README que identifica qué no se pudo correr con GPU/Gold.

## Tarea Copilot D: issues #107 #116 — integrar React + FastAPI + inferencia científica real
Objetivo: una demo de extremo a extremo, sin modelos fingidos.
Instrucciones: partir del main más reciente. Leer PR #156 y rama feature/despliegue-aws-ecs-137 para recuperar selectivamente el frontend React y rutas compatibles; NO fusionar toda la rama divergente. Estudiar API actual src/app/main.py y las configuraciones seguras; crear un adaptador opcional de modelo para recuperar Top-3 con SciBERT sobre chunks del citado y otro para clasificar en las nueve funciones usando un checkpoint REAL del paquete A4, con manejo de pesos no disponibles, límites de CPU/RAM y respuestas 503 transparentes. Mantener el baseline BM25/TF-IDF accesible y claramente etiquetado. La UI debe indicar disponibilidad efectiva; nunca presentar BM25 como SciBERT ni mostrar un mock como inferencia.
Criterios: npm ci, build, tests frontend, pytest backend, prueba E2E de entrada válida y errores, flujo contexto -> artículo citado -> Top-3 SciBERT -> función de cita; una ejecución real reproducible con checkpoint, o indicar por qué se bloqueó.

## Tarea Copilot E: issues #137 #116 #119 — desplegabilidad segura AWS
Objetivo: CI reproducible que distinga validación sin credenciales de despliegue autorizado.
Instrucciones: inspeccionar .github/workflows/deploy-api.yml, terraform.yml, .github/actions/aws-session, terraform/README.md y logs del workflow de main del 15/11/2026. Hacer que tests de Terraform y Docker funcionen sin credenciales; exigir una acción explícita/autorizada para apply y despliegue y fallar claramente si no hay credenciales de AWS cuando se solicita despliegue real. Preferir credenciales efímeras cuando la cuenta lo soporte. No crear recursos AWS, no ejecutar apply/destroy, no publicar keys ni desactivar chequeos.
Criterios: terraform fmt/validate pasan, tests CI y smoke simulados pasan, documentación de secrets/roles, costos y pasos de validación externa cuando exista una cuenta autorizada. No afirmar que una URL está disponible sin probarla.

## Tarea Copilot F: issues #98 #99 #100 — herramienta de auditoría humana (NO etiquetado por IA)
Objetivo: reducir trabajo administrativo sin sustituir a los jueces humanos.
Instrucciones: preparar script que lea hojas humanas privadas locales sin publicarlas, valide 2 revisores independientes por cita, presencia de justificación, estatus, protocolo de ceguera verificable donde existan registros, calcule κ/α, exporte solo agregados y genere discrepancias para adjudicación privada. Conciliar IDs entre candidatos Gold PR #91 y #92 y splits oficiales ACL-200; calcular porcentaje humano sobre denominador real del dataset. Mantener bandera gold_human_certified=false salvo acta explícita de equipo y manifiesto congelado; no certificar automáticamente por pasar tests.
Criterios: tests sintéticos para duplicates/splits/abstenciones/desacuerdos, no exfiltración de etiquetas, reporte reproducible y evidencia pendiente explícita.

## Tarea Copilot G: issues #112–#115 — artículo final y auditoría editorial
Objetivo: elaborar un artículo científico de hasta 12 páginas, usando solo resultados comprobados.
Instrucciones: leer rúbrica en docs/matriz_rubricas_100_distribucion_2026_11.md y resultados verificables. Preparar fuente editable con problema, metodología A1–A7, cuatro celdas A4, Gold humano como pendiente hasta verificación, experimentos medidos, limitaciones y discusión de hipótesis. No inventar citas DOI, cifras, niveles de acuerdo humano, URL ni resultados de test. Un verbo principal por objetivo, resumen de 200–300 palabras, 3–5 palabras clave, declaración de uso de IA, referencias verificables y trazabilidad tabla rúbrica -> sección -> evidencia.
Criterios: pruebas de formato/extensión, validación de figuras/tablas, PDF revisado y auditoría de cada afirmación cuantitativa.
