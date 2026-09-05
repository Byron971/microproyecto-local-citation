/* Lógica del tablero: consulta la API y dibuja tanto las recomendaciones del
 * modelo como la información del estudio de los datos.
 *
 * Ningún dato está escrito a mano en el frontend. Todo lo que se ve, incluidas
 * las cifras del panel de datos, llega desde el backend: si cambian los datos
 * o el modelo, el tablero cambia sin tocar este archivo.
 */

const { PALETA, barrasHorizontales, barrasVerticales, histograma, histogramasSuperpuestos, lineas, leyenda, formatearNumero } = window.Graficas;

const NOMBRES_PARTICION = { train: "Entrenamiento", val: "Validación", test: "Prueba" };

// Estado compartido: la última respuesta del modelo y el ejemplo cargado, para
// poder resaltar la cita correcta cuando se conoce.
const estadoTablero = {
  recomendaciones: [],
  citaCorrecta: null,
};

/* ---------------------------------------------------------------- utilidades */

function elemento(id) {
  return document.getElementById(id);
}

function decimal(valor, digitos = 4) {
  return valor.toLocaleString("es-CO", {
    minimumFractionDigits: digitos,
    maximumFractionDigits: digitos,
  });
}

function porcentaje(valor, digitos = 1) {
  return `${valor.toLocaleString("es-CO", {
    minimumFractionDigits: digitos,
    maximumFractionDigits: digitos,
  })} %`;
}

/** Construye una tabla a partir de columnas declarativas. */
function tabla(contenedor, columnas, filas) {
  contenedor.innerHTML = "";

  const tablaElemento = document.createElement("table");

  const encabezado = document.createElement("thead");
  const filaEncabezado = document.createElement("tr");

  columnas.forEach((columna) => {
    const celda = document.createElement("th");
    celda.textContent = columna.titulo;
    if (columna.numero) celda.className = "numero";
    filaEncabezado.appendChild(celda);
  });

  encabezado.appendChild(filaEncabezado);
  tablaElemento.appendChild(encabezado);

  const cuerpo = document.createElement("tbody");

  filas.forEach((fila) => {
    const filaElemento = document.createElement("tr");

    columnas.forEach((columna) => {
      const celda = document.createElement("td");
      if (columna.numero) celda.className = "numero";

      const contenido = columna.valor(fila);

      if (contenido instanceof Node) {
        celda.appendChild(contenido);
      } else {
        celda.textContent = contenido;
      }

      filaElemento.appendChild(celda);
    });

    cuerpo.appendChild(filaElemento);
  });

  tablaElemento.appendChild(cuerpo);
  contenedor.appendChild(tablaElemento);
}

/** Dibuja las tarjetas de cifras destacadas. */
function cifras(contenedor, entradas) {
  contenedor.innerHTML = "";

  entradas.forEach((entrada) => {
    const tarjeta = document.createElement("div");
    tarjeta.className = "cifra";

    const valor = document.createElement("div");
    valor.className = "valor";
    valor.textContent = entrada.valor;

    const etiqueta = document.createElement("div");
    etiqueta.className = "etiqueta";
    etiqueta.textContent = entrada.etiqueta;

    tarjeta.appendChild(valor);
    tarjeta.appendChild(etiqueta);
    contenedor.appendChild(tarjeta);
  });
}

/* ------------------------------------------------------------ recomendador */

function mostrarMensaje(texto, clase = "info") {
  const mensaje = elemento("mensaje");
  mensaje.textContent = texto;
  mensaje.className = `mensaje ${clase}`;
}

function limpiarMensaje() {
  const mensaje = elemento("mensaje");
  mensaje.textContent = "";
  mensaje.className = "mensaje";
}

function mostrarDetalle(recomendacion) {
  const detalle = elemento("detalle");
  detalle.innerHTML = "";

  const titulo = document.createElement("h3");
  titulo.textContent = recomendacion.titulo;

  const meta = document.createElement("p");
  meta.className = "meta";
  meta.textContent = `${recomendacion.paper_id} · similitud ${decimal(recomendacion.similitud)} · posición ${recomendacion.posicion}`;

  const resumen = document.createElement("p");
  resumen.className = "resumen";
  resumen.textContent = recomendacion.resumen || "Este artículo no tiene resumen.";

  detalle.appendChild(titulo);
  detalle.appendChild(meta);
  detalle.appendChild(resumen);
}

