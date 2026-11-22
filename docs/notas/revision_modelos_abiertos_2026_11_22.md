# Revisión de modelos abiertos existentes — 22 de noviembre de 2026

## Conclusión corregida

El proyecto sí tiene desarrolladas las dos primeras familias: encoders SciBERT ajustados (M/S) y clasificadores generativos abiertos de 7–8B. No es correcto describir la segunda familia como inexistente. Lo pendiente es su disponibilidad para nuevas inferencias y su integración en la aplicación pública. M/S siguen siendo SciBERT de aproximadamente 110 millones de parámetros cada uno; no son los modelos de 7–8B.

## Evidencia revisada

- `proyecto_de_grado/notebooks/jueces_open_weight.ipynb`: implementación v3 de Qwen/Qwen2.5-7B-Instruct y meta-llama/Llama-3.1-8B-Instruct. Código sin salidas guardadas en esta copia. Los carga con AutoModelForCausalLM, clasifica mediante puntuaciones de letras y tres rotaciones de opciones. Usa contexto, título y abstract recortado a 400 caracteres; no consume Top-3 en ese protocolo.
- `proyecto_de_grado/notebooks/jueces_llama_mistral_v1.ipynb`: versión anterior descartada; no utilizar como implementación definitiva.
- `proyecto_de_grado/notebooks/anotacion_test_gold.ipynb`: prepara anotación humana; no entrena ni sirve un clasificador.
- `notebooks/v3_Jueces/Notebook jueces_open_weight v3.ipynb`: copia con ejecución y salidas guardadas. Registra GPU A100 de 40 GB y corrida completa de ambos jueces. Esto es evidencia histórica, no una nueva ejecución realizada en esta revisión.
- `notebooks/v3_Jueces/juez_qwen_v3.jsonl` y `juez_llama_v3.jsonl`: se leyeron íntegramente para contar registros; cada uno contiene 18.000 líneas, 18.000 IDs únicos y distribuciones de longitud 11. Son nueve funciones más Ambiguo y No evaluable. No se auditó aquí la corrección de todas las etiquetas ni su calidad humana.
- Sus archivos `juez_*_v3_meta.json` identifican los modelos, tres rotaciones, hash de prompt, bf16 y las ejecuciones del 3 de noviembre. No fijan una revisión inmutable del modelo base.
- `notebooks/qlora-training/finetune_qlora_citas.ipynb`: código de ajuste QLoRA de Qwen2.5-7B-Instruct, LoRA r=16, alpha=32, cuantización NF4 de 4 bits. Guarda/carga `qlora_citas_adapter_v1/`. Esta copia no tiene salidas ejecutadas.
- `notebooks/qlora-training/clasificar_citas_no_usadas_qlora.ipynb`: inferencia con el adaptador, sin entrenar, vía PeftModel.from_pretrained. También sin salidas en esta copia.
- En las rutas locales revisadas (`proyecto_de_grado`, `artifacts`, `tmp`, `notebooks`, `local_workflows` si existe) no se encontraron archivos `adapter_config.json`, `adapter_model.safetensors`, `adapter_model.bin` ni GGUF. No se inspeccionó almacenamiento remoto ni otras computadoras: no se concluye que el adaptador no exista fuera de estas rutas.
- `src/evaluation/commercial/providers_openweight.py` ya implementa un cliente OpenAI-compatible configurable mediante OPENWEIGHT_BASE_URL y OPENWEIGHT_MODEL. Hay además clientes comerciales OpenAI/Gemini/Cohere y configuración de ejemplo en `config/citation_eval.env.example`. Son utilidades de evaluación; no están conectadas como clasificadores del router M/S.

## Qué se puede reutilizar sin entrenar

1. M/S para encoder ajustado: ya cargados por el servicio científico.
2. Qwen 7B zero-shot: implementación y predicciones existentes. Requiere disponer de sus pesos base o de un servidor que los sirva; no necesita adaptador. Llama 8B es otra opción documentada.
3. Qwen 7B + QLoRA: reutilizable si se recuperan adaptador, base y configuración compatibles; no reentrenar automáticamente por la ausencia local del adaptador.
4. Cliente comercial existente: reutilizable para integración, aunque se deben verificar credenciales, modelo disponible y contrato de salida antes de considerarlo operativo.

El cliente OpenAI-compatible genera texto y no reproduce automáticamente el protocolo del notebook de puntuación de letras y tres rotaciones. Si se cambia a generación JSON, documentarlo como otro perfil de inferencia y no adjudicarle las métricas históricas del juez v3.

## Gaps reales

- Desarrollo de la familia abierta: existe; su integración y despliegue público no están verificados.
- Recursos: el notebook exige CUDA y usa bf16 completo en A100, o cuantización en GPU menor. No se puede asumir que funcione igual en el servicio CPU M/S de 6 GiB. Hace falta un destino de inferencia compatible; puede ser externo.
- Contrato: representar Ambiguo/No evaluable sin forzarlos a una de las nueve funciones. No confundir sus puntuaciones con las de M/S ni inventar probabilidades para una API que solo devuelva una clase.
- Datos de entrada: el juez existente usa título/resumen, mientras M/S usa entrada AB con fragmentos. Explicitar esa diferencia en interfaz y comparación.
- Integración: selector real, ejecución de proveedor, errores, timeout y configuración segura. No simular inferencia devolviendo las 18.000 etiquetas precalculadas para entradas nuevas.
- Evaluación: preetiquetado y referencias comerciales de desarrollo no equivalen a comparación final sobre Gold humano independiente.

La siguiente tarea es confirmar si existe un servidor Qwen/QLoRA disponible o recuperar su adaptador remoto. No hace falta desarrollar ni entrenar otro modelo para cubrir esta familia.
