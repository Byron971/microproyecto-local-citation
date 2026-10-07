/* ---------- ronda de calibración ---------- */
const CALIB = /*__CALIB__*/[];
/*__ACUERDO__*/
const NV = "No válido";
const LSC = LS + "-cal";
let cal = {a: {}, fin: false};                      // mis respuestas: id -> {l, t, ms, d}
try { const v = JSON.parse(localStorage.getItem(LSC) || "null"); if (v && v.a) cal = v; } catch(e){}
function saveCal(){ try { localStorage.setItem(LSC, JSON.stringify(cal)); } catch(e){} }
let cidx = Math.max(0, CALIB.findIndex(i => !cal.a[i.id]));
let shownAt = Date.now(), lastShown = null;
let calTeam = {}, calFirst = true, cWriting = false, cAgain = false;

async function pushCal(){
  if (!db || !me || mode !== "sync") return;
  if (cWriting){ cAgain = true; return; }
  cWriting = true;
  try { await db.doc("calibracion/" + me).set({a: cal.a, fin: !!cal.fin, v: 1}); }
  catch(e){
    if (e && (e.code === "invalid_argument" || e.code === "not_granted" || e.code === "revoked")){ mode = "readonly"; renderStatus(); }
    else if (e && e.code === "unavailable"){ setTimeout(pushCal, 1200 + Math.random() * 1200); }
  }
  cWriting = false;
  if (cAgain){ cAgain = false; pushCal(); }
}
function subCal(){
  db.collection("calibracion").onSnapshot(snap => {
    const t = {};
    snap.docs.forEach(d => { if (d.exists){ const v = d.data(); if (v && v.a) t[d.id] = v; } });
    calTeam = t;
    if (calFirst){
      calFirst = false;
      const r = t[me]; let ch = false;
      if (r){
        for (const [k, v] of Object.entries(r.a || {})) if (!cal.a[k]){ cal.a[k] = v; ch = true; }
        if (r.fin && !cal.fin){ cal.fin = true; ch = true; }
      }
      if (ch) saveCal();
      const remote = (r && r.a) || {};
      if (Object.keys(cal.a).some(k => !remote[k]) || (cal.fin && !(r && r.fin))) pushCal();
    }
    renderCal();
  }, () => {});
}
function calView(){ const t = {...calTeam}; if (me) t[me] = {a: cal.a, fin: cal.fin}; return t; }
function median(xs){ if (!xs.length) return null; const s = [...xs].sort((a, b) => a - b); const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; }

