// Prueba de punta a punta de la página en un navegador simulado (jsdom).
// Simula la base compartida (db) con dos compañeros que ya terminaron la calibración.
const fs = require("fs");
const {JSDOM, VirtualConsole} = require("jsdom");
const {kAlpha} = require(process.argv[3]);
const html = fs.readFileSync(process.argv[2], "utf8");

const errores = [];
const vc = new VirtualConsole();
vc.on("jsdomError", e => errores.push(String(e.message || e)));
vc.on("error", e => errores.push(String(e)));

// --- base simulada: colecciones -> {docId: data}, con suscriptores ---
const store = {respuestas: {}, calibracion: {}};
const subs = {respuestas: [], calibracion: []};
const snap = col => ({docs: Object.entries(store[col]).map(([id, d]) => ({id, exists: true, data: () => d}))});
const notify = col => subs[col].forEach(cb => setTimeout(() => cb(snap(col)), 0));
const fakeDb = {
  collection: col => ({onSnapshot: (cb) => { subs[col].push(cb); setTimeout(() => cb(snap(col)), 0); return () => {}; }}),
  doc: path => { const [col, id] = path.split("/"); return {set: async data => { store[col][id] = JSON.parse(JSON.stringify(data)); notify(col); }}; }
};
const fakeUser = {id: async () => "u_me", profiles: async ids => Object.fromEntries([].concat(ids).map(i => [i, {name: {u_me: "Carlos", u_a: "Ana", u_b: "Beto"}[i] || ""}]))};

// datos de los compañeros: los 36 casos de calibración, con acuerdo parcial
const calib = JSON.parse(html.match(/const CALIB = (\[.*?\]);\r?\n/s)[1].replace(/<\\\//g, "</"));
const L = ["Background", "Evidence", "Application", "Comparison"];
const ansA = {}, ansB = {}, ansMe = {};
calib.forEach((it, i) => {
  ansA[it.id] = {l: L[i % 4], ms: 30000, d: false};
  ansB[it.id] = {l: i % 3 === 0 ? L[(i + 1) % 4] : L[i % 4], ms: 50000, d: i % 5 === 0};
  ansMe[it.id] = i % 4 === 2 ? "Gap" : L[i % 4];          // lo que la prueba va a responder en la página
});
store.calibracion.u_a = {a: ansA, fin: true, v: 1};
store.calibracion.u_b = {a: ansB, fin: true, v: 1};

const dom = new JSDOM(html, {runScripts: "dangerously", url: "https://ejemplo.test/#guia", virtualConsole: vc, pretendToBeVisual: true,
  beforeParse(w){ w.claude = {use: async n => n === "db" ? fakeDb : n === "user" ? fakeUser : null}; w.HTMLElement.prototype.scrollIntoView = () => {}; w.scrollTo = () => {}; }});
const w = dom.window, d = w.document;
const esperar = ms => new Promise(r => setTimeout(r, ms));
const click = el => el.dispatchEvent(new w.MouseEvent("click", {bubbles: true}));
let fallos = 0;
const check = (cond, msg) => { console.log((cond ? "OK   " : "FALLA") + " " + msg); if (!cond) fallos++; };

(async () => {
  await esperar(100);
  // 1) guía
  check(d.querySelectorAll("#classes .cls").length === 9, "la guía muestra las 9 funciones");
  check(d.querySelector("#classes .chip").textContent.includes("→"), "las señales salen en inglés → español");

  // 2) práctica: responder un caso
  click(d.querySelector("#t-practicar"));
  check(!d.querySelector("#v-practicar").hidden, "se abre la pestaña Practicar");
  check(!!d.querySelector("#v-practicar .es-box"), "aparece la traducción al español");
  check(d.querySelectorAll("#case mark.cita").length >= 2, "la CITA se resalta en inglés y en español");
  click(d.querySelector('#case .opt[data-k="Background"]'));
  await esperar(50);
  check(!!d.querySelector("#case .fb"), "tras responder aparece la explicación");
  check(!!d.querySelector("#case .passage .sig"), "se subraya la frase clave");
  check(Object.keys((store.respuestas.u_me || {}).a || {}).length === 1, "la respuesta de práctica se guarda en la base compartida");
  click(d.querySelector("#case [data-act=toggle-es]"));
  check(!d.querySelector("#v-practicar .es-box"), "el botón oculta la traducción");
  click(d.querySelector("#case [data-act=toggle-es]"));

  // 3) calibración: los resultados no se ven antes de terminar
  click(d.querySelector("#t-calibracion"));
  check(d.querySelectorAll("#cgrid .cnum").length === 36, "la calibración tiene 36 casos");
  check(!d.querySelector("#cresults").textContent.includes("Krippendorff"), "no se ven resultados del equipo antes de terminar");
  check(d.querySelector("#c-fin").disabled, "no se puede terminar sin responder todo");
  for (let i = 0; i < calib.length; i++){
    click(d.querySelector(`#ccase .opt[data-ck="${ansMe[calib[i].id]}"]`));
    await esperar(5);
    if (i === 3){ const cb = d.querySelector("#c-dud"); cb.checked = true; cb.dispatchEvent(new w.Event("change", {bubbles: true})); }
    if (i < calib.length - 1) click(d.querySelector("#c-next"));
  }
  await esperar(50);
  check(!d.querySelector("#c-fin").disabled, "con las 36 respuestas se habilita Terminar");
  click(d.querySelector("#c-fin")); click(d.querySelector("#c-fin-yes"));
  await esperar(150);
  const mine = store.calibracion.u_me;
  check(mine && mine.fin === true && Object.keys(mine.a).length === 36, "la base guarda 36 respuestas y la ronda cerrada");
  check(mine && mine.a[calib[3].id].d === true, "se guarda la marca de dudas");
  check(d.querySelectorAll("#ccase .opt:not([disabled])").length === 0, "tras terminar ya no se puede cambiar");

  // 4) α que muestra la página contra α calculado por fuera
  const units = calib.map(it => [ansA[it.id].l, ansB[it.id].l, ansMe[it.id]]);
  const esperado = kAlpha(units).toFixed(2).replace(".", ",");
  const kpi = d.querySelector("#cresults .kpi b").textContent;
  console.log("     α página =", kpi, "| α esperado =", esperado);
  check(kpi === esperado, "el α de la página coincide con el cálculo independiente");
  check(d.querySelector("#cresults").textContent.includes("3") , "cuenta 3 personas que terminaron");
  check(d.querySelectorAll("#cresults td[data-pair]").length === 3, "muestra κ para las 3 parejas");
  check([...d.querySelectorAll("#cresults td[data-pair]")].some(td => td.textContent.includes("Carlos (tú)")), "las parejas muestran nombres");
  check(d.querySelectorAll("#cresults .disc-item").length > 0, "lista casos para discutir");
  check(!!d.querySelector("#ccase .fb .dist"), "tras terminar se ve la distribución del equipo en cada caso");

  // 5) resultados de práctica
  click(d.querySelector("#t-resultados"));
  check(d.querySelector("#kpis").textContent.includes("1/41"), "Resultados cuenta 1 de 41 en práctica");

  console.log(errores.length ? "ERRORES DE CONSOLA:\n" + errores.join("\n") : "Sin errores de consola");
  process.exit(fallos || errores.length ? 1 : 0);
})();
