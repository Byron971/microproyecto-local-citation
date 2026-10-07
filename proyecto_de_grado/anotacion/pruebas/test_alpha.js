const {kAlpha} = require(process.argv[2]);
// π de Scott calculado a mano para 2 anotadores con datos completos
function scottPi(x, y){
  const N = x.length; let d = 0; const c = {};
  x.forEach((v, i) => { if (v !== y[i]) d++; c[v] = (c[v]||0)+1; c[y[i]] = (c[y[i]]||0)+1; });
  const pe = Object.values(c).reduce((s, k) => s + (k/(2*N))**2, 0);
  return ((1 - d/N) - pe) / (1 - pe);
}
const casos = [
  [["a","a","b","b","d","c","c","c","e","d"], ["b","a","b","b","b","c","c","c","e","d"]],
  [["Bg","Bg","FR","App","Ev","App","Bg","App","Imp","App","App","Bg","Ev","Bg","Bg","Ev","Ev","Bg","Bg","Imp"],
   ["FR","Bg","Ev","App","Ev","App","Bg","Imp","Imp","App","App","Bg","Ev","Ev","Bg","Bg","Ev","Gap","Cmp","App"]],
];
let ok = true;
for (const [x, y] of casos){
  const N = x.length, a = kAlpha(x.map((v,i)=>[v,y[i]])), p = scottPi(x, y);
  const esperado = 1 - (1 - p) * (2*N - 1) / (2*N);
  const bien = Math.abs(a - esperado) < 1e-12; ok = ok && bien;
  console.log(`N=${N} α=${a.toFixed(4)} desde π=${esperado.toFixed(4)} ${bien ? "OK" : "FALLA"}`);
}
// 3 anotadores, un caso con respuesta faltante: no debe romperse y debe quedar entre -1 y 1
const tres = [["A","A","A"],["A","B","A"],["B","B"],["C","C","B"],["A","A","A"]];
const a3 = kAlpha(tres); console.log("3 anotadores con faltantes α=", a3.toFixed(4), a3 > -1 && a3 <= 1 ? "OK" : "FALLA");
// mutante: si se ignora el peso 1/(m-1), el resultado con 3 anotadores debe cambiar
const src = require("fs").readFileSync(process.argv[2], "utf8").replace("1 / (m - 1)", "1");
const mut = eval(src.replace("if (typeof module", "({kAlpha}); if (false && typeof module").split("({kAlpha});")[0] + "kAlpha");
console.log("mutante detectado:", Math.abs(mut(tres) - a3) > 1e-9 ? "sí" : "NO");
process.exit(ok ? 0 : 1);
