# Identidad visual · Recomendación Local de Citas Académicas

Combinación elegida en el laboratorio de identidad: https://claude.ai/artifact/S6zEDkMoJJzQjQUM6ALTEb

**Dirección estética:** tecnológica y contemporánea, paleta «Índice». Azul eléctrico con verde agua sobre grises fríos. Precisa y actual, sin estridencias.

## Color

| Rol | HEX | Uso |
|---|---|---|
| Principal | `#2F4BE0` | Botones, enlaces, marca |
| Secundario | `#4A5568` | Metadatos, navegación |
| Acento | `#00A88F` | Etiquetas, señales |
| Fondo | `#F3F5FA` | Lienzo de la app |
| Superficie | `#FFFFFF` | Tarjetas, campos |
| Texto | `#121826` | Texto principal |

- Texto sobre botón principal: `#FFFFFF`
- Texto sobre acento: `#121826`

## Tipografía (Google Fonts)

Combinación sans serif geométrica.

- **Títulos:** Outfit, peso 500 (Medium), título principal de 29 px.
- **Texto:** DM Sans, peso 400; 600/700 para botones.

## Iconografía de interfaz

- Estilo de línea fina: trazo de 1,25 px, esquinas rectas, cuadrícula de 24 px.
- Conjunto base: buscar, documento, cita, enlace, filtro, guardar.

## Símbolo

- **Concepto:** monograma abstracto de la C. Una C gruesa y abierta con un punto en su apertura: la cita encuentra su referencia.
- **Tinta principal:** `#2F4BE0`. **Negativo:** `#F3F5FA` sobre `#121826`.
- Una sola tinta; probado a 24, 32 y 64 px.

Boceto SVG (viewBox 48×48):

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="48" height="48">
  <path d="M34.2 14.4A14 14 0 1 0 34.2 33.6" fill="none" stroke="#2F4BE0" stroke-width="6.5"/>
  <circle cx="37.6" cy="24" r="4" fill="#2F4BE0"/>
</svg>
```

## Contraste (WCAG AA, 4.5:1 para texto normal)

| Combinación | Relación | Resultado |
|---|---|---|
| Texto sobre fondo | 16.26:1 | Cumple |
| Texto sobre superficie | 17.73:1 | Cumple |
| Secundario (metadatos) sobre superficie | 7.53:1 | Cumple |
| Principal (enlaces) sobre superficie | 6.55:1 | Cumple |
| Botón principal (texto blanco) | 6.55:1 | Cumple |
| Etiqueta / botón de acento (texto `#121826`) | 5.91:1 | Cumple |
| Botón secundario | 7.53:1 | Cumple |
| Acento como texto sobre fondo | 2.75:1 | No cumple |

**Regla de uso:** el acento `#00A88F` se usa como relleno (etiquetas, señales) con texto `#121826`, nunca como color de texto sobre el fondo.
