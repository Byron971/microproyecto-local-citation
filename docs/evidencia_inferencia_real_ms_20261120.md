# Evidencia técnica de inferencia real SciBERT + M/S (caso TRAIN)

**Estado:** evidencia local reportada y verificada mediante salidas de PowerShell proporcionadas por el ejecutor; los JSON originales permanecen en el equipo local y **no fueron incorporados ni inspeccionados byte a byte en este PR**. No es evaluación Gold ni reproducción desde un clon limpio.

## 1. Ejecución y procedencia

- Contexto: `D09-1001_D08-1068_0`.
- Artículo citado: `D08-1068`, *Joint Unsupervised Coreference Resolution with Markov Logic*.
- Fuente bibliográfica identificada por la evidencia local: https://aclanthology.org/D08-1068/
- Split informado en la procedencia local: `train` (el reporte no sustituye una comprobación independiente de los splits).
- SHA-256 OCL registrado: `da328fade053dcddf731ddd14a0306cd9595bdf4ed31bee51ed53a154157315b`.
- Párrafos originales: 70; chunks totales: 46; candidatos enviados: 46; cobertura reportada: completa.
- Recuperador: `scibert_base_mean_pooling_cosine`.
- Revisión SciBERT: `24f92d32b1bfb0bcaf9ab193ff3ad01e87732fc1`.
- Dispositivo de **respuesta actual**: `cpu`.
- Rama local del ejecutor: `feature/experimentos-pista-S`; commit local registrado: `c93173fe09366795c625a0aa191550790a007071`.
- Registro de cierre generado localmente: `2026-11-21T04:02:08.1099764Z`. Esta es la fecha de **generación del registro**, no prueba por sí misma la hora en que se ejecutó la inferencia.

## 2. Salida funcional observada

| Posición | Chunk | Sección | Similitud coseno |
| --- | --- | --- | ---: |
| 1 | `p00011-p00012` | Markov Logic | 0.942208 |
| 2 | `p00002-p00003` | Introduction | 0.916638 |
| 3 | `p00065-p00065` | Conclusion | 0.912789 |

| Clasificador | Clase más probable | Valor softmax |
| --- | --- | ---: |
| M | Evidence | 0.458719 |
| S | Background | 0.866312 |

Los valores softmax **no** representan accuracy, F1 ni confianza calibrada de acierto. No existe adjudicación humana del caso documentada en este reporte.

El ejecutor comparó `respuesta_http_20261120.json` y `respuesta_real_ms.json` y obtuvo `True` para coincidencia de recuperador, revisión, Top-3 y clasificadores. Ambas respuestas registran tres fragmentos. Esta prueba compara el contenido serializado de los campos seleccionados; los archivos completos no son idénticos (sus hashes difieren).

## 3. Integridad y huellas de la evidencia local

El comando `python scripts/verificar_artefactos_ms.py` reportó ambos checkpoints presentes, tamaños correctos, SHA-256 correcto y manifiestos de entrenamiento válidos.

| Artefacto | SHA-256 |
| --- | --- |
| Checkpoint M | `26e354d785964b3e8a3a9d9fa0b1857c3e1e542ff5ed4f174f063f48898e80a7` |
| Checkpoint S | `2369f52bee1b96576dddb1ef0f37a5043f552c73b3e836da31a53d956d271a69` |
| `manifiesto_reproducibilidad.json` | `71aa946b7d3c8a2d3ac39620e0185124e38afb2b596cafd93ec8f0f2ab76c863` |
| `procedencia_real_ms.json` | `81fe0d684afaadfc431b935de93a9a94eae5b4cffc7772030d3032a7ecbf1ab9` |
| `respuesta_http_20261120.json` | `297d742aa96b60e493178a94638e93d240ad2f3a3d74966a2c198aed4b1a1235` |
| `respuesta_real_ms.json` | `0f0d78064d73309bb318bfe5116b01ccede20397a6f189cc1f803dda30067646` |
| `solicitud_real_ms.json` | `19786b2b21c8be4ee24ed773f7d60d47ceefe239d40c0d23eff9f14d01b8f185` |

**Diferencia histórica preservada:** el manifiesto del 18/19 de noviembre registró `cuda` y el SHA de respuesta `0978e1607aa203e117eba559cdfd3974dd73408b66f8afa2b8e4f995862273b1`, distinto del archivo actual `respuesta_real_ms.json`. Por ello no se sobrescribe el manifiesto histórico: el nuevo `manifiesto_cierre_tecnico_ms.json` generado localmente representa un registro separado, con dispositivo `cpu`, y huellas de los archivos observados.

## 4. Verificación de CI

La rama de integración incluyó la corrección de la prueba de rutas vía OpenAPI, el ajuste de señales del endpoint M/S y el preflight offline para checkpoints. En el commit `3b9a49c618fd161652effcf8ddba8d4082f1a76e`, los ocho workflows de la PR #201 fueron consultados y figuraban con `conclusion: success`, incluyendo Configuración segura del backend, Top-3 y Ciencia A/B y Docker CPU **sin pesos**. Los workflows no sustituyen la inferencia local con checkpoints.

## 5. Pendientes de certificación

1. Revisar los cinco JSON originales en entorno autorizado y repetir el cálculo de hashes.
2. Verificar independientemente las particiones por documento citante y pares citante-citado, sin fuga.
3. Publicar un procedimiento de recuperación **privada** de M/S y manifiestos; no subir los pesos, textos completos ni datos Gold.
4. Reproducir desde clon y entorno limpios, con versiones compatibles del paquete `recuperacion-densa` y de Python, comprobar código de salida, Top-3, clases y hashes.
5. Mantener las métricas sobre Gold humano certificado como una evaluación **posterior e independiente**.

**Conclusión limitada:** existe una demostración funcional local documentada de SciBERT Top-3 + clasificación M/S sobre un caso académico identificado como TRAIN, con integridad local de pesos y coincidencia de salidas reportada. No se certifica calidad de recuperación ni F1 de las nueve clases.
