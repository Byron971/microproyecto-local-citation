# Lista de cierre de la Entrega 2

Este documento resume el estado operativo de la segunda entrega. Su propósito
es responder dos preguntas: **qué falta hacer** y **qué evidencia permite dar
cada tarea por terminada**.

La lista no reemplaza el [enunciado oficial](enunciados/0401_entrega_02.pdf) ni
la [especificación del modelo](specs/especificacion_tecnica.md). Debe
actualizarse cuando se complete una tarea o cambie el alcance acordado por el
equipo.

## 1. Estado general

- [x] Implementar la línea base TF-IDF.
- [x] Implementar el modelo supervisado de reordenamiento.
- [x] Comparar el modelo con la línea base mediante Recall@10 y MRR@10.
- [x] Centralizar los parámetros del modelo en `config/model.yaml`.
- [x] Guardar y volver a cargar el modelo sin reentrenarlo.
- [x] Incorporar los resultados locales y su análisis en el reporte.
- [x] Documentar los conceptos y el procedimiento técnico.
- [x] Verificar el código con pruebas automatizadas y Tox.
- [x] Publicar los experimentos definitivos en el MLflow compartido.
- [ ] Completar e integrar el tablero de la entrega.
- [ ] Cerrar la documentación, el PDF y el flujo de Git.

## 2. Pendientes del modelo supervisado — issue #6

### 2.1 Ejecutar los experimentos definitivos

- [x] Ejecutar la matriz experimental definida a continuación con el código
  actual y el servidor MLflow compartido.
- [x] Confirmar que todas las corridas usan los mismos datos, `seed`, `top_n`,
  `k` y demás parámetros de control.
- [x] Confirmar que cada corrida registra parámetros, métricas, tiempos,
  coeficientes y artefactos.
- [x] Confirmar que el artefacto `model.joblib` de la variante seleccionada
  puede cargarse y evaluarse sin llamar nuevamente a `fit`.

Las seis corridas quedaron registradas en `http://100.53.183.142:8050`
(experimento `recomendacion-local-citas`), verificadas vía la API REST de
MLflow. Resultado de la matriz (`val`, mismos datos/`seed`/`top_n`/`k`/`max_features`/`min_df`
en las seis):

| ID | `negative_strategy` | `c` | Recall@10 | MRR@10 |
|---|---|---:|---:|---:|
| `LR-R-C01` | `random` | 0.1 | 0,2882 | 0,1489 |
| `LR-R-C1` | `random` | 1.0 | 0,2882 | 0,1490 |
| `LR-R-C10` | `random` | 10.0 | 0,2882 | 0,1490 |
| `LR-H-C01` | `hard` | 0.1 | 0,0628 | 0,0212 |
| `LR-H-C1` | `hard` | 1.0 | 0,0629 | 0,0212 |
| `LR-H-C10` | `hard` | 10.0 | 0,0629 | 0,0212 |

Variante seleccionada según la regla acordada: **`LR-R-C1`** (`random`, `c=1.0`;
empata con `LR-R-C10` a cuatro decimales en MRR@10 y Recall@10, se resuelve por
menor `c`). `c` no cambia la conclusión en ningún caso: las tres corridas
`random` son esencialmente idénticas entre sí, y las tres `hard` también —el
colapso de la variante difícil no es un efecto de regularización, es
consistente con el coeficiente negativo de `similarity_abstract` ya descrito en
el reporte y la especificación técnica.

El servidor compartido anterior (documentado en el reporte, cuenta de Carlos
Caicedo) ya no está disponible; se desplegó uno nuevo sobre la instancia
personal de José Zambrana (`100.53.183.142:8050`, Ubuntu 26.04, `t3.small`,
como servicio `systemd`) para no bloquear el cierre de la entrega. Pendiente
para el equipo: acordar dónde vivirá el servidor compartido de forma estable
hacia la Entrega 3.

#### Matriz experimental acordada

Se utilizará un diseño factorial pequeño de **dos estrategias de negativos por
tres valores de regularización**, para un total de seis corridas supervisadas.
Un diseño factorial prueba todas las combinaciones de los factores elegidos;
permite observar tanto el efecto de la estrategia de negativos como si ese
efecto cambia al regularizar más o menos el modelo.