function renderRecomendaciones(recomendaciones) {
  const lista = elemento("resultados");
  lista.innerHTML = "";

  if (recomendaciones.length === 0) {
    lista.innerHTML = '<li class="vacio">El modelo no encontró artículos similares a ese texto.</li>';
    return;
  }

  recomendaciones.forEach((recomendacion) => {
    const item = document.createElement("li");

    const boton = document.createElement("button");
    boton.type = "button";
    boton.className = "resultado";

    const esCorrecta = recomendacion.paper_id === estadoTablero.citaCorrecta;

    boton.innerHTML = `
      <span class="posicion">${recomendacion.posicion}.</span>
      <span class="titulo">${esCorrecta ? "✓ " : ""}${recomendacion.titulo}
        <span class="paper-id">${recomendacion.paper_id}${esCorrecta ? " · cita correcta" : ""}</span>
      </span>
      <span class="puntaje">${decimal(recomendacion.similitud, 3)}</span>
    `;

    if (esCorrecta) {
      boton.style.background = "#dcfce7";
    }

    boton.addEventListener("click", () => {
      document
        .querySelectorAll(".resultado.seleccionado")
        .forEach((nodo) => nodo.classList.remove("seleccionado"));
      boton.classList.add("seleccionado");
      mostrarDetalle(recomendacion);
    });

    item.appendChild(boton);
    lista.appendChild(item);
  });

  // El primer resultado se muestra de una vez: es el que el usuario quiere ver
  // y ahorra un clic en el caso más frecuente.
  mostrarDetalle(recomendaciones[0]);
  lista.querySelector(".resultado").classList.add("seleccionado");
}

async function recomendar() {
  const contexto = elemento("contexto").value.trim();

  if (!contexto) {
    mostrarMensaje("Escriba un contexto antes de pedir recomendaciones.", "error");
    return;
  }

  const boton = elemento("btn-recomendar");
  boton.disabled = true;
  mostrarMensaje("Consultando el modelo…");

  try {
    const respuesta = await fetch("/api/recomendar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        contexto,
        top_k: Number(elemento("top-k").value),
      }),
    });

    if (!respuesta.ok) {
      const detalle = await respuesta.json().catch(() => ({}));
      throw new Error(detalle.detail || `El backend respondió ${respuesta.status}`);
    }

    const datos = await respuesta.json();
    estadoTablero.recomendaciones = datos.recomendaciones;
    renderRecomendaciones(datos.recomendaciones);

    if (estadoTablero.citaCorrecta) {
      const posicion = datos.recomendaciones.findIndex(
        (r) => r.paper_id === estadoTablero.citaCorrecta
      );

      mostrarMensaje(
        posicion >= 0
          ? `La cita correcta apareció en la posición ${posicion + 1}.`
          : `La cita correcta no quedó entre los ${datos.recomendaciones.length} primeros resultados.`
      );
    } else {
      limpiarMensaje();
    }
  } catch (error) {
    mostrarMensaje(`No se pudo obtener la recomendación. ${error.message}`, "error");
    console.error(error);
  } finally {
    boton.disabled = false;
  }
}

async function cargarEjemplo() {
  const boton = elemento("btn-ejemplo");
  boton.disabled = true;

  try {
    const respuesta = await fetch("/api/ejemplo");

    if (!respuesta.ok) throw new Error(`El backend respondió ${respuesta.status}`);

    const ejemplo = await respuesta.json();

    elemento("contexto").value = ejemplo.texto;
    estadoTablero.citaCorrecta = ejemplo.cita_correcta;

    mostrarMensaje(
      `Ejemplo real del corpus. La cita correcta es «${ejemplo.titulo_correcto}».`
    );
  } catch (error) {
    mostrarMensaje(`No se pudo cargar el ejemplo. ${error.message}`, "error");
  } finally {
    boton.disabled = false;
  }
}

/* --------------------------------------------------- panel: datos y modelo */

