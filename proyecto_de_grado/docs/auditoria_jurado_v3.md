# Auditoría del jurado de pesos abiertos (v3)

Generado por `proyecto_de_grado/src/data/auditar_jurado.py` a partir de `data/jurado/v3/`. Son pre-etiquetas de modelos, no etiquetas humanas. Esa carpeta se publica con DVC al cerrar la anotación del Test Gold, porque trae el voto del jurado de esas citas y los anotadores trabajan a ciegas.

## Entradas (issue #93)

- `jurado_18000_v3.csv`: 18.000 filas, 18.000 identificadores únicos, 0 repetidos.
- Citas que no existen en `data/raw/contexts.json` (ACL-200): 0.
- Etiquetas del QLoRA fuera de las 11 opciones: 0.
- Voto recalculado con la regla de mayoría que no coincide con el CSV: 0; nivel de acuerdo que no coincide: 0.

| Juez | Modelo | Líneas | Repetidas | Faltan | Sobran | Etiqueta inválida | Distinta al CSV | Misma etiqueta en las 3 rotaciones |
|---|---|---|---|---|---|---|---|---|
| qwen | Qwen/Qwen2.5-7B-Instruct | 18.000 | 0 | 0 | 0 | 0 | 0 | 43,8% |
| llama | meta-llama/Llama-3.1-8B-Instruct | 18.000 | 0 | 0 | 0 | 0 | 0 | 41,4% |
| qlora | Qwen2.5-7B-Instruct + adaptador LoRA (columna del CSV) | | | | | | | |

Configuración registrada por el cuaderno en cada `juez_<juez>_v3_meta.json`:

- **qwen:** ninguna (bf16 completo), NVIDIA A100-SXM4-40GB, rotaciones [0, 4, 8], huella del prompt `79b7de672815`, 2026-11-03 22:47.
- **llama:** ninguna (bf16 completo), NVIDIA A100-SXM4-40GB, rotaciones [0, 4, 8], huella del prompt `79b7de672815`, 2026-11-03 21:56.

## Consenso (issue #94)

Regla: la etiqueta final es la que eligen al menos dos de los tres jueces. Si los tres eligen distinto, la cita queda **sin consenso** y no entra al dataset. Si el consenso es Ambiguo o No evaluable, tampoco entra.

- Tres de tres: 5.227 (29,0%). Dos de tres: 9.349 (51,9%). Las tres distintas: 3.424 (19,0%).
- κ de Fleiss entre los tres: 0,356.

| Pareja | Coinciden | κ de Cohen |
|---|---|---|
| qlora y qwen | 54,9% | 0,435 |
| qlora y llama | 34,9% | 0,265 |
| qwen y llama | 49,3% | 0,417 |

En las 9.349 citas de dos de tres, el juez que votó distinto fue: qlora 3.642, qwen 1.052, llama 4.655.

| Etiqueta | Voto final | De ellos 3 de 3 | Elegida por qlora | Elegida por qwen | Elegida por llama |
|---|---|---|---|---|---|
| Background | 4.786 | 1.449 | 7.489 | 5.469 | 1.718 |
| Gap | 995 | 272 | 752 | 1.886 | 1.262 |
| Basis | 382 | 34 | 749 | 896 | 1.061 |
| Comparison | 1.909 | 894 | 2.073 | 2.779 | 1.908 |
| Application | 3.104 | 1.868 | 4.489 | 3.086 | 2.838 |
| Improvement / Modification | 1.155 | 226 | 395 | 1.198 | 4.745 |
| Evidence | 2.009 | 394 | 967 | 2.479 | 3.830 |
| Identification of the Originator | 32 | 6 | 402 | 9 | 35 |
| Further Reading | 153 | 83 | 348 | 179 | 102 |
| Ambiguo | 45 | 1 | 317 | 10 | 500 |
| No evaluable | 6 | 0 | 19 | 9 | 1 |
| SIN_CONSENSO | 3.424 | 0 | 0 | 0 | 0 |

Parejas de etiquetas que más se confunden entre jueces (suma de las tres parejas de jueces):

- Background / Improvement / Modification: 3.389
- Background / Evidence: 3.308
- Application / Improvement / Modification: 2.192
- Background / Gap: 2.125
- Background / Comparison: 1.674
- Application / Evidence: 1.554
- Comparison / Improvement / Modification: 1.474
- Background / Basis: 1.424

Lectura:

- llama es el juez que más veces queda en minoría (49,8% de las citas de dos de tres). Elige Improvement / Modification 4.745 veces, frente a 1.155 en el voto final.
- Misma etiqueta en las tres rotaciones de las opciones: qwen 43,8%, llama 41,4%. Por debajo de 100 % significa que el orden de las opciones todavía influye en cada juez por separado.
- Parte de los votos que son tres de tres, por clase: mayor en Application (60,2%), Further Reading (54,2%), Comparison (46,8%); menor en Identification of the Originator (18,8%), Basis (8,9%).

Archivos de detalle (en `data/jurado/v3/auditoria/`): `desacuerdos_jurado_v3.csv` (las citas sin consenso con la etiqueta de cada juez) y `matrices_jueces_v3.csv` (matriz de confusión de cada pareja de jueces).
