# Registro reproducible de checkpoints A4 (sin Test Gold)

**Estado al 15 de noviembre de 2026:** el código de los cuatro clasificadores
SciBERT-A/B y SPECTER-A/B (semilla 42) tiene manifiestos públicos con SHA-256
del checkpoint, pero los pesos `model.safetensors` están fuera de Git. El
archivo `config/checkpoint_registry.json` se construyó exclusivamente con esos
manifiestos versionados. Este registro **no significa que los modelos estén
disponibles, instalados o validados sobre Gold humano**.

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