function renderDatos(datos) {
  const { dataset, calidad, longitudes, terminos, similitud, integridad_particiones, mas_citados } = datos;

  cifras(elemento("cifras"), [
    { valor: formatearNumero(dataset.contextos), etiqueta: "Contextos de cita" },
    { valor: formatearNumero(dataset.articulos), etiqueta: "Artículos candidatos" },
    { valor: formatearNumero(dataset.particiones.train), etiqueta: "Consultas de entrenamiento" },
    { valor: formatearNumero(dataset.particiones.val), etiqueta: "Consultas de validación" },
    { valor: formatearNumero(dataset.particiones.test), etiqueta: "Consultas de prueba" },
  ]);

  /* --- longitudes --- */
  tabla(
    elemento("tabla-longitudes"),
    [
      { titulo: "Texto", valor: (f) => f.texto },
      { titulo: "Mediana", numero: true, valor: (f) => formatearNumero(Math.round(f.mediana)) },
      { titulo: "Percentil 95", numero: true, valor: (f) => formatearNumero(Math.round(f.percentil_95)) },
      { titulo: "Máximo", numero: true, valor: (f) => formatearNumero(Math.round(f.maximo)) },
    ],
    longitudes.resumen
  );

  histograma(elemento("hist-contextos"), longitudes.histograma_contextos, {
    titulo: "Longitud de los contextos",
    etiquetaX: "Palabras",
    color: PALETA.azul,
  });

  histograma(elemento("hist-resumenes"), longitudes.histograma_resumenes, {
    titulo: "Longitud de los resúmenes",
    etiquetaX: "Palabras",
    color: PALETA.naranja,
    nota: "Eje recortado en el percentil 99 para que la cola larga no aplaste la distribución.",
  });

  /* --- calidad --- */
  tabla(
    elemento("tabla-calidad"),
    [
      { titulo: "Comprobación", valor: (f) => f.comprobacion },
      { titulo: "Casos", numero: true, valor: (f) => formatearNumero(f.cantidad) },
      {
        titulo: "",
        valor: (f) => {
          const marca = document.createElement("span");
          marca.className = f.cantidad === 0 ? "marca marca-ok" : "marca marca-aviso";
          marca.textContent = f.cantidad === 0 ? "correcto" : "revisar";
          return marca;
        },
      },
    ],
    calidad
  );

  tabla(
    elemento("tabla-integridad"),
    [
      { titulo: "Particiones", valor: (f) => f.particiones },
      { titulo: "Citantes", numero: true, valor: (f) => formatearNumero(f.citantes_compartidos) },
      { titulo: "Pares", numero: true, valor: (f) => formatearNumero(f.pares_compartidos) },
    ],
    integridad_particiones
  );

  /* --- términos --- */
  barrasHorizontales(
    elemento("graf-unigramas"),
    terminos.unigramas.map((t) => ({ etiqueta: t.termino, valor: t.frecuencia })),
    { titulo: "Palabras más frecuentes", color: PALETA.azul, anchoEtiqueta: 130 }
  );

  barrasHorizontales(
    elemento("graf-bigramas"),
    terminos.bigramas.map((t) => ({ etiqueta: t.termino, valor: t.frecuencia })),
    { titulo: "Bigramas más frecuentes", color: PALETA.morado, anchoEtiqueta: 160 }
  );

  /* --- señal léxica --- */
  elemento("ayuda-similitud").textContent =
    `Sobre una muestra de ${formatearNumero(similitud.muestra)} consultas se compara la similitud TF-IDF del ` +
    "contexto con el artículo que realmente se citó y con un artículo tomado al azar.";

  elemento("destacado-similitud").innerHTML =
    `El artículo citado obtiene mayor similitud que el aleatorio en <strong>${porcentaje(similitud.porcentaje_positivo_mayor)}</strong> ` +
    `de los casos (media ${decimal(similitud.media_positivos, 4)} frente a ${decimal(similitud.media_negativos, 4)}). ` +
    "Existe señal léxica aprovechable, y eso es lo que justifica la línea base TF-IDF.";

  const contenedorSimilitud = elemento("graf-similitud");
  histogramasSuperpuestos(
    contenedorSimilitud,
    [
      { distribucion: similitud.histograma_negativos, color: PALETA.gris },
      { distribucion: similitud.histograma_positivos, color: PALETA.azul },
    ],
    { titulo: "Distribución de la similitud coseno", etiquetaX: "Similitud coseno" }
  );
  leyenda(contenedorSimilitud, [
    { nombre: "Artículo citado", color: PALETA.azul },
    { nombre: "Artículo al azar", color: PALETA.gris },
  ]);

  /* --- más citados --- */
  barrasHorizontales(
    elemento("graf-citados"),
    mas_citados.map((p) => ({ etiqueta: p.titulo, valor: p.contextos })),
    {
      titulo: "Artículos con más contextos de cita",
      color: PALETA.verde,
      anchoEtiqueta: 300,
      maximoEtiqueta: 60,
      nota: "Los diez artículos más citados del corpus.",
    }
  );
}

