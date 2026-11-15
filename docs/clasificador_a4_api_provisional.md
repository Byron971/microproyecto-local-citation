# Clasificador A4 provisional de nueve funciones en FastAPI

## Capacidades

El nuevo `POST /api/clasificar-cita` solo sirve un **modelo SciBERT-A
genuinamente cargado** a partir de un checkpoint A4 autenticado por SHA-256.
La entrada A usa, **en el mismo orden y con el mismo truncamiento que el
entrenamiento**, `citation_context` con un `TARGETCIT`, título y abstract
del artículo citado. Reutiliza las funciones de
`clasificacion_funcion.dominio` y `clasificador_torch`, incluyendo la cabeza
`[CLS] → Linear(768, 9)`.

La taxonomía tiene nueve categorías:
Background, Gap, Basis, Comparison, Application, Improvement / Modification,
Evidence, Identification of the Originator y Further Reading.

**No se accede a las etiquetas humanas ni al Gold**. Este endpoint conserva
`training_labels=Haiku`, `validacion=provisional_no_gold_humano` y la
advertencia de que el softmax NO está calibrado como probabilidad de acierto.

## Requisitos obligatorios para inferencia real

- Debe existir `proyecto_de_grado/artifacts/clasificacion_a4/corridas/scibert_A_42/model.safetensors`
  **auténtico**, recuperado del equipo de entrenamiento. El hash esperado
  se registra en `config/checkpoint_registry.json` (PR #171) y también en
  `proyecto_de_grado/docs/evidencias_clasificacion_a4/scibert_A_42/manifiesto.json`.
- El snapshot `allenai/scibert_scivocab_uncased` debe existir con su
  revisión fijada y coincidir con
  `proyecto_de_grado/docs/evidencias_clasificacion_a4/manifiesto_modelo_scibert.json`.
  El tokenizador debe tener **exactamente** la huella archivada por A4.
- El intérprete que levanta FastAPI debe tener instalados los paquetes
  `clasificacion-funcion` y `recuperacion-densa`, junto con Torch,
  Transformers y Safetensors según sus lockfiles. El Dockerfile ligero del
  microproyecto **no** incluye esas dependencias.

La configuración es explícita; por defecto el endpoint responde HTTP 503.

```bash
APP_A4_ENABLED=true
APP_A4_RUN=proyecto_de_grado/artifacts/clasificacion_a4/corridas/scibert_A_42
APP_A4_EVIDENCE=proyecto_de_grado/docs/evidencias_clasificacion_a4/scibert_A_42/manifiesto.json
APP_A4_ENCODER_MANIFEST=proyecto_de_grado/docs/evidencias_clasificacion_a4/manifiesto_modelo_scibert.json
APP_A4_DEVICE=cpu
```

Esas variables se **exportan al proceso** que inicia FastAPI; copiarlas a
`config/runtime.env.example` no las activa. Ejecutar primero
`uv run python -m src.app.checkpoint_gate` con los cuatro checkpoints
recuperados para verificar procedencia; el loader realiza su propia
comprobación del peso seleccionado, manifiesto, revisión y tokenizer.
Nunca regenerar un peso nuevo y darle el nombre de la corrida histórica.

## Ejemplo de request

```json
{
  "contexto": "We use the graph representation introduced in TARGETCIT.",
  "cited_title": "Learning Graph Representations for Scientific Text",
  "cited_abstract": "We study representations and evaluate downstream tasks."
}
```

La respuesta devuelve la categoría elegida, su índice de 0 a 8,
las nueve `puntuaciones_softmax`, el modelo A4 exacto, la latencia del
modelo y un rótulo explícito de provisionalidad. El ejemplo anterior es
un texto ilustrativo, no una predicción ni un caso de evaluación.

## Límites e integración posterior

- Este PR implementa **solo entrada A**, no entrada B ni SPECTER. B requiere
  exactamente tres chunks del citado, el `perfil` de sección conforme
  `auditoria_corpus` y su checkpoint B, para evitar comparar mal las entradas.
- No ejecuta entrenamientos, no valida F1, no sirve el Gold ni cambia A4.
- La CI ligera usa una doble de pruebas (`FakeCT`) exclusivamente para
  verificar el contrato y que la preparación llama a la receta original;
  **no acredita que un modelo Torch haya inferido**.
- Falta recuperar el checkpoint y ejecutar el smoke en el mismo hardware de
  servicio, verificando memoria, latencia y resistencia a errores.
- Para usar el resultado en React se necesita una vista de clasificación
  con título y abstract del citado y rótulos de provisionalidad. El corpus
  S2.2 actual no contiene abstract, por lo que no se debe inventar uno.

La ausencia de anotaciones humanas no bloquea esta implementación técnica;
sí bloquea la certificación científica final.
