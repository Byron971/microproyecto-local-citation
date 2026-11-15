# Cobertura y viabilidad de los datos (v1)

Generado por `proyecto_de_grado/src/data/cobertura_datos.py`. Responde los comentarios de la docente sobre la propuesta V3 (rúbricas 4 y 5) con el corpus completo como denominador. Las cifras sobre muestras se marcan como tales.

## 1. Fuentes y homologación

Se arma **un solo dataset**: ACL-200 aporta los contextos, los pares y las particiones; ACL OCL aporta el texto completo del mismo artículo, enlazado por el identificador de ACL Anthology. No se mezclan etiquetas de otros datasets por tener nombres parecidos.

| Fuente | Qué aporta | Unidad | Identificador | Licencia | Uso en el proyecto |
|---|---|---|---|---|---|
| ACL-200 (repositorio de Gu et al., 2022) | contextos con TARGETCIT, pares citante-citado, título y resumen, particiones | contexto de cita | context_id = citante_citado_n (IDs de ACL Anthology) | El repositorio no declara licencia; los textos son de ACL Anthology anteriores a 2016 (CC BY-NC-SA 3.0) | Única fuente de contextos y etiquetas |
| ACL OCL (Rohatgi et al., 2023) | texto completo con secciones de citantes y citados | artículo | mismo ID de ACL Anthology | MIT en Hugging Face; los artículos conservan CC BY-NC-SA 3.0 (antes de 2016) o CC BY 4.0 | Texto completo para el Top-3; se enlaza por ID, sin cambiar etiquetas |
| MultiCite (Lauscher et al., 2022) | intenciones de cita a nivel de oración | oración, varias etiquetas por cita | IDs de S2ORC | CC BY-NC 2.0 (derivado de S2ORC) | No se homologa: 7 intenciones con varias etiquetas por cita, no 9 funciones con una sola |
| unarXive (vía ID de arXiv) | texto completo de arXiv | artículo | ID de arXiv | No aplica: descartada | Descartada: como máximo cubre 1 de 500 pares |

Licencias verificadas el 2026-11-04 en aclanthology.org/faq/copyright, huggingface.co/datasets/WINGNUS/ACL-OCL y github.com/allenai/multicite. ILCiteR se usa solo como referencia metodológica y no se descarga.

**Versión de ACL-200 usada** (`data/raw`, versionada con DVC):

| Archivo | Filas | Bytes | SHA-256 |
|---|---|---|---|
| `contexts.json` | 63.768 | 39.444.198 | `4725714f53cd6e1f2efca883761dc252ac19be1489b699f4d14d1e7b9dcc3a73` |
| `papers.json` | 19.776 | 24.525.110 | `999d6b77fed44d6bb6ed1c49c532c02aaa19f21b9e6d65e569201c2a2c7ee749` |
| `train.json` | 30.390 | 2.096.914 | `62d670079b8ea1d4654d45d18c3a3e028a94732189acb54bc1b2350984ad9dae` |
| `val.json` | 9.381 | 647.289 | `86e7e475fdb30f212eedb9008124dee25c5a8432f6e8af7070c395a808a94326` |
| `test.json` | 9.585 | 661.365 | `12038ef4996fc73c046b7094d6cbbccb43e8b1b3fe102899f00b2a15200c6f6d` |

## 2. ¿Todos los contextos tienen su par?

Sobre los 63.768 contextos de ACL-200 y sus 19.776 artículos:

| Condición | Contextos | Parte del total |
|---|---|---|
| Traen la marca TARGETCIT | 63.768 | 100,0% |
| El citante está en los metadatos | 63.768 | 100,0% |
| El citado está en los metadatos | 63.768 | 100,0% |
| El citado tiene título y resumen | 63.768 | 100,0% |
| **Par completo para clasificar con título y resumen** | **63.768** | **100,0%** |

**Texto completo (ACL OCL).** Es una observación sobre una muestra, no una medición del corpus completo: en 500 contextos al azar (semilla 42, `docs/spike_enlace_datos/`) quedaron completos 411 pares (82,2%). Llevado al corpus, con un intervalo de confianza del 95 % (Wilson), se esperan entre 78,6% y 85,3%, es decir, entre 50.125–54.396 de los 63.768 contextos. Esa cifra solo se confirma al enlazar el corpus completo.

