# Spike: ¿de dónde sale el texto completo de los artículos?

**Fecha:** 23 de septiembre de 2026 · **Muestra:** 500 contextos aleatorios de ACL-200 (semilla 42) · **Script:** `medir_enlace.py`

## La pregunta

La propuesta V3 enlaza ACL-200 con unarXive "por identificador de arXiv" para obtener el texto
completo que exigen la Fase 1 (reconstruir contextos truncados) y la Fase 2 (chunks del
artículo citado). Pero los IDs de ACL-200 son de ACL Anthology (`P15-2138`), no de arXiv, y el
99,5 % de los artículos citados es anterior a 2015. ¿Funciona ese enlace? ¿Hay una ruta mejor?

## Resultado

| | Ruta A: ACL OCL (mismo ID de ACL-200) | Ruta B: unarXive vía arXiv |
|---|---:|---:|
| Citado con texto completo | **99,8 %** (98,0 % usable para chunks) | 4,8 % con ID de arXiv |
| Citante con texto completo | **99,6 %** | 4,0 % con ID de arXiv |
| Contexto ubicado en el citante (reconstruible a oración completa) | **84,2 %** | — |
| **Par completo** (citado usable + contexto reconstruible) | **82,2 % ± 3,4 pp** | **0,2 %** (1 de 500), y es cota superior |

La ruta B, tal como está en la propuesta, no es viable: aun suponiendo que todo artículo con ID
de arXiv esté en unarXive, cubriría 1 de cada 500 pares. La ruta A resuelve más de 4 de cada 5
pares; extrapolado a los 63.768 contextos de ACL-200, son unos 52.000 pares con texto completo,
muy por encima de la meta de 18.000 ejemplos.

**ACL OCL** (WINGNUS/ACL-OCL en HuggingFace, Rohatgi et al., 2023) es el corpus de ACL Anthology
con el texto completo ya extraído por GROBID en formato S2ORC: párrafos con su sección, citas
en el texto enlazadas a la bibliografía. Un JSON por artículo, direccionable por el mismo ID de
ACL-200.

## Calidad del texto de los citados (ruta A)

- Mediana de 4.258 palabras de cuerpo y 13 secciones por artículo; el 96 % de los párrafos trae su sección → se puede registrar la sección de cada chunk, como pide la propuesta.
- Mediana de 34 chunks por artículo con la regla de la propuesta (2 párrafos o 300 palabras).
- 175 de 398 citados tienen al menos un párrafo de más de 300 palabras (GROBID a veces fusiona párrafos) → el chunker debe partir por oración, no solo por párrafo.
- Es texto derivado de PDF, con ruido de extracción: por ejemplo, "Déjean (2000)" aparece como "D6jean (2000)". La propuesta priorizaba LaTeX; para artículos de ACL anteriores a 2015 esa fuente no existe.

## Controles que respaldan las cifras

- **Inspección manual:** el contexto truncado de ACL-200 aparece en el párrafo correcto del citante, con la oración completa y la cita original legible.
- **Control negativo:** cada contexto se buscó en el artículo de *otro* citante: 0 de 500 falsos positivos. El 84,2 % no está inflado por el método.
- **Fallos:** de los 79 contextos no ubicados, 64 tienen coincidencias parciales (18–50 %), es decir, el texto está pero el ruido lo rompe; solo 15 no aparecen. Con coincidencia difusa la tasa subiría, así que 84,2 % es un piso.
- **Bibliografía:** el título del citado aparece en la bibliografía extraída del citante en el 92,6 % de los casos (1,8 % de falsos positivos en el control negativo).

## La otra variante de la ruta B

Construir los contextos directamente desde unarXive, abandonando ACL-200. No se midió a escala:
son 105 GB en un solo tar. Su propia documentación reporta que el 51,2 % de los enlaces de cita
se resuelve a OpenAlex, y en el artículo de muestra ninguna referencia trae ID de arXiv. Llegar
al texto completo del citado exigiría encadenar OpenAlex → arXiv → unarXive, con un techo que ya
parte de ~51 %.

## Recomendación

1. **Adoptar la ruta A** como fuente de texto completo: ACL-200 para los pares y los contextos, ACL OCL para el texto de citantes y citados.
2. **Actualizar la decisión en la documentación del proyecto:** el enlace es por ID de ACL Anthology, no por arXiv, y el texto es de PDF vía GROBID, no de LaTeX, con esta medición como justificación.
3. **Aprovechar la bibliografía de ACL OCL para las clases escasas:** como 80.000 artículos traen las citas enlazadas a su bibliografía, se pueden extraer contextos adicionales fuera de ACL-200. Eso mitiga el riesgo de no llegar a 2.000 ejemplos en *Further Reading* o *Identification of the Originator*.
4. **Chunker con partición por oración** para los párrafos de más de 300 palabras.

## Limitaciones

- La ruta B se midió como cota superior (tener ID de arXiv en Semantic Scholar), no como presencia verificada en unarXive; la conclusión no cambia porque la cota ya es 0,2 %.
- "Usable para chunks" se definió como ≥ 500 palabras de cuerpo y ≥ 3 secciones.
- Licencias por verificar antes de redistribuir el dataset: ACL OCL se publica con licencia MIT; los artículos de ACL Anthology anteriores a 2016 tienen licencia no comercial (CC BY-NC-SA 3.0) y los posteriores CC BY 4.0.

## Cómo reproducirlo

```powershell
cd "D:\ruta\al\repo\microproyecto-local-citation"
python proyecto_de_grado\scripts\spike_enlace_datos\medir_enlace.py --acl200 data\raw --cache proyecto_de_grado\scripts\spike_enlace_datos\cache_ocl --out proyecto_de_grado\docs\spike_enlace_datos --n 500
```

Solo usa la librería estándar de Python. Descarga ~870 JSON (~84 MB) en pocos minutos; el
corpus completo que necesita ACL-200 son 13.412 artículos, del orden de 1,3 GB. Los resultados
por contexto quedan en `resultados/resultados_por_contexto.jsonl`.
