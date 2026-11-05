# Auditoría de extracción, chunks y metadatos retóricos (A1, issue #101)

Cadena auditada: `integrar_contexto()` → `fragmentar()` → chunks usados por el recuperador Top-3.
No contiene métricas Top-3 ni nada rotulado como gold.

## 1. Alcance y comandos
- Commit base: `f45e052` (rama `feature/issue-101`). Paquete: `packages/auditoria-corpus` (ver su README).
- Descarga (único paso con red), desde la raíz:
  `uv run --project packages/auditoria-corpus python -m auditoria_corpus.descarga --n 200 --semilla 101`
  → 200 citados únicos estratificados por split (train 146, val 30, test 24): 199 descargados, 1 `404` (`W03-2501`), 0 errores. SHA-256 del manifiesto: `c0a0322f…05ba1`.
- Auditoría (sin red): `uv run --project packages/auditoria-corpus python -m auditoria_corpus.cli`. Ejecutada dos veces: `resumen.json`, `auditoria_chunks.csv` y `muestras_train.csv` idénticos byte a byte. El `muestras_train.csv` versionado es el subconjunto revisado a mano (ver §6).
- Evidencias: `docs/evidencias_a1/` (`resumen.json`, `muestras_train.csv`, `manifiesto_muestra.json`).

**Toda cifra de cobertura es sobre la muestra descargada (200 de 4568 citados únicos de ACL-200), no sobre el corpus completo.** Los porcentajes sobre ACL-200 (≈2 %) solo reflejan el tamaño de la muestra.

## 2. Cobertura (muestra de 200 citados)
| Split | Contextos OK / total | Citados OK / únicos en ACL-200 |
|---|---|---|
| train | 605 / 30 390 (1,99 %) | 91 / 3 323 (2,74 %) |
| val | 162 / 9 381 (1,73 %) | 48 / 2 208 (2,17 %) |
| test | 155 / 9 585 (1,62 %) | 50 / 2 236 (2,24 %) |

Un citado puede aparecer en varios splits, por eso los citados OK por split suman más de 125. Los porcentajes bajos reflejan el tamaño de la muestra, no la calidad de la cadena. Cifra global: **125 de 200 citados (62,5 %)** produjeron chunks válidos.

## 3. Errores por causa (citados)
| Causa | Citados |
|---|---|
| `parrafo_supera_palabras` | 74 |
| `citado_404` | 1 |
| otras (`id_incorrecto`, `archivo_invalido`, `sin_parrafos`, `parrafo_supera_caracteres`, `indice_invalido`) | 0 |

(`citado_no_descargado` = 4 368 son los citados fuera de la muestra, no un fallo.)
Sobre los 199 artículos descargados, **74 (37,2 %) se descartan completos** porque algún párrafo supera 300 palabras.

## 4. Cumplimiento de chunks
- 3 705 chunks de 125 artículos. **0 violaciones** de: ≤300 palabras, 1–2 párrafos, una sola sección, índices contiguos, reconstrucción exacta del texto sin pérdidas ni duplicados, `chunk_id` coherente.
- Palabras por chunk: mín 1, mediana 100, máx 300. El 70,15 % son de 2 párrafos.
- Sin sección: 157 chunks (4,24 %).
- Huecos de índice (párrafos vacíos descartados): 0 en esta muestra.
- Perfil de sección **heurístico** (palabras clave, no validado): otra 1 884, método 584, results 382, introduction 350, conclusion 231, vacía 157, related_work 117. El 51 % cae en «otra»: el mapeo es pobre y no debe usarse como etiqueta retórica sin validación.

## 5. Reproducibilidad e IDs
- Fragmentar dos veces el mismo artículo da la misma huella SHA-256 en los 125 artículos.
- `chunk_id` **no es único globalmente**: 242 valores distintos para 3 705 chunks; 190 aparecen en varios artículos. El par `(cited_id, chunk_id)` sí es único (3 705/3 705).

## 6. Muestras de train: verificación manual
La CLI genera 20 casos de train (sin IDs de gold/piloto, un caso por citado, semilla 101). Se revisaron a mano **10**. Son las filas 1–9 y 18 del archivo generado, y el archivo versionado `docs/evidencias_a1/muestras_train.csv` solo contiene esas 10 (commit `8ffcd88`). Las otras 10 se retiraron sin revisar. Por eso ese archivo ya no coincide byte a byte con la salida de la CLI, aunque las columnas de datos de las 10 filas no cambiaron. `resumen.json` sigue indicando `muestras.n = 20`, que es lo que genera la CLI.

