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
    for (const frag of cuerpo.fragmentos) {
      const li=document.createElement("li");
      const strong=document.createElement("strong");
      strong.textContent=`${frag.chunk_id} · Posición ${frag.posicion}`;
      const p=document.createElement("p"); p.className="fragmento"; p.textContent=frag.texto;
      const score=document.createElement("p"); score.className="puntaje";
      score.textContent=`BM25 = ${frag.puntaje_bm25.toFixed(4)} (no calibrado)`;
      li.append(strong,p,score);
      $("lista-resultados").appendChild(li);
    }
    $("clasificacion").textContent="Función de cita: no ejecutada; todavía no hay clasificador de nueve funciones validado.";
  } catch(error) {
    $("estado").className="error";
    $("estado").textContent=`No se completó la recuperación. ${error.message}`;
  } finally {
    boton.disabled=false;
  }
});
