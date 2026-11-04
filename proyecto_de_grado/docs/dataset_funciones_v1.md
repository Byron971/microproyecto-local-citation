# Dataset de funciones de cita v1

Generado por `proyecto_de_grado/src/data/curar_dataset_funciones.py`. La etiqueta es el voto del jurado (al menos dos de tres jueces); no se cambió ninguna etiqueta ni se completó ninguna clase. El archivo por cita es `data/dataset_funciones/v1/dataset_funciones_v1.csv` (DVC). En las citas del Test Gold y de la calibración la etiqueta del jurado va vacía, porque las anotan personas a ciegas; su etiqueta final será la humana.

## Uso de cada cita

| Uso | Citas | Qué significa |
|---|---|---|
| entrenamiento | 9.893 | train oficial de ACL-200 o fuera de partición con citante de 2013 o antes |
| validacion | 2.331 | partición val (2014) |
| test_gold_t1 | 519 | tanda 1 del Test Gold (anotación humana en curso) |
| test_gold_t2 | 441 | tanda 2 del Test Gold (escogida, sin repartir) |
| test_gold_t3 | 573 | tanda 3 del Test Gold (escogida, sin repartir) |
| reserva_test | 751 | partición test fuera del Test Gold: no se usa para entrenar |
| calibracion | 20 | calibración 3 (opcional) |
| excluida_sin_consenso | 3.421 | los tres jueces eligieron distinto |
| excluida_ambigua | 51 | consenso en Ambiguo o No evaluable |

## Citas por clase y brecha frente a 2.000

| Clase | Con consenso | 3 de 3 | Entrenamiento | (fuera de partición) | Validación | Test Gold (3 tandas) | Reserva test | Faltan para 2.000 |
|---|---|---|---|---|---|---|---|---|
| Background | 4.786 | 1.449 | 3.167 | 990 | 810 | 300 | 507 | 0 |
| Gap | 995 | 272 | 671 | 247 | 180 | 141 | 1 | 1.005 |
| Basis | 382 | 34 | 286 | 144 | 49 | 44 | 1 | 1.618 |
| Comparison | 1.909 | 894 | 1.306 | 468 | 303 | 286 | 12 | 91 |
| Application | 3.104 | 1.868 | 2.093 | 603 | 490 | 300 | 219 | 0 |
| Improvement / Modification | 1.155 | 226 | 807 | 241 | 189 | 151 | 6 | 845 |
| Evidence | 2.009 | 394 | 1.425 | 557 | 293 | 286 | 3 | 0 |
| Identification of the Originator | 32 | 6 | 25 | 15 | 0 | 5 | 1 | 1.968 |
| Further Reading | 153 | 83 | 113 | 48 | 17 | 20 | 1 | 1.847 |

**Clases por debajo de 2.000:** 6 de 9 (Gap, Basis, Comparison, Improvement / Modification, Identification of the Originator, Further Reading).

**Citas de ACL-200 que todavía no pasaron por el jurado:** 45.768 (train 22.240, val 6.583, test 6.791, fuera de partición 10.154). Pasar por el mismo jurado las que no son de test acercaría las clases escasas a 2.000 sin cambiar el método. El PR #92 ya trae un cuaderno que las clasifica con el QLoRA; faltarían Qwen y Llama. En las 2.700 con que se entrenó el QLoRA, ese modelo no puede ser juez porque ya las vio. Es una decisión del equipo.

## Controles

- Artículos citantes compartidos entre entrenamiento/validación y el Test Gold: 0.
- Pares citante-citado compartidos: 0. Citas compartidas: 0.
- Citas de la prueba de 200 con que se escogió el jurado: 200 (columna `prueba_jurado_200`), de ellas en el Test Gold: 0. No deben usarse para evaluar.
- Parte del entrenamiento que viene de fuera de las particiones oficiales: 33,5%. Se reporta aparte de la partición train oficial.
