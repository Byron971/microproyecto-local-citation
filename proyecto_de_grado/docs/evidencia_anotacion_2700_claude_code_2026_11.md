# Evidencia comunicada por el equipo: anotación de 2.700 citas mediante Claude Code

Fecha de incorporación documental: 3 de noviembre de 2026 (mensaje compartido por el equipo).
**Naturaleza de la fuente:** declaración del responsable y texto de instrucción que compartió; aún no hay logs de ejecución, snapshot del archivo original ni manifiesto de subagentes para reproducirla de forma independiente.

## Identificación

- **Responsable que confirmó el entrenamiento QLoRA:** Carlos (confirmación textual; no se aporta aún máquina, run ID, base model, parámetros ni artefactos).
- **Herramienta coordinadora de anotación:** Claude Code.
- **Modelo base/orquestador declarado:** Claude Sonnet 5.5.
- **Modelo para subagentes declarado:** Claude Haiku 5.5.
- **IDs públicos correspondientes de los modelos en Claude API:** `claude-sonnet-5-5` y `claude-haiku-5-5` (según documentación del fabricante). **No se ha cotejado contra logs qué ID y snapshot resolvió cada tarea.**
- **Archivo de entrada declarado:** `ANOTACION_UNICA_2700_CITAS_REALES.xlsx`, en OneDrive del equipo y copiado a un espacio de trabajo local. No se dispone de enlace estable, versión, hash ni tamaño.
- **Salida solicitada:** CSV con la misma estructura del Excel original y anotaciones en las columnas `¿Evaluable?`, `Función principal`, `Confianza`, `Justificación / duda`.
- **Categorías admitidas para evaluabilidad:** `Evaluable`, `Ambiguo`, `No evaluable`.
- **Nueve funciones principales:** Background; Gap; Basis; Comparison; Application; Improvement / Modification; Evidence; Identification of the Originator; Further Reading.
- **Taxonomía operativa:** la hoja `Guia` del libro Excel es parte del protocolo; sin versionarla, las nueve cadenas de etiquetas no bastan para reconstruir las decisiones.

## Texto compartido del prompt de orquestación

Se conserva el contenido compartido, con la ruta de usuario Linux **redactada** por privacidad. En la declaración original la ruta apuntaba a un archivo local bajo el directorio de Carlos; la ruta absoluta no es necesaria para replicar el experimento. La redacción introduce una diferencia documental explícita con el mensaje original:

> El archivo `<RUTA_LOCAL>/ANOTACION_UNICA_2700_CITAS_REALES.xlsx` contiene 2700 citas que deben ser clasificadas. Necesito que lances varios subagentes que usen haiku, para hacer esta anotacion, cada uno trabajando en su propia particion del dataset
>
> Se deben llenar las columnas "¿Evaluable?,    Función principal,    Confianza,    Justificación / duda" Los UNICOS valores aceptables para la columna ¿Evaluable? son Evaluable, Ambiguo, No evaluable
>
> Para la columna Funcion Principal:
> Background
> Gap
> Basis
> Comparison
> Application
> Improvement / Modification
> Evidence
> Identification of the Originator
> Further Reading
> , puedes ver qué significa cada uno de estos valores en la hoja "Guia" del excel
>
> Usa tu herramienta AskUserQuestion para asegurarme de que comprendes la tarea. El resultado final debe ser un archivo .csv con las anotaciones hechas, con la misma estructura que el archivo de excel original.

**Advertencia:** el mensaje anterior es la instrucción de la sesión Sonnet/Claude Code, no el system prompt ni el prompt expandido de cada subagente Haiku. Tampoco especifica particiones efectivas, semilla, temperatura, reintentos, columnas auxiliares, esquema de confianza ni adjudicación de errores. `AskUserQuestion` indica que pudieron intervenir aclaraciones humanas que no figuran en el mensaje.

## Estado de evidencia y acciones

1. **Confirmado por declaración:** Carlos entrenó QLoRA; se usó Claude Code con Sonnet 5.5 y subagentes Haiku 5.5; el insumo fue el Excel indicado y se pidió un CSV anotado.
2. **Pendiente de inspección:** Excel de OneDrive (hoja Guia, IDs y hash), CSV final y/o salidas parciales, logs/session transcript de Claude Code, mensajes a los subagentes, respuesta de AskUserQuestion y versionado de los modelos realmente invocados.
3. **Pendiente de cuantificar:** recuentos reales de Evaluable/Ambiguo/No evaluable, distribución de las nueve clases, duplicados, desacuerdos y proporción de revisión humana. Los 2.642 clasificados y 58 no evaluables son cifras de trabajo reportadas, no verificadas contra el nuevo Excel y CSV aquí.
4. **Implicación metodológica:** las etiquetas de los LLM son anotación automática; no equivalen por sí mismas a validación humana del 15 %. Un Test Gold de 2015 sigue requiriendo doble anotación humana independiente y adjudicación.

Referencias públicas de modelos: https://platform.claude.com/docs/en/models/overview

**No se ejecutó la anotación, no se recalcularon métricas ni se alteraron datasets al incorporar esta evidencia documental.**
