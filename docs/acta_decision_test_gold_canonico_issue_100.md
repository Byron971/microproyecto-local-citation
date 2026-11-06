# Acta de decisión del Test Gold canónico — Issue #100

Fecha de elaboración: 2026-11-05  
Responsable de coordinación: John Byron Arias Sanz (@Byron971)  
Estado: **PLANTILLA / PENDIENTE DE EVIDENCIA Y APROBACIÓN**. No es una certificación ni una autorización para evaluar modelos sobre test.

## 1. Alcance y fuentes que se deben conciliar

La tarea es designar **un solo manifiesto canónico de test**, no crear etiquetas ni solicitar reanotar ejemplos previamente revisados.

| Fuente | Qué sabemos de artefactos del equipo | Lo que aún NO demuestra |
|---|---|---|
| PR #91: `proyecto_de_grado/anotacion/test_gold_v2/manifiesto_ids.csv` | Selección 1.533 IDs de test (2015), en tandas 519/441/573; 20 calibraciones de 2014 | Que las 1.533 muestras tengan dos anotaciones humanas independientes y decisión adjudicada |
| PR #92: `proyecto_de_grado/anotacion/test_gold/TEST_GOLD_2700_ANOTADO.csv` | 2.700 registros: 1.321 de 2014 y 1.379 de 2015; 5 exclusiones históricas (1 validación, 4 test) | Procedencia, identidad y fecha de las revisiones, ceguera y adjudicación |
| PR #92: `notebooks/qlora-training/ANOTACION_UNICA_2700_CITAS_REALES_ANOTADO.csv` | 2.700 ejemplos preetiquetados por Haiku para entrenamiento; disjuntos por ID de los 2.700 registros del CSV de anotaciones | Ausencia de contaminación por documento, par, texto y ajustes de prompts |
| PR #143 | Conciliación por ID: 832 coincidencias PR #91/PR #92, 701 exclusivos PR #91, 547 exclusivos PR #92 | Doble anotación, splits ACL oficiales ni Gold final aprobado |

**Regla:** un ID común en dos archivos no representa automáticamente dos anotadores. Los 701 exclusivos del PR #91 pueden tener hojas humanas privadas; buscarlas y conciliar sin repetir su trabajo. Los 547 exclusivos del PR #92 no sustituyen automáticamente a los anteriores.

## 2. Evidencias requeridas (sin publicar datos sensibles)

Registrar en este documento solo **rutas de acceso restringido, hashes, conteos y responsables**, nunca las etiquetas individuales del test ni texto de citas protegido.

| Evidencia | Responsable de validación | Referencia segura / SHA-256 | Estado |
|---|---|---|---|
| Hojas originales de las tandas 519, 441, 573 y su asignación | José + Caicedo | PENDIENTE | No verificada |
| Relación por ID entre hojas originales, 701 exclusivos y 832 comunes | José + Caicedo | PENDIENTE | No verificada |
| Identificación de dos evaluadores independientes, ceguera y fechas | José + Caicedo | PENDIENTE | No verificada |
| Regla de adjudicación, resolución de desacuerdos y registro de abstenciones | Equipo de anotación | PENDIENTE | No verificada |
| Acuerdo interanotador y soporte por clase calculados sobre doble anotación real | Equipo de anotación | PENDIENTE | No verificada |
| Splits oficiales ACL-200 y DVC: train/val/test por ID/documento/par | John + José | PENDIENTE | No verificada |
| Verificación de no-leakage sobre train Haiku, jurado y cualquier tuning | John + Duque | PENDIENTE | No verificada |
| Dataset final depurado y proporción humana real por clase (objetivo >=15 %) | Caicedo + John | PENDIENTE | No verificada |

## 3. Decisión explícita del manifiesto

**No escoger por defecto la unión de PR #91 y PR #92.** La decisión requiere soporte de procedencia, particiones oficiales y adjudicación.