function calDist(it, fin){
  const votes = fin.map(([u, v]) => v.a[it.id] && v.a[it.id].l).filter(Boolean);
  const c = {}; votes.forEach(v => c[v] = (c[v] || 0) + 1);
  return {votes, c, rows: Object.entries(c).sort((a, b) => b[1] - a[1]).map(([k, n]) =>
    `<div class="dist-row"><span>${esc(k === NV ? NV : CLS[k].es)}</span><div class="dist-bar" style="--c:var(${CLS[k] ? CLS[k].c : "--c1"})"><i style="width:${(n / votes.length * 100).toFixed(0)}%"></i></div><b>${n}</b></div>`).join("")};
}
function renderCal(){
  if (!CALIB.length) return;
  $("#cgrid").innerHTML = CALIB.map((it, i) =>
    `<button class="cnum${cal.a[it.id] ? " done" : ""}${i === cidx ? " cur" : ""}" data-ci="${i}" aria-label="Caso ${i + 1}">${i + 1}</button>`).join("");
  const it = CALIB[cidx], a = cal.a[it.id];
  if (lastShown !== it.id){ shownAt = Date.now(); lastShown = it.id; }   // el tiempo cuenta desde que se abre el caso
  const dis = cal.fin ? "disabled" : "";
  const opts = CLASSES.map(c => `<button class="opt${a && a.l === c.k ? " is-pick" : ""}" data-ck="${esc(c.k)}" ${dis}>${dot(c.k)}<span><strong>${esc(c.es)}</strong><small>${esc(c.k)}</small></span></button>`).join("")
    + `<button class="opt${a && a.l === NV ? " is-pick" : ""}" data-ck="${NV}" ${dis}><i class="dot" style="--c:var(--line)"></i><span><strong>No válido</strong><small>tabla, ruido o sin sentido</small></span></button>`;
  const done = CALIB.filter(i => cal.a[i.id]).length;
  let team = "";
  if (cal.fin){
    const fin = Object.entries(calView()).filter(([u, v]) => v && v.fin);
    const d = calDist(it, fin);
    if (d.votes.length >= 2) team = `<div class="fb"><h3>Respuestas del equipo en este caso (${d.votes.length})</h3><div class="dist">${d.rows}</div></div>`;
  }
  $("#ccase").innerHTML = `
    <div class="progress"><span>${done} de ${CALIB.length} respondidos</span><div class="bar"><i style="width:${(done / CALIB.length * 100).toFixed(1)}%"></i></div></div>
    <article class="sheet">
      <div class="sheet-meta"><span>Caso ${cidx + 1} de ${CALIB.length} · Calibración</span><span>${esc(it.id)}</span></div>
      ${passage({text: it.text, es: it.es}, false)}
      <p class="cited">Artículo citado: <em>${esc(it.title || "sin título")}</em><span class="tr">En español: ${esc(it.title_es || "")}</span></p>
    </article>
    <p class="ask">${cal.fin ? "Tu respuesta (la ronda está cerrada)" : "¿Qué función cumple la CITA?"}</p>
    <div class="opts">${opts}</div>
    <label class="dud"><input type="checkbox" id="c-dud" ${a && a.d ? "checked" : ""} ${(!a || cal.fin) ? "disabled" : ""}> Tengo dudas con este caso</label>
    ${team}
    <div class="nav">
      <button class="btn" id="c-prev" ${cidx === 0 ? "disabled" : ""}>← Anterior</button>
      <button class="btn${a ? " primary" : ""}" id="c-next" ${cidx === CALIB.length - 1 ? "disabled" : ""}>Siguiente →</button>
    </div>
    ${cal.fin ? "" : `<div class="panel"><p>${done < CALIB.length ? `Te faltan ${CALIB.length - done} casos. Cuando los completes podrás terminar la ronda.` : "Ya respondiste los 36. Al terminar, tus respuestas quedan fijas y se muestran los resultados del equipo."}</p><div class="row" id="c-fin-row"><button class="btn primary" id="c-fin" ${done < CALIB.length ? "disabled" : ""}>Terminar ronda</button></div></div>`}`;
  renderCalResults();
}
function calChoose(k){
  if (cal.fin) return;
  const it = CALIB[cidx], prev = cal.a[it.id];
  // el tiempo se guarda solo en la primera respuesta, con tope de 10 minutos
  const ms = prev ? prev.ms : Math.min(Date.now() - shownAt, 600000);
  cal.a[it.id] = {l: k, t: Date.now(), ms, d: prev ? !!prev.d : false};
  saveCal(); pushCal(); renderCal();
}
async function renderCalResults(){
  const el = $("#cresults");
  if (!cal.fin){ el.innerHTML = `<p class="note">Los resultados del equipo aparecen cuando termines la ronda, para que nadie se deje influir por las respuestas de los demás.</p>`; return; }
  const fin = Object.entries(calView()).filter(([u, v]) => v && v.fin);
  const units = CALIB.map(it => fin.map(([u, v]) => v.a[it.id] && v.a[it.id].l).filter(Boolean));
  const alpha = fin.length >= 2 ? kAlpha(units) : null;
  const lectura = alpha === null ? "Hace falta que al menos dos personas terminen la ronda."
    : alpha >= 0.8 ? "Confiable: el equipo puede anotar el Test Gold."
    : alpha >= 0.7 ? "Alcanza la meta de la propuesta (0,70), pero conviene discutir los casos con desacuerdo."
    : "Por debajo de la meta de 0,70: discutir los desacuerdos, ajustar la guía y repetir con casos nuevos.";
  // κ de Cohen por pareja
  const pares = [];
  for (let i = 0; i < fin.length; i++) for (let j = i + 1; j < fin.length; j++){
    const A = {}, B = {};
    Object.entries(fin[i][1].a).forEach(([k, v]) => A[k] = v.l);
    Object.entries(fin[j][1].a).forEach(([k, v]) => B[k] = v.l);
    pares.push({u: fin[i][0], w: fin[j][0], k: cKappa(A, B)});
  }
  // tiempo por caso (mediana de todas las respuestas)
  const tiempos = [];
  fin.forEach(([u, v]) => Object.values(v.a).forEach(x => { if (x && x.ms > 0) tiempos.push(x.ms); }));
  const med = median(tiempos);
  const horas = med ? (med * 180 / 3600000) : null;   // 180 juicios por persona en el escenario de 450 casos
  // casos con menos acuerdo o con dudas
  const casos = CALIB.map((it, i) => {
    const d = calDist(it, fin); const top = d.votes.length ? Math.max(...Object.values(d.c)) : 0;
    const dudas = fin.filter(([u, v]) => v.a[it.id] && v.a[it.id].d).length;
    return {it, i, d, agree: d.votes.length ? top / d.votes.length : 1, dudas};
  }).filter(x => x.d.votes.length >= 2 && (x.agree < 1 || x.dudas)).sort((a, b) => a.agree - b.agree || b.dudas - a.dudas);
  const nv = units.flat().filter(l => l === NV).length;
  let names = {};
  const ids = fin.map(([u]) => u);
  try { if (userNs && ids.length) names = await userNs.profiles(ids); } catch(e){}
  const who = u => (names[u] && names[u].name) ? names[u].name + (u === me ? " (tú)" : "") : (u === me ? "Tú" : "Integrante");
  const coma = x => x.toFixed(2).replace(".", ",");
  el.innerHTML = `
    <h2>Resultados de la calibración</h2>
    <div class="kpis">
      <div class="kpi"><b>${alpha === null ? "—" : coma(alpha)}</b><span>α de Krippendorff · meta 0,70</span></div>
      <div class="kpi"><b>${fin.length}</b><span>personas terminaron</span></div>
      <div class="kpi"><b>${med ? Math.round(med / 1000) + " s" : "—"}</b><span>mediana por caso${horas ? ` · ≈ ${horas.toFixed(1).replace(".", ",")} h para 180 casos` : ""}</span></div>
    </div>
    <div class="panel"><p>${esc(lectura)}</p>${nv ? `<p class="note">${nv} respuestas marcaron «No válido».</p>` : ""}</div>
    <div><h3>Acuerdo por pareja (κ de Cohen)</h3></div>
    <div class="tbl-wrap"><table>${pares.length
      ? `<thead><tr><th>Pareja</th><th class="num">κ</th></tr></thead><tbody>${pares.map(p => `<tr><td data-pair="${esc(p.u)}|${esc(p.w)}"></td><td class="num">${p.k === null ? "—" : coma(p.k)}</td></tr>`).join("")}</tbody>`
      : `<tbody><tr><td class="empty">Aparece cuando terminen al menos dos personas.</td></tr></tbody>`}</table></div>
    <div><h3>Casos para discutir (${casos.length})</h3></div>
    <div class="panel">${casos.length ? casos.slice(0, 15).map(x => `
      <div class="disc-item">
        <button class="linkbtn" data-ci="${x.i}">Caso ${x.i + 1} · ${Math.round(x.agree * 100)}% de acuerdo${x.dudas ? ` · ${x.dudas} con dudas` : ""}</button>
        <div class="dist">${x.d.rows}</div>
      </div>`).join("") : `<p class="note">Sin desacuerdos por ahora.</p>`}</div>
    <div class="panel">
      <h3>Copiar mis respuestas de calibración</h3>
      <textarea readonly>${esc("# Calibración — mis respuestas\n# id\tetiqueta\tsegundos\tdudas\n" + CALIB.filter(i => cal.a[i.id]).map(i => { const x = cal.a[i.id]; return `${i.id}\t${x.l}\t${Math.round((x.ms || 0) / 1000)}\t${x.d ? "sí" : "no"}`; }).join("\n"))}</textarea>
    </div>`;
  el.querySelectorAll("td[data-pair]").forEach(td => { const [u, w] = td.getAttribute("data-pair").split("|"); td.textContent = who(u) + " · " + who(w); });
}
document.addEventListener("click", e => {
  const t = e.target.closest("button"); if (!t) return;
  if (t.dataset.ci !== undefined){ cidx = +t.dataset.ci; renderCal(); return $("#ccase").scrollIntoView({block: "start"}); }
  if (t.dataset.ck) return calChoose(t.dataset.ck);
  if (t.id === "c-prev"){ cidx = Math.max(0, cidx - 1); return renderCal(); }
  if (t.id === "c-next"){ cidx = Math.min(CALIB.length - 1, cidx + 1); return renderCal(); }
  if (t.id === "c-fin"){ $("#c-fin-row").innerHTML = `<span class="note">Tus respuestas quedarán fijas.</span><button class="btn primary" id="c-fin-yes">Sí, terminar</button><button class="btn" id="c-fin-no">Seguir revisando</button>`; return; }
  if (t.id === "c-fin-no") return renderCal();
  if (t.id === "c-fin-yes"){ cal.fin = true; saveCal(); pushCal(); return renderCal(); }
});
document.addEventListener("change", e => {
  if (e.target.id !== "c-dud") return;
  const it = CALIB[cidx]; if (!cal.a[it.id] || cal.fin) return;
  cal.a[it.id].d = e.target.checked; saveCal(); pushCal();
});

