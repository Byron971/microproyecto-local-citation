# Registro reproducible de checkpoints A4 (sin Test Gold)

**Estado al 15 de noviembre de 2026:** el código de los cuatro clasificadores
SciBERT-A/B y SPECTER-A/B (semilla 42) tiene manifiestos públicos con SHA-256
del checkpoint, pero los pesos `model.safetensors` están fuera de Git. El
archivo `config/checkpoint_registry.json` se construyó exclusivamente con esos
manifiestos versionados. Este registro **no significa que los modelos estén
disponibles, instalados o validados sobre Gold humano**.

## Primera etapa: localizar los pesos en el equipo personal (sin escribir ni descargar)

La búsqueda del 15-nov-2026 en el árbol Git, Releases y el Drive conectado
NO encontró los cuatro archivos A4; esto no descarta el disco donde se entrenó,
backups o almacenamiento S3 del usuario. Las carpetas de checkpoints de Drive
inspeccionadas eran de otros experimentos.

Desde **PowerShell, dentro de la carpeta del repositorio**, ejecutar:

```powershell
# Explorar los archivos safetensors en Documentos, sin modificar nada.
uv run python -m scripts.locate_a4_weights --roots "$env:USERPROFILE\Documents" --max-depth 15 --report artifacts/a4_busqueda_001.json

# Para consultar los paths locales de archivos verificados (no compartir informe público):
uv run python -m scripts.locate_a4_weights --roots "$env:USERPROFILE\Documents" --max-depth 15 --show-paths

# Si el entrenamiento se hizo en D:\, buscar ese disco SOLO si existe.
uv run python -m scripts.locate_a4_weights --roots "D:\" --max-depth 16 --max-candidates 500 --show-paths
```

No pasar una ruta que no exista; el comando rechaza raíces inexistentes. En
almacenamiento con muchos pesos el SHA puede requerir leer gigabytes; controlar
el límite `--max-candidates`. Si el límite se alcanza, el inventario registra
`search_complete=false` y debe repetirse sobre subcarpetas más específicas.
Una coincidencia por **nombre** NO cuenta: el programa compara **bytes completos
SHA-256** contra los cuatro fingerprints de `config/checkpoint_registry.json`.

Códigos de salida: `0` si encontró los cuatro SHA, `1` si faltan o la búsqueda
fue incompleta, `2` para errores de entradas/lectura/reportes. El flag
`--allow-missing` es **solo inventario** y NO certifica pesos. No usar
`--show-paths` en artefactos CI públicos: revelarían rutas privadas de Windows.

Si encuentra los cuatro pesos, conservarlos FUERA de Git. La herramienta
**NO copia, renombra ni sube** pesos y NO ejecuta Torch; después se pueden
preparar en el esquema esperado:
`proyecto_de_grado/artifacts/clasificacion_a4/corridas/<ID>/model.safetensors`,
y aplicar `src.app.restore_a4 --all` desde una carpeta local fuente donde
los cuatro estén organizados por ID. Primero ejecutar restore SIN `--apply`,
luego solo si todos los SHA coinciden usar `--apply`.

Si no se encuentran, solicitar únicamente acceso a respaldos propios
o buckets previamente autorizados. No reemplazar un SHA histórico con pesos
nuevos ni entrenar otro modelo diciendo que es la misma corrida.

## Recuperación técnica y comprobación estricta

En el equipo que ejecutó el entrenamiento A4, localizar
`proyecto_de_grado/artifacts/clasificacion_a4/corridas/`, que debería contener
`scibert_A_42/model.safetensors`, `scibert_B_42/model.safetensors`,
`specter_A_42/model.safetensors` y `specter_B_42/model.safetensors`.
No copiar sus archivos a Git. Verificar su procedencia contra el manifiesto
original, no crear nuevos pesos para aparentar que se recuperó la misma corrida.

```bash
# Inventario informativo: conserva código de salida 0 si solo faltan archivos
uv run python -m src.app.checkpoint_gate --permitir-faltantes

# Gate estricto: salida 0 SOLAMENTE si los cuatro pesos se encontraron y
# tienen SHA-256 idéntico al registro y al manifiesto histórico correspondiente.
uv run python -m src.app.checkpoint_gate \
  --base proyecto_de_grado/artifacts/clasificacion_a4/corridas

# Reporte agregado nuevo, para adjuntar a incidencia sin exponer corpus ni Gold
uv run python -m src.app.checkpoint_gate --permitir-faltantes \
  --reporte proyecto_de_grado/artifacts/auditorias/checkpoints_inventario.json
```

La ejecución estricta falla si algún archivo está ausente, alterado,
es un symlink, su manifiesto no coincide o la identidad encoder/entrada/semilla
no es la esperada. El inventario indica solo IDs, SHA esperado, SHA observado
y estado; no incluye textos de citas, etiquetas, credenciales o datos de test.

Una vez recuperados los pesos, todavía hay que verificar el tokenizer,
revisión del encoder, `input_spec_sha256`, serialización y capacidad RAM
**durante una inferencia real**. Este gate es condición necesaria, no suficiente.

## Separación con la investigación humana

Los cuatro registros proceden de entrenamiento con **etiquetas Haiku**
(`provisional_not_gold`). El gate no asigna funciones de cita, no certifica
anotación humana y no revela el conjunto Gold. Las métricas reportadas
anteriormente no se modifican.

## CI

`Verificar registro A4 sin pesos ni Gold` instala solo dependencias ligeras:
verifica los hashes esperados en manifiestos versionados, ejercita pruebas con
bytes sintéticos y permite que los archivos grandes sigan ausentes de Git.
El workflow deja de pasar si se manipula el registro, la estructura o la
proveniencia histórica. **CI verde no implica checkpoints disponibles**: para
eso ejecutar el gate estricto sobre la carpeta restaurada.