| ID | `negative_strategy` | `c` | Propósito |
|---|---|---:|---|
| `LR-R-C01` | `random` | 0.1 | Negativos aleatorios con regularización fuerte |
| `LR-R-C1` | `random` | 1.0 | Negativos aleatorios con valor de referencia |
| `LR-R-C10` | `random` | 10.0 | Negativos aleatorios con regularización débil |
| `LR-H-C01` | `hard` | 0.1 | Negativos difíciles con regularización fuerte |
| `LR-H-C1` | `hard` | 1.0 | Negativos difíciles con valor de referencia |
| `LR-H-C10` | `hard` | 10.0 | Negativos difíciles con regularización débil |

Los identificadores `LR-…` son etiquetas de esta tabla. El nombre automático
del run contiene la estrategia y una marca de tiempo; el valor exacto de `c`
queda registrado en la columna de parámetros de MLflow.

En regresión logística, `c` es el inverso de la fuerza de regularización:
`0.1` restringe más los coeficientes, `1.0` es el punto de referencia y `10.0`
los restringe menos. Los tres valores están separados por un orden de magnitud,
una búsqueda pequeña y habitual para este hiperparámetro.

#### Parámetros que deben permanecer fijos

| Parámetro | Valor | Razón para no variarlo en esta comparación |
|---|---:|---|
| `seed` | 42 | Mantener reproducible el muestreo aleatorio |
| `negatives_per_positive` | 2 | Mantener igual la proporción de clases |
| `top_n` | 100 | Reordenar exactamente la misma profundidad |
| `k` | 10 | Comparar siempre Recall@10 y MRR@10 |
| `max_features` | 50000 | Mantener fijo el vocabulario máximo TF-IDF |
| `min_df` | 2 | Mantener el mismo filtrado de vocabulario |
| `data_dir` | `data/raw` | Usar los mismos datos y particiones |

No se variarán `top_n`, `k`, `max_features`, `min_df` ni la cantidad de
negativos en esta matriz. Cambiarlos alteraría simultáneamente la recuperación,
las características o el balance del entrenamiento y dificultaría atribuir la
diferencia observada a `negative_strategy` y `c`.

#### Regla de selección definida antes de ejecutar

1. Descartar cualquier corrida que falle, use otros hashes de datos o no tenga
   los artefactos completos.
2. Elegir el mayor **MRR@10** sobre `val`, porque premia colocar la primera cita
   correcta en una posición alta.
3. Si dos configuraciones tienen el mismo MRR@10 a cuatro decimales, elegir la
   de mayor **Recall@10**.
4. Si el empate continúa, elegir el menor `c`, por aplicar mayor regularización.

La selección se realiza exclusivamente con `val`. `test` permanece reservado
para evaluar una sola vez el modelo ganador en la etapa final del proyecto.

La línea base comparable no agrega otra combinación: cada corrida supervisada
ya registra las métricas `baseline_*` sobre los mismos candidatos utilizados
por el reordenador. Esto evita comparar accidentalmente políticas de candidatos
distintas.

Para ejecutar cada combinación, se definen `negative_strategy` y `c` en
`config/model.yaml`; los demás campos se conservan sin cambios. Después se
utiliza:

```bash
export MLFLOW_TRACKING_URI="http://SERVIDOR:8050"
uv run python -m src.training.run_linear_reranker train
```

La combinación queda terminada cuando el run puede verse desde otra máquina en
el experimento compartido, sus parámetros coinciden con la fila correspondiente
y contiene sus artefactos. Un run guardado únicamente en el backend local no
satisface este punto.

### 2.2 Incorporar la evidencia en el reporte

- [ ] Reemplazar `reportes/reporte02/mlflow_tabla_runs.png` por una captura que
  muestre las seis combinaciones supervisadas y sus métricas de línea base en
  MLflow compartido. **Pendiente**: requiere entrar a
  `http://100.53.183.142:8050` desde un navegador y tomar la captura a mano.
- [ ] Verificar que en la captura se distingan Recall@10 y MRR@10. Depende de
  la captura anterior.
- [x] Eliminar de `reportes/reporte02/main.tex` las frases que indican que las
  corridas supervisadas todavía deben publicarse.
- [x] Revisar que los valores del texto y las tablas coincidan con los runs
  definitivos. Coinciden exactamente con los ya escritos en el reporte y la
  especificación (no hubo que cambiar ninguna cifra, solo el estado de
  "pendiente" a "hecho").
- [x] Actualizar la definición de terminado en la especificación técnica.

