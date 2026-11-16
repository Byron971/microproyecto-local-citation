"""UNICO modulo que importa `proyecto_de_grado.*` y conoce sus rutas.

Deuda transitoria: `proyecto_de_grado` se importa como namespace desde la raiz del repo
(pythonpath ../..). Las rutas bajo `local_workflows/` no se versionan (.gitignore)."""
import csv
import glob
import json
from pathlib import Path

from auditoria_corpus import adaptador_proyecto_grado as _auditoria
from proyecto_de_grado.src.data.preparar_preetiquetado import leer_exclusiones
from proyecto_de_grado.src.data.validar_splits import load_split_index

from .seleccion_datos import Fuentes, _clase

REPO = Path(__file__).resolve().parents[4]
RAW = REPO / "data/raw"
ANOTACION = REPO / "proyecto_de_grado/anotacion"
HAIKU_2700 = REPO / "local_workflows/ANOTACION_UNICA_2700_CITAS_REALES_ANOTADO.csv"
SPLIT_V2 = REPO / "local_workflows/qlora_split_v2.json"
TEST_GOLD = ANOTACION / "test_gold/TEST_GOLD_2700_ANOTADO.csv"
TEST_GOLD_MANIFIESTO = ANOTACION / "test_gold/TEST_GOLD_2700_MANIFIESTO.csv"
GOLD_V2 = ANOTACION / "test_gold_v2/manifiesto_ids.csv"
GRUPO_GOLD_V2 = "testgold"  # el manifiesto tambien trae 20 filas `calibracion3`
JURADO = REPO / "v3_Jueces/jurado_18000_v3.csv"
# Salida de `anotacion_sonnet.consolidar` (scripts/anotar_sonnet.py consolidar).
ETIQUETAS_SONNET = ANOTACION / "sonnet/etiquetas_sonnet.csv"
REFERENCIA_GPT = REPO / "v3_Jueces/referencia_gpt_200.jsonl"
# Etiquetas QLoRA v2 de las 18.000 y de las 43.014 restantes (misma version del modelo).
PREDS_QLORA = (REPO / "local_workflows/qlora_18000_preds_v2.jsonl",
               *sorted(glob.glob(str(REPO / "local_workflows/subconjuntos_qlora/*_qlora_v2_preds.jsonl"))))
CACHE_OCL = _auditoria.CACHE
# Reutiliza sin modificar la integracion, el fragmentador (regla de chunks de A1) y la
# descarga de ACL OCL.
integrar = _auditoria.integrar
fragmentar = _auditoria.fragmentar
descargar_ocl = _auditoria.descargar_ocl
EXCLUSIONES = (
    ANOTACION / "ids_excluir_test_gold.txt",
    ANOTACION / "ids_piloto_historico_no_test_final.txt",
)


def cargar_papers(raw=RAW) -> dict:
    return json.loads((Path(raw) / "papers.json").read_text(encoding="utf-8-sig"))


def leer_csv(ruta: Path) -> list[dict]:
    if not Path(ruta).exists():
        raise FileNotFoundError(f"Falta el archivo de entrada: {ruta}")
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _fila_anotada(fila: dict) -> dict:
    """Etiqueta = funcion principal si es Evaluable; si no, el motivo de abstencion."""
    estado = (fila.get("¿Evaluable?") or "").strip()
    funcion = (fila.get("Función principal") or "").strip()
    if estado == "Evaluable":
        if not funcion:
            raise ValueError(f"Evaluable sin funcion principal: {fila.get('context_id')}")
        etiqueta = funcion
    elif estado in ("Ambiguo", "No evaluable"):
        etiqueta = estado
    else:
        raise ValueError(f"Estado de evaluabilidad desconocido {estado!r}: {fila.get('context_id')}")
    return {"context_id": fila["context_id"], "etiqueta": etiqueta,
            "titulo": fila.get("Título citado", ""), "abstract": fila.get("Resumen citado", "")}