- Fecha de decisión: **PENDIENTE**
- Opción aprobada (PR #91 / subconjunto PR #92 / selección reconciliada y justificada): **PENDIENTE**
- Justificación científica y regla de inclusión/exclusión: **PENDIENTE**
- Ruta del manifiesto canónico, acceso restringido: **PENDIENTE**
- SHA-256 del manifiesto canónico: **PENDIENTE**
- Total de IDs test únicos elegibles: **PENDIENTE**
- Casos evaluables (excluir/contabilizar por separado Ambiguo y No evaluable): **PENDIENTE**
- Total de IDs de 2014 reservados exclusivamente a validación: **PENDIENTE**
- Exclusiones históricas aplicadas sin borrar archivos de origen: **PENDIENTE**
- Documentos citantes, citados y pares únicos en cada split: **PENDIENTE**
- Intersección de IDs, documentos y pares entre train/val/test (debe ser cero): **PENDIENTE**
- Denominador del dataset final tras depuración: **PENDIENTE**
- Numerador de ejemplos efectivamente validados por humanos: **PENDIENTE**
- Proporción humana real y por clase: **PENDIENTE**
- Métrica de acuerdo y protocolo de resolución de desacuerdos: **PENDIENTE**

No sustituir una prueba de solapamiento por ID por una prueba de aislamiento a nivel de documento. Si algún control detecta intersecciones, **bloquear publicación y evaluación definitiva**.

## 4. Flujo de aprobación

1. **José y Caicedo:** contrastar las hojas humanas privadas con los dos manifiestos; indicar qué trabajo ya está realizado, quién anotó de forma independiente y cómo se adjudicó. No solicitar volver a anotar sin detectar primero una ausencia real.
2. **John:** verificar splits ACL-200 reales con DVC, exclusiones, hashes, independencia a nivel citante/citado/par y cobertura del dataset final.
3. **Carlos Duque:** confirmar que ningún Gold test entró a entrenamiento, elección de checkpoint, prompts, jueces ni ablaciones; entregar manifiestos de entrenamiento, modelos y seeds.
4. **Equipo:** elegir una sola política de inclusión y firmar el manifiesto. Dejar en un registro restringido la identidad de los revisores y las resoluciones por ejemplo.
5. **John:** únicamente después de las verificaciones, versionar el manifiesto canónico y habilitar un proceso de evaluación final aparte del evaluador actualmente provisional.

### Registro de conformidad

| Rol | Decisión (aprobado / cambios requeridos) | Fecha | Evidencia |
|---|---|---|---|
| John — coordinación y controles de splits | PENDIENTE | — | — |
| José — revisión humana y adjudicación | PENDIENTE | — | — |
| Caicedo — cobertura y procedencia | PENDIENTE | — | — |
| Duque — aislamiento experimental | PENDIENTE | — | — |
| Gabriel — revisión editorial de informe/artículo | PENDIENTE | — | — |

## 5. Gate objetivo del Issue #100

No marcar completado ni declarar «Test Gold definitivo» hasta tener, conjuntamente:

- [ ] Un único manifiesto con ruta, versión, SHA-256 y partición test avalada por archivos oficiales.
- [ ] Evidencia de la revisión humana y de independencia de anotadores; acuerdo y adjudicación verificables.
- [ ] Exclusiones y tratamiento de Ambiguo/No evaluable documentados.
- [ ] Cruces automáticos de IDs **y documentos y pares** entre train/validation/test, con intersecciones cero.
- [ ] Numerador y denominador de la validación humana del corpus final, más desglose por clase.
- [ ] Aprobaciones expresas registradas y bloqueo levantado mediante cambio revisable, no por editar manualmente una bandera.

**Estado actual:** NO CERTIFICADO. El benchmark `paired_benchmark.py` sigue siendo provisional. Los resultados históricos de microproyecto no constituyen automáticamente las métricas del proyecto de grado.

## 6. Dependencias y enlaces de trabajo

- Issue #100: https://github.com/Byron971/microproyecto-local-citation/issues/100
- Issue #111 y PR #143 (conciliación): https://github.com/Byron971/microproyecto-local-citation/pull/143
- Auditoría existente: `docs/auditoria_congelamiento_gold_john_100.md`
- Protocolo experimental: `docs/protocolo_experimental_grado_2026_11.md`
- Auditoría de CSV: `src/evaluation/commercial/gold_existing_csv_audit.py`
- Conciliación PR #91/#92: `src/evaluation/commercial/gold_manifest_reconcile.py` **en PR #143, aún no fusionado al momento de preparar el acta**.

Esta acta registra decisiones pendientes y **no** altera datasets, modelos ni etiquetas.
