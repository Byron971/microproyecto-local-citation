# Cuadernos del proyecto de grado

Cuadernos de Google Colab para construir el dataset de funciones de cita: el pre-etiquetado con un jurado de modelos de pesos abiertos (actividad A2 del enunciado) y la preparación de la anotación humana del Test Gold (actividad A3). Leen y escriben en Google Drive; los resultados no se versionan en Git porque son datos.

| Cuaderno | Qué hace | Estado |
|---|---|---|
| `jueces_open_weight.ipynb` | Jurado de jueces de pesos abiertos sobre las 18.000 citas (versión v3) | Vigente |
| `jueces_llama_mistral_v1.ipynb` | Primera versión del jurado y su diagnóstico | Descartada; se conserva como evidencia |
| `anotacion_test_gold.ipynb` | Muestreo de la calibración y de las tandas del Test Gold, traducción de apoyo y hojas por anotador | Vigente |

## `jueces_open_weight.ipynb`: jurado de pesos abiertos

Tres jueces clasifican cada cita en una de las 9 funciones (más Ambiguo y No evaluable) y votan; la etiqueta final es la que eligen al menos dos.

- **Jueces:** Qwen 2.5 7B ajustado con QLoRA (columna del archivo `ANOTACION_18000_CITAS_REALES_QLORA.csv`), `Qwen/Qwen2.5-7B-Instruct` y `meta-llama/Llama-3.1-8B-Instruct`, estos dos sin ajuste (zero-shot).
- **Prompt:** definiciones y reglas de desempate de `docs/guia_anotacion_funcion_cita.md`, con la respuesta iniciada en `Answer:`. Se leen las probabilidades de las 11 letras en una sola pasada.
- **Sesgo de posición:** cada cita se clasifica con tres rotaciones de las opciones (0, 4 y 8) y se promedian las probabilidades, para que ninguna clase quede siempre en la misma letra.
- **Entorno:** Colab con A100; modelos completos en bf16 (en GPU de menos de 30 GB se cuantizan a 4 bits).
- **Entrada y salida (Drive, carpeta `jueces/`):** `ANOTACION_18000_CITAS_REALES_QLORA.csv` → `juez_<juez>_v3.jsonl`, `juez_<juez>_v3_meta.json` y `jurado_18000_v3.csv`.

### Cómo se escogió el jurado

Prueba con las mismas 200 citas, comparada contra dos referencias de desarrollo (Claude Sonnet 5.5 y GPT-6.1 Sol, que coinciden entre sí en 82 %, κ = 0,757). Las referencias solo sirvieron para escoger el método; no son etiquetas humanas.

| Modelo | Acierto contra el consenso de las referencias (164 citas) |
|---|---|
| QLoRA (Qwen 2.5 7B ajustado) | 77 % |
| Qwen 2.5 7B | 65 % |
| Llama 3.1 8B | 43 % |
| Granite 4.2 8B | 24 % (descartado) |
| OLMo 3 7B | 18 % (descartado) |
| Mistral 7B v0.3 | 12 % (descartado) |

Con el jurado QLoRA + Qwen + Llama, cuando los tres coinciden el acierto es 93 % (55 citas) y cuando coinciden dos, 71 % (82 citas).

### Resultado sobre las 18.000 citas

κ de Fleiss entre los tres jueces: 0,356. Tres de tres de acuerdo: 5.227 citas; dos de tres: 9.349; sin consenso: 3.424 (fuera del dataset). Votos: Background 4.786, Application 3.104, Evidence 2.009, Comparison 1.909, Improvement / Modification 1.155, Gap 995, Basis 382, Further Reading 153, Identification of the Originator 32.

### Historia de versiones

1. **v1** (`jueces_llama_mistral_v1.ipynb`): Llama 3.1 8B y Mistral 7B con definiciones cortas y un solo orden de opciones. κ de Fleiss −0,014 con el QLoRA. El diagnóstico mostró que Llama elegía por posición (al invertir las opciones cambiaba de etiqueta en 15 de 22 citas) y que Mistral asignaba casi todo a Comparison o Evidence.
2. **v2:** reglas de la guía, prefijo `Answer:`, Qwen como tercer juez y dos órdenes (normal e invertido). κ 0,224, pero con 11 opciones la del centro (Improvement / Modification) no cambia de letra al invertir y acaparó el voto.
3. **v3:** tres rotaciones y modelos completos en bf16. Es la versión vigente.

## `anotacion_test_gold.ipynb`: anotación humana

Prepara el trabajo de los cinco anotadores del equipo.

- **Calibración 3:** 20 citas de 2014 (partición val), dos por clase y tres sin consenso, iguales para todos.
- **Test Gold:** citas de 2015 (partición test), al azar por clase según el voto del jurado, en tres tandas fijadas desde el inicio: 519 (tope de 500 por clase), 441 (tope de 1.000) y 573 (tope de 2.000), en total 1.533. Cada cita la anota una pareja; con cinco personas hay diez parejas.
- **A ciegas:** las hojas no muestran la etiqueta de ningún modelo. `clave_coordinador_v2.csv` guarda el voto del jurado y no se comparte con los anotadores.
- **Versiones de las hojas:** el nombre lleva la versión (`TestGold_T1_v2_<Apellido>.xlsx`). La v1 se repartió el 3-nov a las 7:43 p. m.; la v2 reemplazó dos citas por las exclusiones posteriores y es la vigente.
- **Exclusiones:** citas del taller de práctica y de las calibraciones anteriores (`../anotacion/`), las 200 citas con las que se escogió el jurado, y las exclusiones agregadas después (`ids_piloto_historico_no_test_final.txt` y G1.1), que se reemplazaron en la misma posición sin rehacer el orden.
- **Traducción de apoyo:** contexto, título y resumen traducidos al español con GPT-6.1 Sol, verificando que se conserven las marcas TARGETCIT y OTHERCIT. Se decide con el texto original en inglés.
- **Hojas:** una por anotador, con listas desplegables, estado de avance, guía rápida, definiciones de las 9 funciones y 41 ejemplos explicados del taller.
- **Reproducible:** semilla 2026; con los mismos archivos de entrada se obtiene la misma asignación.

## Requisitos para correrlos

- Google Colab (los jueces necesitan GPU; la anotación no).
- Secretos de Colab: `HF_TOKEN` (licencia de Llama aceptada en Hugging Face) y, para las referencias y la traducción, `ANTHROPIC_API_KEY` y `OPENAI_API_KEY`. Las llaves nunca se escriben en las celdas.
- En Drive, carpeta `proyecto_grado/jueces/`: `ANOTACION_18000_CITAS_REALES_QLORA.csv` (y `jurado_18000_v3.csv` para la anotación).