class FuentesProyectoGrado:
    def __init__(self, raw=RAW, haiku=HAIKU_2700, split=SPLIT_V2, test_gold=TEST_GOLD,
                 manifiesto=TEST_GOLD_MANIFIESTO, gold_v2=GOLD_V2, exclusiones=EXCLUSIONES):
        self._raw, self._haiku, self._split = Path(raw), Path(haiku), Path(split)
        self._test_gold, self._manifiesto = Path(test_gold), Path(manifiesto)
        self._gold_v2, self._exclusiones = Path(gold_v2), tuple(exclusiones)

    def indice(self):
        idx = load_split_index(self._raw)
        return dict(idx.by_context), idx.contexts

    def filas_haiku(self):
        return [_fila_anotada(f) for f in leer_csv(self._haiku)]

    def split_entrenamiento(self):
        if not self._split.exists():
            raise FileNotFoundError(f"Falta el split de entrenamiento: {self._split}")
        doc = json.loads(self._split.read_text(encoding="utf-8"))
        return {k: list(doc[k]) for k in ("train", "val")}

    def filas_test_gold(self):
        anios = {f["context_id"]: f["anio_citante"] for f in leer_csv(self._manifiesto)}
        filas = []
        for f in leer_csv(self._test_gold):
            if f["context_id"] not in anios:
                raise ValueError(f"Contexto sin manifiesto: {f['context_id']}")
            filas.append({**_fila_anotada(f), "anio_citante": anios[f["context_id"]]})
        return filas

    def ids_gold_v2(self):
        return [f["context_id"] for f in leer_csv(self._gold_v2) if f["grupo"] == GRUPO_GOLD_V2]

    def exclusiones(self):
        excluidos: set[str] = set()
        for ruta in self._exclusiones:
            excluidos |= leer_exclusiones(Path(ruta))
        return excluidos

    def rutas(self):
        return {"haiku_2700": self._haiku, "split_entrenamiento": self._split,
                "test_gold": self._test_gold, "test_gold_manifiesto": self._manifiesto,
                "gold_v2_manifiesto": self._gold_v2,
                **{f"exclusiones_{i}": r for i, r in enumerate(self._exclusiones)}}


def _leer_jsonl(ruta) -> list[dict]:
    with open(ruta, encoding="utf-8") as f:
        return [json.loads(linea) for linea in f if linea.strip()]


def cargar_sonnet(ruta: Path = ETIQUETAS_SONNET) -> dict[str, dict]:
    """{context_id: {"label", "confianza"}} solo de filas Evaluable con una de las 9 clases.

    Vacio si el consolidado no existe (las fuentes siguen funcionando sin pista Sonnet)."""
    if not Path(ruta).exists():
        return {}
    salida = {}
    for fila in leer_csv(ruta):
        if (fila.get("¿Evaluable?") or "").strip() != "Evaluable":
            continue
        clase = _clase(fila.get("Función principal"))
        if clase:
            salida[fila["context_id"]] = {"label": clase,
                                          "confianza": (fila.get("Confianza") or "").strip()}
    return salida


def cargar_fuentes_104(fuentes: "FuentesProyectoGrado | None" = None) -> Fuentes:
    """Fuentes del issue #104: QLoRA v2, jurado, Haiku, GPT, contextos y exclusiones."""
    fp = fuentes or FuentesProyectoGrado()
    qlora = {}
    for ruta in PREDS_QLORA:
        for r in _leer_jsonl(ruta):
            qlora[r["context_id"]] = {"label": r["label"], "p": r["p"], "dist": r["dist"]}
    jurado = {f["context_id"]: {"voto": f["voto"], "acuerdo": int(f["jueces_de_acuerdo"]),
                                "qlora": f["qlora"]} for f in leer_csv(JURADO)}
    haiku = {f["context_id"]: f["etiqueta"] for f in fp.filas_haiku()}
    split = fp.split_entrenamiento()
    gpt = {r["context_id"]: r["etiqueta"] for r in _leer_jsonl(REFERENCIA_GPT)
           if r.get("estado") == "completed"}
    ids_gold = {f["context_id"] for f in leer_csv(fp._manifiesto)} | set(fp.ids_gold_v2())
    return Fuentes(qlora=qlora, jurado=jurado, haiku=haiku, haiku_train=set(split["train"]),
                   haiku_val=set(split["val"]), gpt=gpt, contextos=cargar_papers_contextos(fp._raw),
                   ids_gold=ids_gold, ids_excluidos=fp.exclusiones(), sonnet=cargar_sonnet())


def cargar_papers_contextos(raw=RAW) -> dict:
    return json.loads((Path(raw) / "contexts.json").read_text(encoding="utf-8-sig"))
