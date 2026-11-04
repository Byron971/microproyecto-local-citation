# Cierre de tesis — auditoría de código, estado y plan del equipo (3/11/2026)

**Estado de este documento:** propuesta operativa para revisión del equipo; ninguna asignación aquí equivale a aceptación de la persona indicada. Datos y cifras de cuadernos/README del PR #91 se distinguen de salidas auditadas. **No sustituye el cronograma oficial de Uniandes.**

## Alcance real, no confundir tres productos

1. **MVP heredado de recomendación de artículos:** `model-package/modelo_citas`, `src/app/main.py`, FastAPI+dashboard y Docker. Localmente se verificó `/api/estado`: 19.776 artículos, 91.170 pares de entrenamiento y contenedor Healthy. Fue reconstruido un wheel 0.2.0; todavía no hay prueba reciente de producción AWS.
2. **Recuperación Top-3 dentro del *artículo citado*:** `feature/corte-vertical-top3-s2` y PR #90 (borrador); BM25 léxico y prototipos exploratorios SciBERT/ACL OCL. **El PR #81 fue fusionado a `audit/preetiquetado-g0`, no a `main`.** Faltan corpus versionado accesible en Docker, evaluación humana de relevancia de chunks y ablación C1/C2 en Gold.
3. **Clasificación de nueve funciones:** SciBERT C1 supervisado sobre etiquetas automáticas provenientes de lote 2.700 (2.642 utilizables; split interno train 2.115, validación 527), F1 Macro desarrollo 0,523968; todavía sin endpoint/producto integrado ni evaluación sobre Gold. Jurado open-weight v3 en PR #91 y QLoRA de Carlos Duque son líneas paralelas.

## Cifras del jurado documentadas en PR #91 (no recalculadas desde CSV)

- Entrada total: 18.000; 3/3 consenso: 5.227; 2/3 consenso: 9.349; sin consenso: 3.424; κ de Fleiss comunicado: 0,356.
- Cobertura con al menos 2/3: **14.576/18.000 = 80,98 %**. Los votos agregados entre nueve categorías suman **14.525**, faltan 51 registros con consenso no distribuido entre las nueve (posibles estados de abstención; comprobar en `jurado_18000_v3.csv`).
- Distribución reportada: Background 4.786; Application 3.104; Evidence 2.009; Comparison 1.909; Improvement/Modification 1.155; Gap 995; Basis 382; Further Reading 153; Identification of the Originator 32. La meta de 2.000 **por cada una de nueve clases** claramente **no está alcanzada** en siete categorías y precisa estrategia/aceptación metodológica.
- Muestra de desarrollo para escoger jurado: 200; referencias Sonnet/GPT coincidieron en 164 (82 %, κ 0,757 comunicado). Acierto 93 % **condicionado a coincidencia triple** en 55 casos, y 71 % condicionado a coincidencia doble en 82; no son exactitud global ni Gold humano. Al seleccionar los jueces en estas mismas 200 citas, estos porcentajes pueden ser optimistas.
- README PR #91 describe Sonnet modelo `claude-sonnet-5-5` y GPT modelo `gpt-6.1-sol` como referencias de desarrollo, no Gold. Los ID exactos se ven en celdas del notebook; verificar ejecuciones/metadata.

## Análisis de código: fallos y salvaguardas prioritarios

**A. Fuente de verdad de splits (crítico).** `jueces_open_weight.ipynb` contiene `particion(cid)` que infiere train/val/test leyendo `cid[1:3]`; asigna 2000–2013 a train y aparta 1980–1999. El ACL-200 supervisado versionado define train **2009–2013 (30.390)**, val **2014 (9.381)** y test **2015 (9.585)**. La inferencia por año **no demuestra pertenencia al split** y puede incluir contextos no supervisados. Auditar los 18.000/595/519 por `context_id` frente a `data/raw/{train,val,test}.json` antes de usar etiquetas, seleccionar Gold o entrenar B. El año del *citado* nunca determina el split del *citante*.

**B. GOLD aún no certificado (crítico).** `anotacion_test_gold.ipynb` prepara calibración 3 (20 de val 2014) y tres tandas Gold de test 2015: 519, 441, 573 (1.533 acumulados), con 5 personas y 10 parejas; hojas `TestGold_T1_v2_<Apellido>.xlsx`. La generación de hojas **no prueba** que se llenaron, que se mantuvo cegamiento o que exista adjudicación. `clave_coordinador_v2.csv` contiene voto del jurado y debe mantenerse fuera de las hojas/alcance de los anotadores. Verificar esquema, IDs únicos, fechas, dos juicios independientes, κ/α, adjudicaciones y huellas de las hojas antes de llamar Gold a las etiquetas.