## 3. Particiones y fecha del artículo

ACL-200 no trae un campo de año: el año sale del identificador de ACL Anthology del citante (P15-1122 es de 2015). Por eso se contrastó contra las listas oficiales `train.json`, `val.json` y `test.json`.

| Partición oficial | Años | Contextos | Con año fuera de su rango |
|---|---|---|---|
| train | 2009–2013 | 30.390 | 0 |
| val | 2014 | 9.381 | 0 |
| test | 2015 | 9.585 | 0 |

Fuera de las tres particiones quedan 14.412 contextos (2000-2008 12.010, 2009-2013 329, 2014 148, antes_de_2000 1.925). Están en `contexts.json`, pero no en las listas oficiales.

| Cruce | Citantes compartidos | Citados compartidos | Pares citante-citado compartidos |
|---|---|---|---|
| train-val | 0 | 1.518 | 0 |
| train-test | 0 | 1.338 | 0 |
| val-test | 0 | 1.305 | 0 |

Ningún artículo citante ni ningún par se repite entre particiones, así que no hay fuga por documento. Que un artículo citado aparezca en varias particiones es normal (los artículos muy citados) y no es fuga, pero se mide: de las 1.533 citas del Test Gold, 829 (54,1%) tienen un citado que también aparece en entrenamiento. Los resultados se pueden reportar aparte para citados vistos y no vistos.

**Textos duplicados:** 1.434 textos de contexto aparecen con más de un identificador (3.139 contextos). En 1.282 de esos grupos el citante es el mismo: es una frase que cita varios trabajos a la vez, y cada trabajo citado cuenta como una cita aparte. 7 grupos cruzan particiones: son textos que se repiten en artículos de años distintos. Citas del Test Gold con un texto idéntico en entrenamiento o validación: 0. Citas del Test Gold con un texto idéntico fuera de la partición de prueba que hoy no está en el dataset: 1 (`W15-3019_P11-1083_2`): si el dataset se amplía, su gemelo debe quedar fuera.

**Concentración por artículo citante:**

| Conjunto | Contextos | Artículos citantes | Mediana por artículo | Máximo | Parte del 10 % de artículos con más citas |
|---|---|---|---|---|---|
| train | 30.390 | 5.182 | 4 | 49 | 32,8% |
| val | 9.381 | 1.406 | 5 | 55 | 32,4% |
| test | 9.585 | 1.468 | 5 | 67 | 31,3% |
| Entrenamiento del dataset v1 | 9.893 | 5.192 | 1 | 13 | 27,5% |

## 4. ¿Las 18.000 citas del jurado son una muestra al azar?

Las 2.700 citas con que se ajustó el QLoRA no pueden entrar al jurado, porque ese modelo ya las vio. Si las 18.000 se tomaron al azar entre las demás, cada partición debería aportar en proporción a su tamaño.

| Partición | Población (sin las 2.700) | Observado | Esperado al azar |
|---|---|---|---|
| sin_particion | 14.412 | 4.258 | 4.248 |
| test | 9.585 | 2.794 | 2.825 |
| train | 27.690 | 8.150 | 8.162 |
| val | 9.381 | 2.798 | 2.765 |

Prueba ji cuadrado: χ² = 0.78 con 3 grados de libertad, p = 0.85. Citas de la muestra que están entre las 2.700: 0. La distribución es compatible con una muestra al azar, aunque una prueba así no lo demuestra: la forma de escogerlas debe quedar documentada por quien las tomó.

## 5. ¿Se llega a 2.000 citas por clase?

Proyección si las 61.068 citas posibles de ACL-200 pasaran por el mismo jurado, con la proporción de cada clase en las 18.000 (intervalo del 95 %). Supone que la muestra es al azar (sección 4) y que el jurado se comporta igual en el resto. Incluye las citas de 2015, de donde sale el Test Gold.

