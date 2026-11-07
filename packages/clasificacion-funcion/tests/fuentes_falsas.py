"""Fuentes en memoria para probar servicio y CLI sin tocar el repo."""
from pathlib import Path


def _ctx(cid, citing, cited):
    return {"citing_id": citing, "refid": cited, "masked_text": f"texto de {cid} TARGETCIT fin"}


class FuentesFalsas:
    """train: t1..t4 (citantes P1..P4); val: v1 (P5); test 2015: e1..e4; 2014: d1; Gold v2: e1, e3, e5."""

    def __init__(self, tmp_path: Path | None = None):
        self.tmp = tmp_path
        self.ctx = {
            "t1": _ctx("t1", "P1", "A"), "t2": _ctx("t2", "P2", "B"),
            "t3": _ctx("t3", "P3", "C"), "t4": _ctx("t4", "P4", "A"),
            "v1": _ctx("v1", "P5", "A"),
            "e1": _ctx("e1", "P6", "A"), "e2": _ctx("e2", "P7", "D"), "e3": _ctx("e3", "P8", "E"),
            "e4": _ctx("e4", "P9", "F"), "e5": _ctx("e5", "P10", "G"), "d1": _ctx("d1", "P11", "H"),
        }
        self.split = {**{c: "train" for c in ("t1", "t2", "t3", "t4", "v1")},
                      **{c: "test" for c in ("e1", "e2", "e3", "e4", "e5", "d1")}}

    def indice(self):
        return dict(self.split), self.ctx

    def _fila(self, cid, etiqueta, **extra):
        return {"context_id": cid, "etiqueta": etiqueta, "titulo": f"titulo {cid}",
                "abstract": f"abstract {cid}", **extra}

    def filas_haiku(self):
        return [self._fila("t1", "Background"), self._fila("t2", "Gap"),
                self._fila("t3", "Ambiguo"), self._fila("t4", "Evidence"),
                self._fila("v1", "No evaluable")]

    def split_entrenamiento(self):
        return {"train": ["t1", "t2", "t3", "t4"], "val": ["v1"]}

    def filas_test_gold(self):
        return [self._fila("e1", "Basis", anio_citante="2015"),
                self._fila("e2", "Ambiguo", anio_citante="2015"),
                self._fila("e3", "Comparison", anio_citante="2015"),
                self._fila("e4", "Application", anio_citante="2015"),
                self._fila("d1", "Background", anio_citante="2014")]

    def ids_gold_v2(self):
        return ["e1", "e3", "e5"]

    def exclusiones(self):
        return {"e4"}

    def rutas(self):
        if self.tmp is None:
            return {}
        ruta = self.tmp / "entrada.csv"
        ruta.write_text("a,b\n", encoding="utf-8")
        return {"entrada": ruta}