function renderModelo(datos) {
  const modelo = datos.modelo;
  const punto = (k) => modelo.curva.find((p) => p.k === k);

  cifras(elemento("cifras-modelo"), [
    { valor: decimal(punto(10).recall, 4), etiqueta: "Recall@10 (validación)" },
    { valor: decimal(punto(10).mrr, 4), etiqueta: "MRR@10 (validación)" },
    { valor: decimal(modelo.techo_recuperacion, 4), etiqueta: "Recall@100 · techo de la 1.ª etapa" },
    { valor: formatearNumero(modelo.vocabulario), etiqueta: "Términos en el vocabulario" },
    { valor: formatearNumero(modelo.consultas), etiqueta: "Consultas evaluadas" },
  ]);

  const contenedorCurva = elemento("graf-curva");
  lineas(
    contenedorCurva,
    [
      {
        nombre: "Recall@K",
        color: PALETA.azul,
        puntos: modelo.curva.map((p) => ({ x: p.k, y: p.recall })),
      },
      {
        nombre: "MRR@K",
        color: PALETA.naranja,
        puntos: modelo.curva.map((p) => ({ x: p.k, y: p.mrr })),
      },
    ],
    { etiquetaX: "Profundidad del ranking (K)", etiquetaY: "Valor de la métrica" }
  );
  leyenda(contenedorCurva, [
    { nombre: "Recall@K", color: PALETA.azul },
    { nombre: "MRR@K", color: PALETA.naranja },
  ]);

  tabla(
    elemento("tabla-curva"),
    [
      { titulo: "K", numero: true, valor: (f) => f.k },
      { titulo: "Recall@K", numero: true, valor: (f) => decimal(f.recall) },
      { titulo: "MRR@K", numero: true, valor: (f) => decimal(f.mrr) },
    ],
    modelo.curva
  );

  const recall10 = punto(10).recall;
  const recall100 = punto(100).recall;
  const mrr10 = punto(10).mrr;
  const mrr100 = punto(100).mrr;
  const crecimientoMrr = ((mrr100 - mrr10) / mrr10) * 100;

  elemento("lectura-modelo").innerHTML = `
    <p>
      Al pasar de K=10 a K=100 el Recall <strong>se duplica</strong>
      (${decimal(recall10)} → ${decimal(recall100)}) mientras el MRR apenas se mueve
      (${decimal(mrr10)} → ${decimal(mrr100)}, un ${porcentaje(crecimientoMrr)}). Los artículos
      recuperados entre las posiciones 10 y 100 quedan tan abajo que casi no aportan al ranking.
    </p>
    <p>
      Ese contraste es exactamente el escenario donde un reordenamiento supervisado aporta valor:
      no necesita encontrar nada nuevo, solo <strong>subir lo que la primera etapa ya recuperó</strong>.
      La brecha entre Recall@100 y MRR@100 cuantifica el margen disponible.
    </p>
    <p>
      Recall@100 = <strong>${decimal(recall100)}</strong> es además el <strong>techo del sistema completo</strong>.
      Como la segunda etapa solo reordena los candidatos que la primera recupera, ningún reordenador
      puede superar ese ${porcentaje(recall100 * 100)} mientras la recuperación siga siendo puramente léxica.
      Elevarlo exige actuar sobre la primera etapa, con representaciones semánticas.
    </p>
  `;
}

