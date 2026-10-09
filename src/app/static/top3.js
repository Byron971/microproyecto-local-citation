"use strict";
/* Interfaz aislada del tablero anterior; siempre trata las entradas como texto. */
const $ = (id) => document.getElementById(id);
const ejemplo = {
  cited_id: "DEMO-SINTETICO",
  contexto: "The proposed graph neural architecture learns node representations TARGETCIT.",
  parrafos: [
    "Graph neural networks aggregate signals from local neighbors to learn representations of each node.",
    "Neural graph architectures combine message passing and shared embeddings across edges.",
    "Citation styles differ by scientific discipline, so references must be curated.",
    "This paper introduces a statistical approach to machine translation evaluation."
  ]
};
$("ejemplo").addEventListener("click", () => {
  $("cited-id").value = ejemplo.cited_id;
  $("contexto").value = ejemplo.contexto;
  $("parrafos").value = ejemplo.parrafos.join("\n\n");
  $("estado").className = "";
  $("estado").textContent = "Ejemplo sintético cargado. No es evidencia del corpus ni Test Gold.";
});
function mostrarFragmentos(fragmentos) {
  $("lista-resultados").replaceChildren();
  for (const frag of fragmentos) {
    const li = document.createElement("li");
    const strong = document.createElement("strong");
    strong.textContent = `${frag.chunk_id} · Posición ${frag.posicion}`;
    const p = document.createElement("p");
    p.className = "fragmento";
    p.textContent = frag.texto;
    const score = document.createElement("p");
    score.className = "puntaje";
    const indices = Array.isArray(frag.paragraph_indices)
      ? ` · Párrafos OCL ${frag.paragraph_indices.join(", ")}`
      : "";
    score.textContent = `BM25 = ${frag.puntaje_bm25.toFixed(4)} (no calibrado)${indices}`;
    li.append(strong, p, score);
    $("lista-resultados").appendChild(li);
  }
}

$("form-top3").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const contexto = $("contexto").value.trim();
  const cited_id = $("cited-id").value.trim();
  const partes = $("parrafos").value.split(/\n\s*\n/).map(p=>p.trim()).filter(Boolean);
  if (!contexto || !cited_id || !partes.length || partes.length > 100) {
    $("estado").className = "error";
    $("estado").textContent = "Escribe un contexto, un identificador y entre 1 y 100 párrafos.";
    return;
  }
  const parrafos = partes.map((texto,i)=>({chunk_id:`p${i+1}`,texto,seccion:null}));
  const boton = $("buscar");
  boton.disabled = true;
  $("estado").className = "";
  $("estado").textContent = "Calculando BM25 de fragmentos…";
  $("lista-resultados").replaceChildren();
  try {
    const respuesta = await fetch("/api/top3-fragmentos", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify({contexto,cited_id,parrafos})
    });
    const cuerpo = await respuesta.json();
    if (!respuesta.ok) {
      const detalle = typeof cuerpo.detail === "string" ? cuerpo.detail : "Revisa los límites y textos de entrada.";
      throw new Error(`HTTP ${respuesta.status}: ${detalle}`);
    }
    if (!cuerpo.fragmentos.length) {
      $("estado").textContent = "No hay coincidencias léxicas suficientes. No se inventaron fragmentos relevantes.";
    } else {
      $("estado").textContent = `Encontrados ${cuerpo.total_resultados} fragmentos de ${cuerpo.total_fragmentos_analizados} del artículo ${cuerpo.cited_id}.`;
    }
    mostrarFragmentos(cuerpo.fragmentos);
    $("clasificacion").textContent="Función de cita: no ejecutada; todavía no hay clasificador de nueve funciones validado.";
  } catch(error) {
    $("estado").className="error";
    $("estado").textContent=`No se completó la recuperación. ${error.message}`;
  } finally {
    boton.disabled=false;
  }
});

$("ejemplo-real").addEventListener("click", async () => {
  const boton = $("ejemplo-real");
  boton.disabled = true;
  $("estado").className = "";
  $("estado").textContent = "Consultando muestra de desarrollo ACL-200 + ACL OCL…";
  $("lista-resultados").replaceChildren();
  try {
    const listado = await fetch("/api/top3-corpus/ejemplos");
    const catalogo = await listado.json();
    if (!listado.ok || !catalogo.ejemplos?.length) {
      throw new Error(typeof catalogo.detail === "string" ? catalogo.detail : "No hay casos reales preparados.");
    }
    const id = catalogo.ejemplos[0].context_id;
    const respuesta = await fetch(`/api/top3-corpus/${encodeURIComponent(id)}`);
    const caso = await respuesta.json();
    if (!respuesta.ok) {
      throw new Error(typeof caso.detail === "string" ? caso.detail : "No se pudo leer la muestra real.");
    }
    $("contexto").value = caso.contexto;
    $("cited-id").value = caso.cited_id;
    $("parrafos").value = "";
    mostrarFragmentos(caso.fragmentos);
    $("estado").textContent = `Caso REAL de desarrollo: ${caso.context_id} · Artículo citado: ${caso.cited_id} · ${caso.total_resultados} de ${caso.total_fragmentos_analizados} fragmentos. Los fragmentos provienen de ACL OCL, no del campo manual de párrafos.`;
    $("clasificacion").textContent = "Clasificación no ejecutada. No existe aún relevancia humana Top-3 ni evaluación científica de este caso.";
  } catch (error) {
    $("estado").className = "error";
    $("estado").textContent = `No hay una muestra real disponible: ${error.message}`;
  } finally {
    boton.disabled = false;
  }
});