**Revisor:** Carlos Duque. **Método:** comparar cada chunk con el PDF del artículo citado en ACL Anthology (`https://aclanthology.org/<cited_id>.pdf`).
- `texto_ok`: el texto del chunk coincide con el del PDF.
- `seccion_ok`: el texto aparece en el PDF bajo la sección que indica la columna `seccion`.
- `chunk_ok`: el chunk forma una unidad completa. Se marcó `no` cuando se corta a mitad de una frase.

| Criterio | Correctos | Incorrectos |
|---|---|---|
| `texto_ok` | 10 / 10 | 0 |
| `seccion_ok` | 9 / 10 | 1 |
| `chunk_ok` | 6 / 10 | 4 |

**Problemas encontrados.** Cada nota del revisor se contrastó con el JSON de ACL OCL en `cache_ocl`.
1. **Chunks cortados por fórmulas (4 de 10: `E06-1015`, `P03-1016`, `N10-1082`, `W10-0216`).**
   - **Qué pasa:** ACL OCL saca cada fórmula a un párrafo aparte. En `E06-1015`, `P03-1016` y `N10-1082` ese párrafo contiene solo la palabra `EQUATION`. En `W10-0216`, la expresión matemática en línea (`C is discarded if IG(S) ≥ IG(C) − δ,`) se separa del resto de la frase.
   - **Consecuencia:** como `fragmentar()` trabaja por párrafos, el chunk termina a mitad de frase (por ejemplo, `E06-1015` termina en «We define») y la continuación queda en otro chunk.
   - **Otros defectos vistos en esos artículos:** los subíndices aparecen separados (`T 1` en lugar de T₁) y en `E06-1015` el texto de una figura se extrajo como párrafo (`S → N VP …`).
2. **Sección equivocada (1 de 10: `W06-3807`).**
   - **Qué pasa:** el texto pertenece a la sección 4 del PDF, pero tiene asignada la sección 3 («Learning of Graph Rules»). En el JSON de ACL OCL la numeración salta de 3 a 5: el encabezado de la sección 4 no se extrajo, así que sus párrafos heredan la sección anterior.
   - **Consecuencia:** el error viene de la fuente, no de `fragmentar()`, y no se puede detectar con las comprobaciones automáticas del apartado 4.
3. **Sin problemas (5 de 10):** `W04-1017`, `P10-1107`, `D11-1135`, `P08-2042` y `P07-1120`. El texto, la sección y los límites del chunk coinciden con el PDF.

**Alcance:** 10 casos solo permiten describir tipos de error, no estimar su frecuencia en el corpus. Los 4 cortes por fórmula y el error de sección son defectos de la extracción de ACL OCL que las comprobaciones automáticas no detectan, porque cada chunk sí reproduce fielmente su JSON.

## 7. Interpretación y recomendaciones
Hallazgos preliminares del código frente a los datos:
1. **Confirmado**: `chunk_id` solo identifica con `(cited_id, chunk_id)`. Recomendado: issue de seguimiento para un ID compuesto.
2. **No observado** en la muestra (0 huecos); se mantiene la prueba de límite pero no hay evidencia de impacto.
3. **Confirmado**: secciones vacías aceptadas (4,24 % de los chunks).
4. **Confirmado y el más relevante**: ~37 % de artículos descartados por un solo párrafo largo; recomendado issue de seguimiento para dividir por oraciones, con cuidado de no sesgar la cobertura.
5. No se verificó `contar_chunks()` del spike con datos; queda como pendiente.
6. **Observado en la verificación manual:**
   - **Qué se vio:** las fórmulas se extraen como párrafos aparte y cortan frases (4 de 10 muestras), y hay un caso de sección perdida en la fuente (1 de 10). El texto en sí estuvo bien en las 10.
   - **Posible efecto:** C2 y C3 recibirían algunos chunks incompletos, y C3 alguna sección equivocada.
   - **Lo que no se ha medido:** cuántos chunks del corpus están afectados ni si esto cambia el F1.
   - **Recomendado:** contar en los 3 705 chunks los párrafos `EQUATION` y los saltos en la numeración de secciones, y valorar en un issue de seguimiento si conviene unir la frase cortada antes de fragmentar.

Límites: muestra de 200 citados; heurística de secciones sin validar; verificación manual de solo 10 casos de train.