| Clase | Con consenso en la muestra | Proyección en ACL-200 | Intervalo 95 % | ¿Alcanza 2.000? |
|---|---|---|---|---|
| Background | 4.786 | 16.237 | 15.846–16.634 | sí |
| Gap | 995 | 3.376 | 3.178–3.585 | sí |
| Basis | 382 | 1.296 | 1.174–1.431 | no |
| Comparison | 1.909 | 6.477 | 6.207–6.756 | sí |
| Application | 3.104 | 10.531 | 10.198–10.872 | sí |
| Improvement / Modification | 1.155 | 3.919 | 3.706–4.143 | sí |
| Evidence | 2.009 | 6.816 | 6.540–7.102 | sí |
| Identification of the Originator | 32 | 109 | 77–153 | no |
| Further Reading | 153 | 519 | 443–608 | no |

**Lectura:** con todo ACL-200 llegarían a 2.000 6 clases (Background, Gap, Comparison, Application, Improvement / Modification, Evidence). 3 no llegarían ni en el mejor caso (Basis, Identification of the Originator, Further Reading). El conteo actual por clase y la brecha están en `docs/dataset_funciones_v1.md`.

**Plan de expansión, sin duplicar ni fabricar citas:**

1. Pasar por el mismo jurado las citas de ACL-200 que todavía no lo han pasado. Las 2.700 del QLoRA necesitan otro tercer juez, porque ese modelo ya las vio.
2. Para las clases que no llegan ni con todo ACL-200: extraer contextos nuevos de la bibliografía enlazada de ACL OCL (fuera de ACL-200), con el mismo jurado y las mismas reglas. Antes hay que medir cuántos salen. Como sugirió el experto, con los ejemplos que ya tiene cada clase escasa (unos 50 a 200) se puede entrenar un clasificador sencillo que señale candidatos, y pasar al jurado solo esos candidatos. Eso abarata la búsqueda, pero no aumenta las citas que existen: el clasificador propone y el jurado decide.
3. No completar clases repitiendo citas ni generándolas con modelos. Si una clase no llega, se reporta la brecha y se evalúa con F1 macro y por clase, sin esconderla.

Pasos 1 y 2 son una decisión del equipo (tiempo de GPU y fecha de congelamiento).

## 6. Etiquetas de modelos frente a etiquetas humanas

| Conjunto | Citas | Quién etiquetó | ¿Cuenta como humano? |
|---|---|---|---|
| Entrenamiento del QLoRA | 2.700 (2.642 evaluables, 51 ambiguas, 7 no evaluables) | Claude Haiku 5.5 | No |
| Jurado | 18.000 | QLoRA, Qwen 2.5 7B y Llama 3.1 8B | No |
| Test Gold | 1.533 | Dos personas del equipo por cita | Sí, cuando termine la anotación |

Las 2.700 de Claude Haiku son pre-etiquetas de un modelo, no revisiones humanas. Solo el Test Gold decide la evaluación.

## 7. Frente a los comentarios de la docente

| Comentario | Respuesta | Dónde |
|---|---|---|
| ¿Un solo dataset o comparar formas de extraer contextos? | Un solo dataset: ACL-200 más el texto de ACL OCL por ID; MultiCite no se homologa | Sección 1 |
| Falta describir el dataset | Archivos, huellas, filas, pares y concentración sobre el corpus completo | Secciones 1 a 3 |
| ¿Todos los contextos tienen su par? | 100,0% con título y resumen; texto completo estimado en 78,6%–85,3% | Sección 2 |
| ¿Qué se tiene en cuenta en el split? ¿Cuándo se escribió el artículo? | Particiones oficiales por año del citante, contrastadas contra las listas; sin citantes ni pares compartidos | Sección 3 |
| ¿Se llega a la meta con los datos actuales? | No en todas: 3 de 9 clases no llegan ni con todo ACL-200 | Sección 5 |
| ¿Plan si los datos no alcanzan? | Jurado sobre el resto de ACL-200, luego ACL OCL, y brecha reportada sin fabricar citas | Sección 5 |

## 8. Cómo reproducirlo

1. `dvc pull data/raw` (remoto público, sin credenciales).
2. Correr el comando del encabezado del script. Las pruebas están en `proyecto_de_grado/tests/test_cobertura_datos.py`.
3. El jurado (`data/jurado/`) se publica al cerrar la anotación del Test Gold; sin él no se puede rehacer la sección 4 ni la 5.