**Nota:** las capturas `ec2_instancia.png`, `ec2_mlflow_servidor.png` y
`mlflow_ui_ip.png` en `reportes/reporte02/` muestran la instancia EC2 anterior
(cuenta de Carlos Caicedo, IP `3.236.142.168`), que ya no está disponible. El
servidor compartido ahora vive en `100.53.183.142` (ver nota en la sección
2.1). Esas tres capturas también deberían retomarse desde la instancia actual
para que la evidencia sea consistente con el texto.

No debe elegirse una variante porque tenga mejor `accuracy` o menor pérdida. La
decisión del reordenador se basa en Recall@10 y MRR@10 calculados sobre los
mismos candidatos de validación.

### 2.3 Cerrar el trabajo en GitHub

- [ ] Revisar que el diff no incluya archivos de datos, credenciales, `mlruns/`
  ni artefactos locales.
- [ ] Crear commits con mensajes que identifiquen la implementación, las
  pruebas y la documentación.
- [ ] Abrir un Pull Request relacionado con el issue #6.
- [ ] Registrar en el reporte los commits o el Pull Request como evidencia de
  la contribución individual.
- [ ] Integrar el Pull Request después de la revisión del equipo.

## 3. Pendientes grupales de la entrega

### 3.1 Tablero — issues #8 y #9

- [ ] Conectar el tablero con datos reales del proyecto.
- [ ] Completar el panel recomendador de citas.
- [ ] Completar el panel de exploración del conjunto de datos.
- [ ] Explicar en el reporte qué recibe y qué devuelve cada panel.
- [ ] Agregar una captura de una consulta real resuelta, no solo de la pantalla
  inicial.
- [ ] Reemplazar la sección marcada como pendiente en
  `reportes/reporte02/main.tex`.
- [ ] Añadir los commits o Pull Requests correspondientes a la tabla de trabajo
  en equipo.

Estas tareas dependen de los responsables de los issues #8 y #9, pero afectan
el cierre de toda la entrega.

### 3.2 Revisión final del reporte

- [ ] Buscar y resolver todos los marcadores `TODO`, `PENDIENTE` y «Sección
  pendiente».
- [ ] Revisar que las figuras tengan títulos legibles y sean mencionadas en el
  texto.
- [ ] Revisar ortografía, numeración, referencias y consistencia de métricas.
- [ ] Compilar el PDF después de integrar todos los aportes.
- [ ] Inspeccionar visualmente todas las páginas del PDF.
- [ ] Confirmar que el reporte respeta el límite de páginas del enunciado.
- [ ] Confirmar que el archivo final abre correctamente y es el que se enviará.

Comprobación rápida de marcadores pendientes:

```bash
rg -n "TODO|PENDIENTE|Sección pendiente" reportes/reporte02 docs
```

## 4. Verificaciones antes de entregar

- [ ] Sincronizar el entorno con `uv sync`.
- [ ] Ejecutar toda la suite con `uv run tox`.
- [ ] Confirmar que todas las pruebas finalizan correctamente.
- [ ] Comprobar que `git status` contiene únicamente cambios intencionales.
- [ ] Verificar desde una copia limpia del repositorio que se puede seguir el
  README para instalar, entrenar y validar.
- [ ] Confirmar que los datos requeridos se recuperan mediante el procedimiento
  documentado y que no dependen de archivos personales.
- [ ] Verificar los enlaces y rutas mencionados en la documentación.

## 5. Uso de las particiones

- TF-IDF se ajusta sobre el catálogo fijo de artículos, sin utilizar etiquetas
  ni contextos de validación o prueba.
- `train` se utiliza para construir los pares y ajustar las transformaciones
  supervisadas y la regresión logística.
- `val` se utiliza para comparar `random` frente a `hard` y seleccionar la
  variante de esta entrega.
- `test` se reserva para la evaluación final del modelo seleccionado.

Por tanto, **no es necesario ejecutar `test` para cerrar la comparación de la
Entrega 2**. Consultarlo durante la selección introduciría información de prueba
en una decisión de diseño.

## 6. Definición de entrega terminada

La Entrega 2 puede considerarse lista cuando:

1. no quedan casillas pendientes en las secciones 2, 3 y 4;
2. los runs definitivos son visibles en MLflow compartido;
3. el tablero funciona con una consulta real;
4. el reporte no contiene marcadores temporales y su PDF fue revisado;
5. todos los aportes están versionados, revisados e integrados.