**C. 15 % de validación humana distinto de Gold (crítico).** La propuesta exige al menos 15 % del corpus final validado por personas. Si se conserva N=18.000 son 2.700; si el dataset final fuese 14.525 con función válida, **2.179**. Incluso las **1.533 citas** previstas para tres tandas (si completas y adjudicadas) no satisfacen por sí solas ninguna de esas cuotas. El número definitivo depende de N, las clases aceptadas y la revisión humana efectiva. Evitar considerar 2.700 anotaciones de Haiku como revisiones humanas. Ratificar cambios de alcance con docente y reportar si meta no es viable.

**D. Ruido de taxonomía (crítico).** Hoja Guia del Excel Haiku usada para QLoRA define Basis «fundamenta una afirmación o premisa», solapándose con Evidence. La guía oficial `docs/guia_anotacion_funcion_cita.md` define Basis como base intelectual/conceptual directa y Evidence como soporte de una afirmación específica. SciBERT C1 entrenó sobre esa fuente automática; preservar C1 A, medir sesgo Basis/Evidence, congelar guía y no corregir usando Gold.

**E. Reanudación sin control fuerte de versiones (alto).** `jueces_open_weight.ipynb` guarda resultados por `VERSION` y reanuda usando `leer_hechos` según contexto, sin validar en cada registro el hash del prompt, ID/revisión exacta del modelo ni hash del CSV de entrada antes de reutilizarlo. `HASH_PROMPT` depende del prompt construido para **la primera fila** (incluye contenido del caso), no solo de la plantilla; no es un fingerprint de configuración puro. Implementar manifiesto por corrida con fuente/IDs/hash, modelos y versiones, parámetros, rotaciones, prompt y tokenizador, y bloquear reanudación incompatible.

**F. Muestreo Gold condicionado al jurado (alto).** `cuotas_test` estratifica según predicción del jurado. Es útil para clases raras, pero se debe reportar como **selección estratificada por pseudoetiqueta**, no muestra aleatoria simple representativa de población; medir cobertura y tasas de discrepancia por clase. Congelar test antes de comparar C1 A/B y excluir **todos los IDs Gold y sus citantes** del entrenamiento B. No evaluar sobre las 200 citas usadas para escoger modelos.

**G. Captura de anotación (medio).** La hoja Excel marca `COMPLETO` para un caso `Evaluable` con función y confianza aunque se deje vacía la justificación, mientras las instrucciones requieren una frase. Corregir fórmula / validación antes de distribuir hojas nuevas; **no regenerar ni sobrescribir hojas ya anotadas**. Las definiciones del Excel deben cotejarse con guía versionada.

**H. Despliegue y ramas (alto).** PR #88 nuevo bucket S3 está fusionado en main; estación Windows usa wheel local y `uv.lock` distintos sin commit. Comparar hash del wheel y fijar distribución reproducible, pruebas de clon limpio y CI. PR #90 Top-3 y PR #91 jurado aún no fusionados a main; validación CI de tests no equivale a ejecutar notebooks GPU en Colab ni a probar inferencia AWS.

**I. Limitaciones científicas/seguridad.** No atribuir F1 a juicios automáticos sobre Gold inexistente. En Top-3 reportar Hit@3/Recall@3/MRR@3 solo cuando humanos hayan adjudicado chunks; no confundir scores BM25 con probabilidades. Documentar licencias ACL y evitar publicar artículos completos/datos restringidos o credenciales. El pre-etiquetado automático no se convierte en Gold.

## Decisiones del equipo que bloquean el cierre

- [ ] Ratificar el tamaño final N, la cuota de 2.000/clase y cómo se abordará la insuficiencia de las clases escasas. **Docente/experto, a más tardar 6-nov.**
- [ ] Ratificar cuota mínima de revisión humana del 15 % y distinguirla de Test Gold. **Coordinación, 6-nov.**
- [ ] Congelar guía Basis/Evidence y la versión de hojas; registrar discrepancias de versiones ya entregadas. **Coordinación, 4-nov.**
- [ ] Obtener dataset 18.000, CSV v3, QLoRA adapter/split/preds, Excel de 2.700, logs de subagentes y archivos Gold; ejecutar auditoría ACL sobre IDs. **Duque + Caicedo, 5-nov.**
- [ ] Confirmar que las fechas comunicadas 26-nov despliegue, 27-nov sustentación, 29-nov informe final sean las del aula. **Coordinación, 4-nov.**

## Asignación propuesta — revisar y aceptar en el grupo

`Arias` = John Arias; `Caicedo` = Carlos Caicedo (por mensaje «Carlos C», confirmar); `Duque` = Carlos Duque. Pinzón y Zambrana se identifican como anotadores en el notebook; el liderazgo por entregable sugerido abajo **no es un acuerdo previo**.

