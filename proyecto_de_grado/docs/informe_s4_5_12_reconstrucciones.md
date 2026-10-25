# Resultado S4.5 — Auditoría preliminar de las doce reconstrucciones

Fuente: archivo del usuario `reconstrucciones_preliminares_s4_5.jsonl`. Registro de resultados técnicos **no Gold**. Un puntaje de coincidencia textual (incluido 1.0) no constituye precisión de recuperación ni garantiza identidad bibliográfica.

| Contexto | Estado / motivo | Score de párrafo | Párrafo | Bibliografía candidata |
|---|---|---:|---:|---|
| `S14-2033_P11-1016_0` | `TARGETCIT_cerca_de_OTHERCIT_grupo_potencial` | 0.692 | 0 | BIBREF7 |
| `D14-1103_P06-1055_0` | `referencia_candidata_no_unica_en_parrafo` | 0.600 | 0 | BIBREF5 |
| `P14-1098_D09-1099_1` | `TARGETCIT_cerca_de_OTHERCIT_grupo_potencial` | 1.000 | 46 | BIBREF17 |
| `W14-3321_W08-0509_0` | `TARGETCIT_cerca_de_OTHERCIT_grupo_potencial` | 0.600 | 12 | BIBREF13 |
| `E14-1037_D12-1069_0` | `bibliografia_candidata_sin_cita_en_parrafo` | 1.000 | 13 | BIBREF13 |
| `D14-1210_N03-1017_1` | `bibliografia_candidata_sin_cita_en_parrafo` | 0.556 | 18 | BIBREF19 |
| `W14-2710_D13-1010_0` | `candidata_para_revision_humana` | 1.000 | 0 | BIBREF16 |
| `S14-2006_P14-1133_0` | `bibliografia_candidata_sin_cita_en_parrafo` | 1.000 | 1 | BIBREF1 |
| `D14-1215_D10-1004_0` | `bibliografia_candidata_sin_cita_en_parrafo` | 0.867 | 62 | BIBREF19 |
| `W14-5505_J07-2003_0` | `TARGETCIT_cerca_de_OTHERCIT_grupo_potencial` | 0.737 | 6 | BIBREF4 |
| `D14-1175_D13-1174_2` | `TARGETCIT_cerca_de_OTHERCIT_grupo_potencial` | 0.800 | 17 | BIBREF8 |
| `E14-1067_D13-1181_0` | `TARGETCIT_cerca_de_OTHERCIT_grupo_potencial` | 0.571 | 2 | BIBREF7 |

## Observaciones

- La única oración candidata, `W14-2710_D13-1010_0`, contiene `TARGETCIT` una vez y conserva referencias de otros autores. Sigue pendiente de revisión independiente contra `BIBREF16` y el span original.
- La causa `TARGETCIT_cerca_de_OTHERCIT_grupo_potencial` es una **abstención heurística** de G1.2, no un dictamen humano de agrupamiento. Es especialmente importante inspeccionar la estructura de paréntesis de `W14-3321_W08-0509_0` y `E14-1067_D13-1181_0` sin forzar aceptación.
- Para los cuatro casos sin cita identificada en el párrafo, inspeccionar `cite_spans`, offsets, biblioteca candidata, otros párrafos del citante y posibles diferencias del parseo OCR/GROBID.
- Para `D14-1103_P06-1055_0`, inspeccionar las múltiples posiciones `BIBREF5`, contrastando cuál corresponde al contexto enmascarado.
- La preselección contiene casos de `val` expuestos a depuración: no reutilizarlos para el Test Gold final de `test`. No modificar `train/val/test.json` ni el corpus fuente.

## Siguiente comprobación

Ejecutar `diagnosticar_enlaces_s4_5.py` del paquete adjunto contra los 12 documentos citantes ya almacenados localmente. Solo a partir de ese CSV será posible distinguir si los bloqueos son por extracción de spans, agrupamiento real o coincidencia textual que no verifica el vínculo. El resultado tampoco representa validación humana.
