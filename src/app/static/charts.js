/* Gráficas en SVG generadas a mano.
 *
 * Se dibujan sin librerías externas para que el tablero funcione sin conexión
 * y sin paso de compilación. Cada función recibe un contenedor y devuelve el
 * SVG ya insertado, con el mismo contrato: el ancho se adapta al contenedor
 * mediante viewBox y la altura se fija en el sistema de coordenadas interno.
 */

// Todo el módulo vive dentro de una IIFE porque este archivo se carga como
// script clásico y comparte el ámbito global con dashboard.js. Sin este
// cierre, cada constante de aquí (PALETA, formatearNumero, ...) se declararía
// en el ámbito global y chocaría con las que dashboard.js obtiene de
// window.Graficas, lo que aborta el segundo script con un SyntaxError.
(function () {

  const SVG_NS = "http://www.w3.org/2000/svg";

  const PALETA = {
    azul: "#2f6da1",
    azulOscuro: "#1c3a5c",
    naranja: "#ea580c",
    verde: "#16a34a",
    morado: "#7c3aed",
    ambar: "#d97706",
    rojo: "#b0413e",
    gris: "#94a3b8",
  };

  /** Crea un elemento SVG con sus atributos ya aplicados. */
  function crear(tag, atributos = {}) {
    const elemento = document.createElementNS(SVG_NS, tag);

    for (const [clave, valor] of Object.entries(atributos)) {
      elemento.setAttribute(clave, valor);
    }

    return elemento;
  }

  /** Inserta un texto en el SVG. */
  function texto(padre, contenido, atributos = {}) {
    const nodo = crear("text", { "font-size": 11, ...atributos });
    nodo.textContent = contenido;
    padre.appendChild(nodo);
    return nodo;
  }

  /**
   * Prepara el lienzo: limpia el contenedor, escribe un título opcional y
   * devuelve el elemento SVG listo para dibujar dentro.
   */
  function lienzo(contenedor, ancho, alto, titulo, nota) {
    contenedor.innerHTML = "";

    if (titulo) {
      const encabezado = document.createElement("div");
      encabezado.className = "grafica-titulo";
      encabezado.textContent = titulo;
      contenedor.appendChild(encabezado);
    }

    const svg = crear("svg", {
      viewBox: `0 0 ${ancho} ${alto}`,
      preserveAspectRatio: "xMidYMid meet",
      role: "img",
    });
    contenedor.appendChild(svg);

    if (nota) {
      const pie = document.createElement("div");
      pie.className = "grafica-nota";
      pie.textContent = nota;
      contenedor.appendChild(pie);
    }

    return svg;
  }

  /** Formatea un número con separador de miles en español. */
  function formatearNumero(valor) {
    return valor.toLocaleString("es-CO");
  }

  /** Recorta una cadena a un máximo de caracteres, con puntos suspensivos. */
  function recortar(cadena, maximo) {
    return cadena.length > maximo ? `${cadena.slice(0, maximo - 1)}…` : cadena;
  }

  /**
   * Barras horizontales, adecuadas cuando las etiquetas son textos largos
   * (términos frecuentes, títulos de artículos).
   *
   * datos: [{ etiqueta, valor }]
   */
  function barrasHorizontales(contenedor, datos, opciones = {}) {
    const {
      titulo = "",
      nota = "",
      color = PALETA.azul,
      anchoEtiqueta = 150,
      altoBarra = 22,
      formato = formatearNumero,
      maximoEtiqueta = 34,
    } = opciones;

    const ancho = 620;
    const margenDerecho = 60;
    const alto = datos.length * altoBarra + 14;

    const svg = lienzo(contenedor, ancho, alto, titulo, nota);

    const maximo = Math.max(...datos.map((d) => d.valor), 1);
    const anchoUtil = ancho - anchoEtiqueta - margenDerecho;

    datos.forEach((dato, indice) => {
      const y = indice * altoBarra + 7;
      const largo = (dato.valor / maximo) * anchoUtil;

      texto(svg, recortar(dato.etiqueta, maximoEtiqueta), {
        x: anchoEtiqueta - 8,
        y: y + altoBarra / 2 - 1,
        "text-anchor": "end",
        "dominant-baseline": "middle",
      });

      svg.appendChild(
        crear("rect", {
          x: anchoEtiqueta,
          y: y + 3,
          width: Math.max(largo, 1),
          height: altoBarra - 9,
          rx: 2,
          fill: color,
        })
      );

      texto(svg, formato(dato.valor), {
        x: anchoEtiqueta + largo + 7,
        y: y + altoBarra / 2 - 1,
        "dominant-baseline": "middle",
        class: "valor-barra",
      });
    });

    return svg;
  }

  /**
   * Barras verticales con eje X etiquetado. Se usa para comparaciones cortas
   * (particiones, poblaciones de negativos).
   *
   * datos: [{ etiqueta, valor, color? }]
   */
  function barrasVerticales(contenedor, datos, opciones = {}) {
    const {
      titulo = "",
      nota = "",
      color = PALETA.azul,
      formato = formatearNumero,
      maximoForzado = null,
    } = opciones;

    const ancho = 560;
    const alto = 250;
    const margen = { arriba: 24, derecha: 12, abajo: 46, izquierda: 12 };

    const svg = lienzo(contenedor, ancho, alto, titulo, nota);

    const maximo = maximoForzado ?? Math.max(...datos.map((d) => d.valor), 1);
    const anchoUtil = ancho - margen.izquierda - margen.derecha;
    const altoUtil = alto - margen.arriba - margen.abajo;
    const paso = anchoUtil / datos.length;
    const anchoBarra = Math.min(paso * 0.55, 90);

    // Línea base del eje X.
    svg.appendChild(
      crear("line", {
        x1: margen.izquierda,
        y1: margen.arriba + altoUtil,
        x2: ancho - margen.derecha,
        y2: margen.arriba + altoUtil,
        class: "eje",
      })
    );

    datos.forEach((dato, indice) => {
      const centro = margen.izquierda + paso * (indice + 0.5);
      const altura = Math.max((dato.valor / maximo) * altoUtil, 1);
      const y = margen.arriba + altoUtil - altura;

      svg.appendChild(
        crear("rect", {
          x: centro - anchoBarra / 2,
          y,
          width: anchoBarra,
          height: altura,
          rx: 3,
          fill: dato.color || color,
        })
      );

      texto(svg, formato(dato.valor), {
        x: centro,
        y: y - 7,
        "text-anchor": "middle",
        class: "valor-barra",
        "font-size": 12,
      });

      // Las etiquetas se parten en varias líneas para que quepan sin rotarlas.
      const palabras = String(dato.etiqueta).split(" ");
      palabras.forEach((palabra, linea) => {
        texto(svg, palabra, {
          x: centro,
          y: margen.arriba + altoUtil + 17 + linea * 13,
          "text-anchor": "middle",
        });
      });
    });

    return svg;
  }

  /**
   * Histograma a partir de los bordes y conteos calculados en el backend.
   *
   * distribucion: { bordes: [...], conteos: [...] }
   */
  function histograma(contenedor, distribucion, opciones = {}) {
    const {
      titulo = "",
      nota = "",
      color = PALETA.azul,
      etiquetaX = "",
    } = opciones;

    const ancho = 560;
    const alto = 210;
    const margen = { arriba: 12, derecha: 12, abajo: 40, izquierda: 44 };

    const svg = lienzo(contenedor, ancho, alto, titulo, nota);

    const { bordes, conteos } = distribucion;
    const maximo = Math.max(...conteos, 1);
    const anchoUtil = ancho - margen.izquierda - margen.derecha;
    const altoUtil = alto - margen.arriba - margen.abajo;
    const anchoBarra = anchoUtil / conteos.length;

    // Malla horizontal con tres referencias: suficiente para leer alturas sin
    // saturar la gráfica.
    for (let i = 0; i <= 2; i += 1) {
      const valor = (maximo / 2) * i;
      const y = margen.arriba + altoUtil - (valor / maximo) * altoUtil;

      svg.appendChild(
        crear("line", {
          x1: margen.izquierda,
          y1: y,
          x2: ancho - margen.derecha,
          y2: y,
          class: "malla",
        })
      );

      texto(svg, formatearNumero(Math.round(valor)), {
        x: margen.izquierda - 6,
        y,
        "text-anchor": "end",
        "dominant-baseline": "middle",
        "font-size": 10,
      });
    }

    conteos.forEach((conteo, indice) => {
      const altura = (conteo / maximo) * altoUtil;

      svg.appendChild(
        crear("rect", {
          x: margen.izquierda + indice * anchoBarra,
          y: margen.arriba + altoUtil - altura,
          width: Math.max(anchoBarra - 1, 1),
          height: Math.max(altura, 0),
          fill: color,
          opacity: 0.85,
        })
      );
    });

    svg.appendChild(
      crear("line", {
        x1: margen.izquierda,
        y1: margen.arriba + altoUtil,
        x2: ancho - margen.derecha,
        y2: margen.arriba + altoUtil,
        class: "eje",
      })
    );

    // Cinco marcas en el eje X, tomadas de los bordes reales del histograma.
    const marcas = 5;
    for (let i = 0; i <= marcas; i += 1) {
      const posicion = i / marcas;
      const indiceBorde = Math.round(posicion * (bordes.length - 1));

      texto(svg, formatearNumero(Math.round(bordes[indiceBorde])), {
        x: margen.izquierda + posicion * anchoUtil,
        y: margen.arriba + altoUtil + 15,
        "text-anchor": "middle",
        "font-size": 10,
      });
    }

    if (etiquetaX) {
      texto(svg, etiquetaX, {
        x: margen.izquierda + anchoUtil / 2,
        y: alto - 6,
        "text-anchor": "middle",
        "font-size": 11,
      });
    }

    return svg;
  }

  /**
   * Dos histogramas superpuestos, para comparar distribuciones sobre el mismo
   * eje (similitud de positivos frente a negativos).
   */
  function histogramasSuperpuestos(contenedor, series, opciones = {}) {
    const { titulo = "", nota = "", etiquetaX = "" } = opciones;

    const ancho = 560;
    const alto = 220;
    const margen = { arriba: 12, derecha: 12, abajo: 40, izquierda: 44 };

    const svg = lienzo(contenedor, ancho, alto, titulo, nota);

    const maximoConteo = Math.max(...series.flatMap((s) => s.distribucion.conteos), 1);

    // Ambas series se dibujan sobre el mismo rango de X para que la comparación
    // sea legítima; si cada una usara su propio rango, la superposición engañaría.
    const minimoX = Math.min(...series.map((s) => s.distribucion.bordes[0]));
    const maximoX = Math.max(
      ...series.map((s) => s.distribucion.bordes[s.distribucion.bordes.length - 1])
    );

    const anchoUtil = ancho - margen.izquierda - margen.derecha;
    const altoUtil = alto - margen.arriba - margen.abajo;

    const escalaX = (valor) =>
      margen.izquierda + ((valor - minimoX) / (maximoX - minimoX || 1)) * anchoUtil;

    series.forEach((serie) => {
      const { bordes, conteos } = serie.distribucion;

      conteos.forEach((conteo, indice) => {
        const x0 = escalaX(bordes[indice]);
        const x1 = escalaX(bordes[indice + 1]);
        const altura = (conteo / maximoConteo) * altoUtil;

        svg.appendChild(
          crear("rect", {
            x: x0,
            y: margen.arriba + altoUtil - altura,
            width: Math.max(x1 - x0 - 0.5, 0.5),
            height: Math.max(altura, 0),
            fill: serie.color,
            opacity: 0.55,
          })
        );
      });
    });

    svg.appendChild(
      crear("line", {
        x1: margen.izquierda,
        y1: margen.arriba + altoUtil,
        x2: ancho - margen.derecha,
        y2: margen.arriba + altoUtil,
        class: "eje",
      })
    );

    for (let i = 0; i <= 5; i += 1) {
      const valor = minimoX + ((maximoX - minimoX) * i) / 5;

      texto(svg, valor.toFixed(2), {
        x: escalaX(valor),
        y: margen.arriba + altoUtil + 15,
        "text-anchor": "middle",
        "font-size": 10,
      });
    }

    if (etiquetaX) {
      texto(svg, etiquetaX, {
        x: margen.izquierda + anchoUtil / 2,
        y: alto - 6,
        "text-anchor": "middle",
        "font-size": 11,
      });
    }

    return svg;
  }

  /**
   * Líneas con marcadores y eje X categórico, para la curva de métricas frente
   * a la profundidad del ranking.
   *
   * series: [{ nombre, color, puntos: [{ x, y }] }]
   */
  function lineas(contenedor, series, opciones = {}) {
    const { titulo = "", nota = "", etiquetaX = "", etiquetaY = "" } = opciones;

    const ancho = 620;
    const alto = 290;
    const margen = { arriba: 16, derecha: 16, abajo: 46, izquierda: 48 };

    const svg = lienzo(contenedor, ancho, alto, titulo, nota);

    const todosY = series.flatMap((s) => s.puntos.map((p) => p.y));
    const maximoY = Math.max(...todosY, 0.1) * 1.12;

    const anchoUtil = ancho - margen.izquierda - margen.derecha;
    const altoUtil = alto - margen.arriba - margen.abajo;

    // El eje X es categórico (las profundidades evaluadas están espaciadas de
    // forma irregular). Usarlo así evita que los puntos de K pequeño se
    // amontonen ilegiblemente contra el origen.
    const categorias = series[0].puntos.map((punto) => punto.x);
    const paso = anchoUtil / Math.max(categorias.length - 1, 1);
    const escalaX = (indice) => margen.izquierda + indice * paso;
    const escalaY = (valor) => margen.arriba + altoUtil - (valor / maximoY) * altoUtil;

    for (let i = 0; i <= 4; i += 1) {
      const valor = (maximoY / 4) * i;
      const y = escalaY(valor);

      svg.appendChild(
        crear("line", {
          x1: margen.izquierda,
          y1: y,
          x2: ancho - margen.derecha,
          y2: y,
          class: "malla",
        })
      );

      texto(svg, valor.toFixed(2), {
        x: margen.izquierda - 7,
        y,
        "text-anchor": "end",
        "dominant-baseline": "middle",
        "font-size": 10,
      });
    }

    categorias.forEach((categoria, indice) => {
      texto(svg, `K=${categoria}`, {
        x: escalaX(indice),
        y: margen.arriba + altoUtil + 17,
        "text-anchor": "middle",
        "font-size": 10,
      });
    });

    series.forEach((serie) => {
      const puntos = serie.puntos
        .map((punto, indice) => `${escalaX(indice)},${escalaY(punto.y)}`)
        .join(" ");

      svg.appendChild(
        crear("polyline", {
          points: puntos,
          fill: "none",
          stroke: serie.color,
          "stroke-width": 2.5,
          "stroke-linejoin": "round",
          "stroke-linecap": "round",
        })
      );

      serie.puntos.forEach((punto, indice) => {
        svg.appendChild(
          crear("circle", {
            cx: escalaX(indice),
            cy: escalaY(punto.y),
            r: 4,
            fill: "#fff",
            stroke: serie.color,
            "stroke-width": 2.5,
          })
        );
      });

      // Solo se rotula el último punto de cada serie: rotular todos saturaría la
      // gráfica y el valor exacto ya está en la tabla que la acompaña.
      const ultimo = serie.puntos[serie.puntos.length - 1];
      texto(svg, `${serie.nombre} ${ultimo.y.toFixed(3)}`, {
        x: escalaX(serie.puntos.length - 1) - 6,
        y: escalaY(ultimo.y) - 12,
        "text-anchor": "end",
        "font-size": 11,
        fill: serie.color,
        "font-weight": 700,
      });
    });

    svg.appendChild(
      crear("line", {
        x1: margen.izquierda,
        y1: margen.arriba + altoUtil,
        x2: ancho - margen.derecha,
        y2: margen.arriba + altoUtil,
        class: "eje",
      })
    );

    if (etiquetaX) {
      texto(svg, etiquetaX, {
        x: margen.izquierda + anchoUtil / 2,
        y: alto - 6,
        "text-anchor": "middle",
        "font-size": 11,
      });
    }

    if (etiquetaY) {
      texto(svg, etiquetaY, {
        x: 12,
        y: margen.arriba + altoUtil / 2,
        "text-anchor": "middle",
        "font-size": 11,
        transform: `rotate(-90 12 ${margen.arriba + altoUtil / 2})`,
      });
    }

    return svg;
  }

  /** Construye una leyenda de colores debajo de una gráfica. */
  function leyenda(contenedor, entradas) {
    const bloque = document.createElement("div");
    bloque.className = "leyenda";

    entradas.forEach((entrada) => {
      const item = document.createElement("span");

      const muestra = document.createElement("i");
      muestra.style.background = entrada.color;

      item.appendChild(muestra);
      item.appendChild(document.createTextNode(entrada.nombre));
      bloque.appendChild(item);
    });

    contenedor.appendChild(bloque);
  }

  window.Graficas = {
    PALETA,
    barrasHorizontales,
    barrasVerticales,
    histograma,
    histogramasSuperpuestos,
    lineas,
    leyenda,
    formatearNumero,
  };

})();