| Fecha límite | Responsable propuesto | Actividad | Criterio de cierre |
|---|---|---|---|
| **04-nov** | Los cinco: Arias, Caicedo, Duque, Pinzón, Zambrana | Calibración 3, 20 citas val 2014, individual | 5 hojas completas, sin consultar otras respuestas ni jurado; SHA/versión |
| **05-nov** | Caicedo, co-revisión Pinzón | Medir acuerdo/calibración, llamada de adjudicación, congelar guía | κ/α, matriz Basis/Evidence y acta sin usar calibración como Gold |
| **05-nov** | Duque | Subir adapter QLoRA, qlora_split, qlora_val_preds, config | Enlaces, hash, base model, hiperparámetros, GPU, métricas |
| **05-nov** | Duque, auditoría Arias | Manifiesto de selección y 18.000 IDs/CSV juez | Algoritmo/seed/splits, conteos filtros, cobertura/descartes, hashes |
| **06-nov** | Caicedo, auditoría Arias | Verificar 519 TestGold T1 v2 y excluir IDs históricas/595 | Manifiesto 519 test reales, 2 anotadores/caso, hoja ciega sin voto |
| **06-nov** | Caicedo + todos | Ratificar N, 2.000/clase, 15 % humano y escalamiento | Acta con docente/decisión explícita |
| **07-nov** | Arias | Conciliar PR #88 con wheel local, resguardar modelos | Prueba API desde instalación limpia y hash wheel |
| **08-nov** | Arias, revisión Caicedo | Integrar PR #90 Top-3 con pruebas | Endpoints BM25 funcionando; corpus disponible, smoke E2E |
| **09-nov** | Arias | Integración SciBERT C1 A a FastAPI/dashboard | Endpoint 9 clases, artefacto, tests y latencia |
| **10-nov** | Cinco anotadores (coordinación Caicedo) | Terminar T1: 519 citas (≈208 por persona) | 1.038 juicios independientes, archivos completos |
| **11-nov** | Caicedo + Pinzón | Adjudicación T1, auditoría de Gold | κ/α, desacuerdos, adjudicador, Gold T1 congelado |
| **12-nov** | Duque, evaluación Arias | Preparar variante SciBERT B con etiquetas de jurado SOLO train | Splits y hashes, validación desarrollo, checkpoint B |
| **13-nov** | Caicedo, equipo anotador | Generar/distribuir T2 441 y T3 573 si se aprueba carga | IDs congelados, versiones sin sobrescribir hojas T1 |
| **14-nov** | Arias + Pinzón | Calibrar evaluación humana Top-3 y baseline BM25/SciBERT | 100 casos planificados o número viable ratificado, juicios de chunks |
| **17-nov** | Cinco anotadores | Completar T2/T3, sujetos a decisión del 15 % y disponibilidad | Hojas dobles completas y sin ver etiquetas automáticas |
| **19-nov** | Caicedo + Zambrana | Adjudicar T2/T3, cerrar manifiesto Gold y cobertura humana | IDs test certificados, acuerdo por clase, recuentos reales 15 % |
| **20-nov** | Arias + Duque | Evaluación congelada A vs B vs jurado; ablation C1/C2 | F1 Macro, por clase, matrices, cobertura, intervalos, errores |
| **21-nov** | Arias | Docker, AWS y pruebas de recuperación | URL/servicio verificable, health, predict, modelos, CI y logs |
| **23-nov** | Zambrana, Caicedo, Duque | Borrador artículo/informe con resultados verificables | Métodos, sesgos, límites, autoría y referencias; no cifras inventadas |
| **24-nov** | Arias | Informe técnico de despliegue, manuales y video demo | Evidencias de AWS, seguridad, costos y clon limpio |
| **25-nov** | Pinzón + equipo | Revisión cruzada documento, presentación y simulacro | Lista de defectos críticos resueltos |
| **26-nov** | Arias + equipo | Entrega informe de despliegue | Archivo, evidencias y comprobante |
| **27-nov** | Todos (coordinación Caicedo) | Sustentación | Demo estable y roles acordados |
| **29-nov** | Todos (edición Zambrana) | Informe final de tesis | Revisión metodológica, anexos y comprobante |

**Hito intermedio:** 10-nov = MVP integrado local + T1 con anotaciones; **hito final académico:** 29-nov. Un MVP técnico no constituye cierre de tesis.

## Evidencia disponible y límites

- Repositorio: https://github.com/Byron971/microproyecto-local-citation
- PR #88: paquete remoto S3 fusionado main
- PR #89: auditoría reproducible de lotes (borrador)
- PR #90: integración Top-3 (borrador)
- PR #91: notebooks de jurado y muestreo Gold (abierto, revisión pendiente)
- `proyecto_de_grado/scripts/auditar_lotes_jueces.py`: cruza IDs y splits cuando se aporten CSV. **Sus 7 pruebas sintéticas pasaron localmente**; aún no se ejecutó sobre los 18.000 y 519 reales.
- `proyecto_de_grado/docs/evidencia_anotacion_2700_claude_code_2026_11.md`, `proyecto_de_grado/docs/evidencia_jurado_calibracion_gold_2026_11.md`: relatos del equipo, todavía pendientes de corroboración con originales.

**Prohibido confundir:** «corrida documentada en notebook» con «salidas reproducidas»; «hojas preparadas» con «Gold anotado»; «acuerdo entre modelos» con «acierto frente a humanos»; «TF-IDF artículos desplegado» con «tesis C1/C2 desplegada».
