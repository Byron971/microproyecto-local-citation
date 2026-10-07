// α de Krippendorff (nominal): admite varios anotadores y casos sin todas las respuestas.
// units: arreglo de casos; cada caso es la lista de etiquetas que le dieron los anotadores.
function kAlpha(units){
  const o = {}; let n = 0;
  units.forEach(vals => {
    const m = vals.length; if (m < 2) return;          // un caso con una sola respuesta no aporta pares
    for (let i = 0; i < m; i++) for (let j = 0; j < m; j++) if (i !== j){
      const key = vals[i] + "|" + vals[j]; o[key] = (o[key] || 0) + 1 / (m - 1);
    }
    n += m;
  });
  if (n < 2) return null;
  const nc = {}; for (const [k, v] of Object.entries(o)){ const c = k.split("|")[0]; nc[c] = (nc[c] || 0) + v; }
  let Do = 0; for (const [k, v] of Object.entries(o)){ const [a, b] = k.split("|"); if (a !== b) Do += v; } Do /= n;
  let De = 0; const cs = Object.keys(nc); for (const a of cs) for (const b of cs) if (a !== b) De += nc[a] * nc[b]; De /= n * (n - 1);
  return De === 0 ? 1 : 1 - Do / De;
}
// κ de Cohen entre dos anotadores, sobre los casos que ambos respondieron.
function cKappa(a, b){
  const ids = Object.keys(a).filter(k => b[k]);
  if (ids.length < 2) return null;
  let agree = 0; const ma = {}, mb = {};
  ids.forEach(k => { const x = a[k], y = b[k]; if (x === y) agree++; ma[x] = (ma[x] || 0) + 1; mb[y] = (mb[y] || 0) + 1; });
  const N = ids.length, po = agree / N;
  let pe = 0; for (const c of new Set([...Object.keys(ma), ...Object.keys(mb)])) pe += ((ma[c] || 0) / N) * ((mb[c] || 0) / N);
  return pe === 1 ? 1 : (po - pe) / (1 - pe);
}
if (typeof module !== "undefined") module.exports = {kAlpha, cKappa};
