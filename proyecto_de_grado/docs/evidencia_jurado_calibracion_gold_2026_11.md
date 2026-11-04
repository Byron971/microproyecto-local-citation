# Evidencia comunicada: jurado open-weight, calibración 3 y Test Gold

Corte de información del equipo: 3 de noviembre de 2026. Procedencia: mensajes de Carlos C. **Estado: informado, no verificado todavía con los archivos originales de SharePoint.**

## Jurado sobre lote de 18.000

- Jurado definitivo comunicado: **QLoRA, Qwen 2.5 7B y Llama 3.1 8B**.
- Modelos evaluados y descartados: Mistral 7B, Granite 8B y OLMo 7B, según el responsable por bajo desempeño. No hay métricas completas, criterios de descarte ni predicciones aportadas en esta auditoría.
- Referencias comerciales comunicadas: **Sonnet y GPT**; solicitar IDs exactos, snapshots, prompts, temperatura, conteos y huellas de predicciones.
- **93 %** es el acuerdo/acierto comunicado **condicionado a que los tres jueces coincidan**, contra esas referencias. Falta cobertura del consenso, definición operativa de la referencia, tamaño de muestra, intervalo y desacuerdos; no es automáticamente accuracy global ni Gold humano.
- Los 18.000 siguen sin manifiesto verificable de selección. No confundir el conjunto propuesto de 18.000 con cobertura por clase demostrada.

## Ronda humana y Gold nuevo

- **Calibración 3:** 20 citas de **2014**, según mensaje del equipo. Se solicita que cada integrante termine su anotación individual el **4 de noviembre de 2026** y que los desacuerdos se examinen antes de pasar al test.
- **Tanda 1 de Test Gold:** se han **preparado/distribuido** 519 citas de **2015**, con asignación comunicada de alrededor de 208 por integrante en parejas. Aún **no** equivalen a un test adjudicado, sellado ni validado; comprobar context_id, asignación real, doble anotación ciega, ausencias, excluidos históricos, hoja guía y resguardo frente a modelos/predicciones.
- El equipo indica que usó las listas nuevas de exclusión y dejó **595 ejemplos anteriores a 2000 fuera del Test Gold**. Esto no implica por sí mismo que esas citas no pertenezcan al **train**: el split ACL-200 depende del año del **citante**, no del citado. Mantener ambas preguntas separadas y auditar sus IDs.
- **Taxonomía para Gold:** usar `docs/guia_anotacion_funcion_cita.md` del repositorio. No usar etiquetas automáticas o decisiones del compañero durante la anotación ciega.

## Alerta crítica de cambio de definición: Basis / Evidence

Se comunicó que la hoja `Guia` del Excel usado para Haiku define **Basis** como *«fundamenta una afirmación o premisa»*, interpretación que se solapa con **Evidence**. La guía versionada del repositorio dice:

- **Basis:** *«el trabajo citado constituye una base intelectual o conceptual directa de la investigación actual y la propuesta se construye sobre ese trabajo»*.
- **Evidence:** *«la cita respalda una afirmación, hipótesis, decisión metodológica, dato o interpretación concreta del texto citante»*.

**Riesgo:** QLoRA aprendió de etiquetas de un Excel con posible conflicto taxonómico; SciBERT C1 también se entrenó con 2.642 anotaciones utilizables provenientes del mismo lote inicial de 2.700. Ambos pueden transportar ese ruido/deriva. Esto no prueba la magnitud del error: medir matriz de confusión Basis/Evidence, reanotación humana ciega de una muestra y documentar cómo se aplican las definiciones. **No reescribir silenciosamente** etiquetas históricas ni ajustarlas mirando Test Gold.

## Respuesta sobre SciBERT C1

- Origen de etiquetas: lote original de 2.700 anotaciones generadas con Claude Code/Sonnet 5.5 y subagentes Haiku 5.5, **no etiquetas humanas Gold**.
- De ese lote se usaron **2.642** registros con etiqueta de función; **58** quedaron fuera de ese entrenamiento como no evaluables/no clasificados según consolidación local.
- Partición **de desarrollo** dentro del train original ACL-200: 2.115 para entrenamiento y 527 para validación, separando citantes y contextos.
- Comparaciones medidas sobre ese mismo desarrollo: TF-IDF + Logistic Regression F1 Macro 0,2367; SciBERT C1 F1 Macro aproximadamente 0,5240, accuracy aproximadamente 0,7685. **Estas no son métricas Gold final**.
- Próximo experimento correcto: congelar Gold humano independiente; evaluar C1 vigente sin modificarlo; entrenar otra variante con predicciones del jurado **solo de train**, separando candidatos, confianza, cobertura y procedencia. Comparar A vs B sobre el **mismo Test Gold sellado**, sin usarlo para ajustar ninguno.

## Insumos que faltan para marcarlo como verificado

1. Archivos de calibración 3 de 2014 y asignaciones de la tanda Gold 519 de 2015, con IDs y datos de doble anotación/adjudicación, descargados de SharePoint.
2. Listado de 595 IDs y denominador/filtro usado para excluirlos, así como lista exacta de exclusiones de John.
3. Lote de 18.000 IDs y script de selección, predicciones del jurado y manifiesto de ejecución.
4. Excel original de 2.700 con hoja `Guia`, CSV generado y snapshot de prompts de subagentes.
5. Artefactos QLoRA y registro de entrenamiento de Carlos Duque.

**Este documento registra decisiones declaradas; no declara que los 519 casos ya tengan anotaciones definitivas ni que el 93 % sea accuracy Gold.**
