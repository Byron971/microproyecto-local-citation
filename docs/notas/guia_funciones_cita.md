# Guía visual de funciones de cita

## Solicitud y alcance

El usuario pide aplicar a Ayuda el diseño de Detalles del análisis y usar un nombre más representativo. La pestaña se renombra «Funciones de cita»: contiene las nueve definiciones de la clasificación, no ayuda general de uso. La navegación superior Ayuda y «Cómo analizar una cita» mantienen su propósito y nombre.

El glosario y los detalles comparten la clase de superficie `result-info-surface`: blanco, borde, radio, espaciado de escritorio/móvil y estilo de introducción. La lista utiliza separadores discretos; en escritorio el término y su descripción quedan alineados en dos columnas; en móvil cada descripción sigue a su término. Se conserva Outfit/DM Sans y la paleta existente.

Cada término tiene un nombre orientativo en español y la etiqueta inglesa original, marcada `lang=en`, para relacionarla con las puntuaciones. Las nueve definiciones se reutilizan sin cambios desde `citationFunctions.ts`; no se cambian etiquetas, orden, clases o criterios del clasificador. Todas permanecen visibles sin acordeones, buscadores ni controles nuevos. No se añaden ejemplos que puedan interpretarse como validación científica.

Se conserva una lista descriptiva `dl/dt/dd` para asociar términos y definiciones, coherente con la [estructura de contenido de W3C](https://www.w3.org/WAI/tutorials/page-structure/content/). Las tres pestañas conservan roles, asociaciones y navegación de teclado siguiendo el [patrón W3C de pestañas](https://www.w3.org/WAI/ARIA/apg/patterns/tabs/): puntuación inicial, panel único, flechas, Inicio/Fin y entrada al panel con Tab. Cambiar pestaña no inicia solicitudes.

Este cambio es exclusivamente presentación frontend: se conservan Top-3, análisis asíncrono, consentimiento, proveedores, modelos, corpus y controles de consumo. El proyecto no obtiene evidencia científica adicional por mejorar el glosario.

## Verificación local

Build TypeScript/Vite correcto y 41 pruebas unitarias aprobadas. Las comprobaciones específicas de M/S/comercial verifican las nueve etiquetas inglesas y definiciones, nombres en español, igualdad de fondo/radio/espaciado con Detalles, panel único, teclado y ausencia de nuevas inferencias. Se corrigió la comprobación del panel oculto para usar `includeHidden` antes de registrar el resultado final.

Los seis recorridos M/S/comercial aprobaron en escritorio/móvil. Capturas del glosario revisadas en ambos tamaños; las nueve definiciones permanecen completas y los nombres largos se ajustan sin desbordamiento. Evidencia final separada en `artifacts/citation-guide-verified-local/`; los intentos anteriores con el selector incorrecto no son aceptación.

## Publicación y checklist

Pendiente de publicación y comprobación pública. Las pruebas locales no sustituyen el estado real publicado.

- [x] Pestaña renombrada a «Funciones de cita».
- [x] Misma superficie, jerarquía y separación que Detalles del análisis.
- [x] Nueve definiciones y etiquetas originales conservadas; nombres españoles orientativos.
- [x] Seis recorridos de pestañas M/S/comercial y capturas locales revisadas.
- [ ] Publicación frontend y confirmación de HTML, salud y servicios actuales.
- [ ] UI publicada con mocks y capturas de escritorio/móvil verificadas.

Estado general: T01–T03 disponibles; T04 pendiente por cuota; T05–T06 suspendidas por QLoRA; T07–T09 disponibles para M/S y comercial con familia abierta suspendida; T10 parcial; T11 conserva aceptación real anterior; T12 migración/retirada pendiente sin retirar ECS; T13 notas actualizadas y cierre documental final pendiente. El proyecto continúa parcialmente cumplido.
