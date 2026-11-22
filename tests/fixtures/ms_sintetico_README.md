# Caso sintético M/S

Los 46 fragmentos fueron inventados para validar integración y despliegue.
La referencia se generó localmente con los checkpoints M/S y la revisión SciBERT
fijados en `config/ms_release.json`, Python 3.12 y CPU. No representa una etiqueta
científica correcta ni mide calidad del modelo; comprueba concordancia numérica
entre la inferencia local y la nube. Tolerancia absoluta de probabilidades: 0.005.

Puede enviarse al endpoint público sin transmitir el caso TRAIN del equipo.
El caso TRAIN privado se mantiene local y no fue enviado durante este despliegue.
