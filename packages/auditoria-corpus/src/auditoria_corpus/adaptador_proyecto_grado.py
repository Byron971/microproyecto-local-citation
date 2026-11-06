"""UNICO modulo que importa `proyecto_de_grado.*`.

Deuda transitoria: `proyecto_de_grado` aun no es un paquete instalable y se
importa como namespace desde la raiz del repo. """
from __future__ import annotations

from pathlib import Path

from proyecto_de_grado.src.data import exportar_corpus_top3 as _exp
from proyecto_de_grado.src.data.integrar_acl import integrar_contexto
from proyecto_de_grado.src.data.preparar_preetiquetado import leer_exclusiones
from proyecto_de_grado.src.data.validar_splits import load_split_index
from proyecto_de_grado.scripts.spike_enlace_datos.medir_enlace import descargar_ocl as _d

from .reglas import ReglasChunk

REPO: Path = _exp.REPO
CACHE: Path = _exp.CACHE
RAW: Path = REPO / "data/raw"
EXCLUSIONES = (
    REPO / "proyecto_de_grado/anotacion/ids_excluir_test_gold.txt",
    REPO / "proyecto_de_grado/anotacion/ids_piloto_historico_no_test_final.txt",
)

fragmentar = _exp.fragmentar
integrar = integrar_contexto
cargar_indice = load_split_index

REGLAS = ReglasChunk(
    max_palabras=_exp.MAX_PALABRAS,
    max_parrafos=_exp.MAX_PARRAFOS_CHUNK,
    max_caracteres=_exp.MAX_CARACTERES,
)


def cargar_exclusiones(rutas=EXCLUSIONES) -> set[str]:
    excluidos: set[str] = set()
    for ruta in rutas:
        excluidos |= leer_exclusiones(Path(ruta))
    return excluidos


def descargar_ocl(acl_id: str, cache_dir: Path):
    """Paso de red: delega en el descargador existente del spike."""

    return _d(acl_id, cache_dir)
