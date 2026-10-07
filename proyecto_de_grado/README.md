# Proyecto de grado — Recomendación local de citas y clasificación de su función

Esta carpeta reúne los avances del **proyecto de grado** del Grupo 19 (Tema 1), que se desarrolla en el curso *Proyecto: Despliegue de Soluciones* con la profesora Haydemar Núñez. Está separada del microproyecto que ocupa el resto del repositorio, que ya fue entregado y calificado en el curso anterior. Lo que se reutiliza de ese trabajo, como los datos de ACL-200 versionados con DVC y el piloto de anotación, se lee desde su ubicación original y no se duplica.

**Integrantes:** Carlos Eduardo Duque Lugo, John Byron Arias Sanz, Gabriel Gustavo Pinzón Páez, José María Zambrana Arze, Carlos Alfredo Caicedo Bermúdez.

## Estado al 7 de octubre de 2026

| Frente | Estado |
|---|---|
| Propuesta V3 | Calificada con 86/100. Los 14 puntos perdidos están en metodología, datos y evaluación ([retroalimentación](docs/retroalimentacion_propuesta_V3.md)). |
| Fuente de texto completo | Decidida con evidencia: ACL OCL, enlazado por el ID de ACL Anthology, deja completo el 82,2 % de los pares; unarXive por ID de arXiv, el 0,2 % ([estudio](docs/spike_enlace_datos/README.md)). El experto confirmó que se pueden combinar fuentes si se cumplen las características del enunciado y las cuotas. |
| Informe de avance | Borrador con las secciones ajustadas a la retroalimentación ([Markdown](docs/informe_avance/borrador_ajustes_informe_avance.md) · [Word](docs/informe_avance/borrador_ajustes_informe_avance.docx)). Tiene 6 marcas de pendiente. |
| Anotación | Hay una página de práctica y calibración ([fuentes](anotacion/taller/)). La ronda de calibración está pendiente de correr con el equipo. |
| Modelos, API y tablero | Sin empezar. |

## Estructura

```
proyecto_de_grado/
├── docs/
│   ├── retroalimentacion_propuesta_V3.md     comentarios de la docente por criterio y qué ajustar
│   ├── informe_avance/                        borrador del informe de avance (Markdown y Word)
│   └── spike_enlace_datos/                    estudio de enlace ACL-200 ↔ ACL OCL / unarXive
├── anotacion/
│   ├── taller/                                página de anotación: guía, práctica y calibración
│   ├── pruebas/                               pruebas de la página y del cálculo de acuerdo
│   └── ids_excluir_test_gold.txt              77 casos que NO pueden entrar al Test Gold
└── scripts/
    ├── cifras_informe.py                      recalcula desde ACL-200 las cifras del informe
    └── spike_enlace_datos/medir_enlace.py     mide la cobertura de texto completo por ruta
```

Más adelante, el curso pide `notebooks/`, `modelos/` y `app/` (o `src/`) para el despliegue. Se crearán dentro de esta carpeta cuando haya contenido.

## Decisiones registradas

1. **Un solo dataset integrado.** ACL-200 aporta los contextos y los pares; ACL OCL aporta el texto completo. MultiCite e ILCiteR quedan solo como referencia externa.
2. **Partición temporal.** Se conserva la de ACL-200: entrenamiento 2009–2013, validación 2014 y prueba 2015, sin artículos citantes compartidos.
3. **Test Gold separado del entrenamiento.** El Test Gold lo anotan solo personas, con doble anotación ciega, y es lo único que se usa para evaluar. El conjunto de entrenamiento lo pre-etiquetan los modelos.
4. **La cita objetivo siempre va marcada** en las hojas de anotación. En el piloto, con κ = 0,48, la marca se había borrado.
5. **Los casos de práctica y de calibración no entran al Test Gold.** La lista está en [`anotacion/ids_excluir_test_gold.txt`](anotacion/ids_excluir_test_gold.txt).

## Página de anotación

La página tiene cuatro pestañas:

- **Guía:** las 9 funciones con sus señales en inglés y español, el orden de decisión y las reglas para casos ambiguos.
- **Practicar:** 41 casos con traducción al español y explicación después de responder, en tres niveles: casos claros, trampas y los desacuerdos del piloto.
- **Calibración:** 36 casos nuevos sin respuesta visible. Al cerrar la ronda calcula el α de Krippendorff, el κ por pareja y el tiempo por caso, y lista los casos para discutir.
- **Resultados:** el desempeño propio por función y el acuerdo del equipo.

La versión publicada se comparte como enlace de claude.ai. Para que las respuestas de cada persona se guarden en el equipo, hay que tener acceso de *Contributor*. El archivo [`anotacion/taller/taller_anotacion.html`](anotacion/taller/taller_anotacion.html) es la misma página para abrir en el navegador; así abierta funciona en modo local, sin compartir respuestas.

Las etiquetas de referencia de los niveles 1 y 2 de la práctica son una propuesta pendiente de validar con el equipo. Las del nivel 3 son las que el equipo reconcilió en el piloto.

## Cómo reproducir

Todos los comandos se ejecutan desde la raíz del repositorio, con los datos de ACL-200 descargados (`dvc pull`; el remoto por defecto es público).

```powershell
# Cifras del informe (tamaño, particiones por año, truncamiento, años de los citados)
python proyecto_de_grado\scripts\cifras_informe.py data\raw

# Reconstruir la página de anotación a partir de sus fuentes
python proyecto_de_grado\anotacion\taller\build.py data\raw proyecto_de_grado\anotacion\taller

# Probar la página y el cálculo del acuerdo (requiere Node.js)
cd proyecto_de_grado\anotacion\pruebas
npm install
node test_acuerdo.js ..\taller\acuerdo.js
node test_alpha.js ..\taller\acuerdo.js
node prueba.js ..\taller\taller_anotacion.html ..\taller\acuerdo.js
```

`prueba.js` simula la página completa en un navegador, con dos compañeros ficticios que ya cerraron la calibración. Verifica 23 comportamientos, entre ellos que el α que muestra la página coincida con un cálculo independiente. `test_acuerdo.js` comprueba que el κ coincide con el 0,484 que calcula `src/evaluation/annotation.py` para el piloto.

## Pendientes

- Curar el conjunto de 100 contextos con los fragmentos que respaldan cada cita. Según el experto, el Top-3 es un insumo para la clasificación y no requiere métricas propias, así que su evaluación principal es la mejora en F1 Macro (C2 frente a C1).
- Decisión del equipo sobre el tamaño del Test Gold: 450 casos (recomendado) o 2.700 (propuesta V3).
- Ronda de calibración con los cinco integrantes hasta alcanzar α ≥ 0,70.
- Línea base de clasificación y primeras cifras de Recall@K y MRR para el informe de avance.
