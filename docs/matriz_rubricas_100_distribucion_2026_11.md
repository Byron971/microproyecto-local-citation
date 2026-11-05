# Plan de cierre de rúbricas y distribución de issues — 4 de noviembre de 2026

Estado: **auditoría de evidencias y hoja de ruta**, no certificación de entrega.  
Repo: https://github.com/Byron971/microproyecto-local-citation  
Revisión de docente: `proyecto_de_grado/docs/retroalimentacion_propuesta_V3.md` (rama `feature/s2-5-homologacion-fuentes`).  
Control de integración: #111 y PR #89–#92.

## Advertencias: cuatro entregables, cuatro rúbricas diferentes
1. **Informe de avance (8 páginas)**. Rúbrica exacta en *Estructuración de informe para despliegue de soluciones.docx*: propuesta 10, datos 15, construcción 35, resultados 10, análisis 20, referencias 5, presentación/redacción 5.
2. **Artículo científico final (máximo 12 páginas conforme a instrucciones del curso recopiladas en #112 y #115)**. Rúbrica interna de #112: problema 10, estado del arte 10, metodología 30, resultados 15, discusión 15, conclusiones 10, calidad editorial 10. Resumen 200–300 palabras, 3–5 palabras clave, autoría y afiliaciones, citas verificables; formato papel carta, TNR 10, márgenes 2,5 cm, sencillo, justificado, figuras/tablas numeradas y citadas en texto.
3. **Despliegue y demostrador**. Rúbrica de #116–#119: funcionamiento/inferencia 35, README/reproducibilidad 15, parametrización 15, interfaz/explicabilidad 35. Requiere URL verdaderamente accesible y documento con enlace, no solo Docker local.
4. **Sustentación**. Rúbrica de #120–#123: relato problema–solución 30, resultados+demo 25, diseño/coherencia 20, comunicación oral 15, manejo del tiempo 10. Ensayar la sesión real y preguntas.

**No sumar porcentajes de una rúbrica a otra ni confundir el antiguo microproyecto (TF-IDF ranking de papers) con recuperación local de fragmentos del artículo citado.**

## Cambios exigidos por Haydemar: propuesta V3 obtuvo 86/100
- **Datos 11/20 (−9):** documentar resolución de pares, cobertura real, splits por año del *citante*, viabilidad de 2.000 ejemplos de cada una de nueve clases, expansión si faltan. Issue #125.
- **Metodología 12/15 (−3):** homologación entre ACL-200/ACL OCL y otras fuentes sin confundir unidades ni licencias; ablación de sección como predictor espurio, incluida sección barajada. Issues #125 y #128.
- **Evaluación 8/10 (−2):** definir Gold humano por (contexto, chunk) y fórmulas denominadas Hit@3/Recall@3/MRR@3 (no es Gold de papers). Issue #127.
- **Objetivos 10/10 con observación:** un solo verbo principal por objetivo. **Verificar en el artículo final #112**; el informe de avance #126 fue entregado el 25-oct según el equipo y solo requiere reentrega si Haydemar la solicita.
- Problemática, estado del arte y ética bien evaluados en V3 no eximen actualizar fuentes ni someter a nueva revisión.

## Hallazgos críticos según archivos/PR inspeccionados (NO confundir con métricas finales)
| Hallazgo | Evidencia documental | Bloqueo / tarea |
|---|---|---|
| Jurado 18.000 citas, 14.525 con etiquetas válidas, 3.424 sin mayoría y 51 ambiguos/no evaluables; cuadrar denominadores | #111, PR #91 | #93, #94, #95 |
| Falta balance en Gap 1.005, Basis 1.618, Comparison 91, Improvement/Modification 845, Originator 1.968, Further Reading 1.847; faltante conjunto 7.374 | `dataset_funciones_v1.md`, PR #91 | #95, #125; no afirmar 18.000 balanceadas |
| Gold propuesto de 519+441+573=1.533 (8,52% de 18.000). Mínimo humano 15% de 18.000 sería 2.700, sin confundirse con hoja de 2.700 **preetiquetada** | PR #91 y #92, #111, propuesta | #97–#100 y #127; reconciliar un solo Gold canónico |
| PR #91 y #92 proponen manifiestos Gold distintos, muchos archivos aún sin certificación humana; no usar materiales antiguos | #111 | #100, #111 |
| **A4 requiere SciBERT Y SPECTER**, ambos con entrada **A (contexto+título/abstract)** y **B (contexto+Top-3/sección)**. Fuentes Haiku/jurado son un **tercer factor separado**, no nombres A/B. Requiere controles de sección | Propuesta A4, #103, comentario docente | #103, #104, #128; no declarar SPECTER ejecutado sin checkpoint/pruebas |
| Baseline BM25 en PR #90 (pendiente en main) y módulo denso SciBERT S2.8 en rama de investigación; no equivalen a servicio final integrado | PR #84, #90, módulos SciBERT | #101, #102, #107, #116 |
| Código de `gold_policy.py` en main advierte que el piloto de 20 casos no es Gold final y que pasar checks de forma no certifica anotación | `src/evaluation/commercial/gold_policy.py` | #98–#100, #109 |
| No hay evidencia verificada aquí de benchmark final F1 sobre Gold adjudicado, Top-3 Recall/MRR con juicio humano ni URL externa real | #111, archivos revisados | #110, #116, #119, #127 |
| La propuesta exige validación humana del 15% y no overlap por documentos/par; algunos controles de split están en ramas, sin integración final | propuesta y #111 | #96, #100, #109 |
| Reproducibilidad de QLoRA, parámetros, dependencia GPU, huellas/modelos/prompt Haiku y 595 exclusiones antiguas pendientes de auditoría | PR #89–#92, #111 | #93, #104, #111 |

## Distribución de 35 issues por responsable principal (7 por persona)
El responsable coordina entrega y PR, pero las revisiones y anotaciones se realizan entre varios. Los 31 issues #93–#123 se conservaron; se añadieron #125–#128 para cerrar huecos. El PR #124 no es issue.

| Integrante | Issues (7) | Enfoque |
|---|---|---|
| John Byron Arias Sanz @Byron971 | #109 #110 #111 #112 #116 #118 #119 | protocolo/benchmark, merge y PR, artículo final, API/seguridad/QA |
| Carlos Alfredo Caicedo Bermúdez @CaicedoBz | #93 #94 #95 #96 #120 #125 #126 | jurado/dataset/anti-leakage, fuente y viabilidad, avance de 8 páginas, relato |
| José María Zambrana Arze @josezambrana | #97 #98 #99 #100 #114 #123 #127 | Gold de clases, Gold de chunks, acuerdo humano, discusión y ensayos |
| Carlos Eduardo Duque Lugo @CarlosEdDL | #101 #102 #103 #104 #106 #113 #128 | SciBERT recuperación y clasificador, eficiencia, metodología y ablations |
| Gabriel Gustavo Pinzón Páez **@guspi123** (permiso actual `read`) | #105 #107 #108 #115 #117 #121 #122 | APIs comerciales, interfaz, referencias/IA, formato, README, demo y diseño; requiere `write` y asignación técnica |

**Asignación técnica real (5-nov):** las cuatro cuentas verificadas inicialmente aparecen como `assignees`. Gabriel confirmó `@guspi123`, pero el repositorio muestra permiso **`read`**, no `write`, y los siete issues no lo muestran como `assignee`. Se registró su usuario y trabajo en #105, #107, #108, #115, #117, #121 y #122. **Acción administrativa pendiente:** elevar a `write`, volver a asignar y actualizar `.github/CODEOWNERS` para que su aprobación sea válida como code owner. Hasta entonces no afirmar completada la asignación. 

**Advertencia de equidad:** siete issues por integrante no implican idénticas horas. Revisar horas de anotación humana, experimentos GPU, implementación y edición en la reunión de equipo. Los cinco deben contribuir con evidencia de commits/PR; José no debe etiquetar en solitario 2.700 casos ni todos los chunks.

## Matriz de trazabilidad del informe de avance (8 páginas)
| Rubro (pts) | Evidencia que debe estar en las 8 páginas | Issues | Estado actual |
|---|---|---|---|
| Problema/propuesta 10 | objetivo claro y una tarea de recuperación + una de nueve clases | #120 #126 | redacción por verificar |
| Datos 15 | origen/versiones/licencias, limpieza, 18.000 y desglose de clases, 15% humano, anti-leakage | #93–#100 #125 | **brechas P0** |
| Metodología 35 | modelo, diagrama, hiperparámetros/experimentos, dos factores separados, infraestructura real | #101–#109 #113 #128 | parcial; A/B no final |
| Resultados 10 | matrices, F1 Macro/Micro/por clase, recuperación Top-3 humana, denominadores | #102 #110 #127 | **Gold pendiente** |
| Análisis 20 | errores por clase, sesgo de sección, déficit clases, riesgos, planes de mitigación | #106 #111 #114 #128 | parcial |
| Referencias 5 | trabajos recientes, citas verificables, datos/modelos | #108 | revisar |
| Presentación 5 | no más de 8 páginas, tablas legibles, corrector y anexos vía link | #115 #126 | preparar |

No marcar cumplimiento basado en documentos vacíos, un PR abierto, notebooks sin outputs o métricas sobre el piloto.

## Matriz del artículo (hasta 12 páginas)
| Rubro (pts) | Evidencia y puntos de control | Issues |
|---|---|---|
| Problema 10 | contexto, pregunta, contribución verificable y objetivo de una acción | #112 #120 |
| Estado del arte 10 | revisión crítica reciente, comparación de métodos y referencias de origen | #108 |
| Metodología 30 | arquitectura, corpus, anotación, jurado, **SciBERT y SPECTER A/B**, origen etiquetas separado, modelos comerciales, despliegue | #93–#109 #113 #125 #127 #128 |
| Resultados 15 | F1 por clase/Macro/Micro, confusión, BM25 vs SciBERT con Gold, costo y latencia | #102 #106 #110 #127 |
| Discusión 15 | error analysis, sesgos, falsos acuerdos, limitaciones y amenazas a validez | #111 #114 #128 |
| Conclusiones 10 | responde objetivos con cifras soportadas y trabajo futuro factible | #112 #114 |
| Calidad 10 | formato, máximo 12, abstract 200–300 palabras, **un verbo principal por objetivo**, referencias/IA explícitas (el equipo reporta 0/5 en el avance), tablas | #108 #115 #112 |

## Matriz del despliegue y sustentación
- **35/100 funcionamiento:** #107 #116 #119 — endpoint real, modelo real, URL accesible desde fuera y fallos controlados.
- **15/100 reproducibilidad:** #117 — README ejecutado desde clon limpio, pesos externos con hash.
- **15/100 parametrización:** #118 — configuración sin secretos, CPU/GPU, timeout/rutas; pruebas.
- **35/100 UX:** #107 #121 — Top-3, sección, clase y confianza solo cuando sea legítima; no prometer 'probabilidad' si hay solo score no calibrado.
- **Sustentación 30+25+20+15+10:** #120–#123 — relato, demo y datos finales, diseño, oralidad, tiempo.

## Puertas de calidad y orden
**P0 / obligatorio antes de presentar resultados finales:** resolver diferencias PR #91/#92, balance real o justificar incumplimiento, guía de doble anotación, Gold canónico de 9 funciones, Gold de chunks, splits limpios y datasets con hash.  
**P1 / evidencia experimental:** implementar y validar SciBERT-A/B y **SPECTER-A/B** (enunciado A4), comparación independiente Haiku/jurado y ablaciones de sección; benchmark sobre mismo Gold, métricas/semillas/latencia/recursos.  
**P2 / integración:** API + interfaz verdaderamente operativa y documentada, Docker/CI, entregable de enlaces verificables.  
**P3 / publicación:** informe avance 8 páginas, artículo 12 páginas, sustentación ensayada; cada tabla y afirmación vinculada a archivo, commit, run y responsable.

## Checklist de control final (revisión cruzada cinco autores)
- [ ] Ninguna cifra con origen ambiguo (18.000, 14.525, 2.700, 1.533, 519, 2.642/2.700 Haiku).
- [ ] Cada figura/tabla tiene fuente, split, unidad, N y fecha/versión cuando aplica.
- [ ] Objetivos utilizan un verbo principal; discusión de sección verdadera/barajada y homologación explícita.
- [ ] Entrenamiento y selección de prompts sin contacto con Gold final; manifestos anti-leakage.
- [ ] El 15% humano de dataset final **se demuestra**, no se confunde con preetiquetas IA.
- [ ] Datos raros no se duplican para completar 2.000 artificialmente.
- [ ] Se informa comparabilidad de los modelos, soporte por clase y límites computacionales.
- [ ] Informe 8 pág y artículo 12 pág verificados por separado.
- [ ] URL externa probado, README reproducido, servicios parametrizados y evidencia de demo.
- [ ] Los cinco poseen aportes verificables y revisan sus secciones; no fusionar por aprobación implícita.

## Riesgo residual
La rúbrica y la asignación están cubiertas en el **plan**, pero alcanzar 100 depende de resultados reales, cumplimiento de muestra humana, calidad de experimentos, revisión docente y funcionamiento observable. Este documento no declara cumplimiento ni sustituye evaluación académica.

## Coordinación del equipo (5-nov-2026)
- **PR #134** del responsable Caicedo corresponde a #125: cobertura del corpus y respuestas a Haydemar. Está abierto, **no duplicar el informe**; revisar evidencia y pruebas antes de cerrar #125.
- **Issue #126:** el equipo afirma entrega el 25-oct. Solicitar comprobante y confirmar si se pide reentrega; si no, cerrarlo como histórico y concentrar correcciones de objetivos en #112.
- **A4:** el #103 asignado a @CarlosEdDL debe contener cuatro corridas SciBERT/SPECTER × entrada A/B; no confundir esta matriz con la fuente Haiku/Jurado.
- **Puntos vulnerables de Gabriel:** #105 comerciales zero/few-shot; #108 referencias y declaración de IA (0/5 reportado por equipo); #107 y #121 selector de modelos real en demo. La cuenta @guspi123 debe adquirir permiso write antes de ser CODEOWNER.