function renderNegativos(datos) {
  const negativos = datos.negativos;

  if (!negativos) {
    elemento("rejilla-negativos").innerHTML = `
      <section class="tarjeta ancha">
        <div class="aviso">
          El diagnóstico de negativos necesita los pares supervisados de <code>data/processed/</code>,
          que no están disponibles. Genérelos con <code>python -m src.data.make_processed</code> y
          recalcule el tablero con <code>python -m src.app.insights --force</code>.
        </div>
      </section>`;
    return;
  }

  const contenedorSimilitud = elemento("graf-similitud-negativos");
  barrasVerticales(
    contenedorSimilitud,
    [
      { etiqueta: "Positivos", valor: negativos.similitud_media.positivos, color: PALETA.azul },
      { etiqueta: "Negativos aleatorios", valor: negativos.similitud_media.aleatorios, color: PALETA.gris },
      { etiqueta: "Negativos duros", valor: negativos.similitud_media.duros, color: PALETA.rojo },
    ],
    { formato: (v) => decimal(v, 4) }
  );

  barrasVerticales(
    elemento("graf-auc"),
    [
      { etiqueta: "Contra aleatorios", valor: negativos.auc.positivos_vs_aleatorios, color: PALETA.gris },
      { etiqueta: "Contra duros", valor: negativos.auc.positivos_vs_duros, color: PALETA.rojo },
    ],
    { formato: (v) => decimal(v, 4), maximoForzado: 1 }
  );

  const aucAleatorios = negativos.auc.positivos_vs_aleatorios;
  const aucDuros = negativos.auc.positivos_vs_duros;

  elemento("lectura-negativos").innerHTML = `
    <p>
      Los pares supervisados de <code>data/processed</code> toman sus negativos por muestreo uniforme
      sobre todo el corpus. En producción, en cambio, el reordenador solo recibe los
      ${negativos.top_n} candidatos que devuelve TF-IDF, y todos ellos son temáticamente cercanos a
      la consulta.
    </p>
    <p>
      La diferencia no es sutil. Con los negativos aleatorios actuales, la similitud coseno
      <strong>por sí sola</strong> separa las clases con un AUC de <strong>${decimal(aucAleatorios)}</strong>:
      un clasificador entrenado sobre esos datos reportaría métricas excelentes sin haber aprendido nada útil.
      El ${porcentaje(negativos.aleatorios_sin_terminos_comunes)} de esos negativos no comparte
      ni un solo término con la consulta.
    </p>
    <p>
      Contra negativos duros el AUC cae a <strong>${decimal(aucDuros)}</strong>, por debajo de 0,5:
      el coseno queda <strong>peor que el azar</strong>, porque los negativos duros son en promedio
      <em>más</em> similares a la consulta (${decimal(negativos.similitud_media.duros)}) que los propios
      positivos (${decimal(negativos.similitud_media.positivos)}). Ahí es donde un reordenador supervisado
      tiene algo real que aprender.
    </p>
    <p>
      Medido sobre ${formatearNumero(negativos.consultas)} consultas de validación.
    </p>
  `;
}

/* ------------------------------------------------------------------ arranque */

function activarPestanas() {
  document.querySelectorAll(".pestana").forEach((pestana) => {
    pestana.addEventListener("click", () => {
      document.querySelectorAll(".pestana").forEach((p) => p.classList.remove("activa"));
      document.querySelectorAll(".panel").forEach((p) => p.classList.remove("activo"));

      pestana.classList.add("activa");
      elemento(pestana.dataset.panel).classList.add("activo");
    });
  });
}

function actualizarEstado(texto, clase) {
  elemento("estado-texto").textContent = texto;
  elemento("estado").querySelector(".punto").className = `punto ${clase}`;
}

async function iniciar() {
  activarPestanas();

  elemento("btn-recomendar").addEventListener("click", recomendar);
  elemento("btn-ejemplo").addEventListener("click", cargarEjemplo);

  // Si el usuario edita el texto, deja de tener sentido resaltar la cita del
  // ejemplo anterior: el contexto ya no es el mismo.
  elemento("contexto").addEventListener("input", () => {
    estadoTablero.citaCorrecta = null;
  });

  try {
    const [estadoRespuesta, insightsRespuesta] = await Promise.all([
      fetch("/api/estado"),
      fetch("/api/insights"),
    ]);

    if (!estadoRespuesta.ok || !insightsRespuesta.ok) {
      throw new Error("El backend aún está cargando el modelo.");
    }

    const estado = await estadoRespuesta.json();
    const datos = await insightsRespuesta.json();

    actualizarEstado(
      `Modelo listo · ${estado.modelo.modelo} · ${formatearNumero(estado.modelo.articulos)} artículos`,
      "punto-listo"
    );

    renderDatos(datos);
    renderModelo(datos);
    renderNegativos(datos);

    const fecha = new Date(datos.generado_en);
    elemento("pie-texto").textContent =
      `Información calculada el ${fecha.toLocaleString("es-CO")} · ` +
      `vocabulario de ${formatearNumero(estado.modelo.vocabulario)} términos · ` +
      `evaluación sobre la partición de ${NOMBRES_PARTICION[datos.modelo.particion] || datos.modelo.particion}.`;
  } catch (error) {
    actualizarEstado("No se pudo conectar con el backend", "punto-error");
    elemento("pie-texto").textContent = error.message;
    console.error(error);
  }
}

document.addEventListener("DOMContentLoaded", iniciar);
