// Prueba del cálculo de acuerdo entre anotadores (acuerdo.js).
// Uso: node test_acuerdo.js ..\taller\acuerdo.js
const {kAlpha, cKappa} = require(process.argv[2]);
const r = (x) => Math.round(x * 1000) / 1000;
let fallos = 0;
const check = (cond, msg) => { console.log((cond ? "OK   " : "FALLA") + " " + msg); if (!cond) fallos++; };

// 1) acuerdo perfecto: α y κ deben valer 1
check(kAlpha([["A","A"],["B","B"],["C","C"]]) === 1, "α = 1 con acuerdo perfecto");
check(cKappa({1:"A",2:"B",3:"C"}, {1:"A",2:"B",3:"C"}) === 1, "κ = 1 con acuerdo perfecto");

// 2) piloto real del equipo (20 casos, annotations/citation_function/annotator_a.csv frente a la
//    segunda anotación): src/evaluation/annotation.py reporta κ = 0,4839 en acuerdo/agreement_summary.json.
//    Los 8 desacuerdos son los de acuerdo/disagreements.csv, en el mismo orden de casos.
const A = {"1":"Bg","2":"Bg","3":"FR","4":"App","5":"Ev","6":"App","7":"Bg","8":"App","9":"Imp","10":"App","11":"App","12":"Bg","13":"Ev","14":"Bg","15":"Bg","16":"Ev","17":"Ev","18":"Bg","19":"Bg","20":"Imp"};
const B = {...A, "1":"FR","3":"Ev","8":"Imp","14":"Ev","16":"Bg","18":"Gap","19":"Cmp","20":"App"};
check(r(cKappa(A, B)) === 0.484, `κ del piloto = ${r(cKappa(A, B))} (esperado 0,484, igual que el script del equipo)`);

// La verificación exacta de α contra la π de Scott está en test_alpha.js.
process.exit(fallos ? 1 : 0);
