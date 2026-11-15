"""UNICO modulo que importa `proyecto_de_grado.*` y `src.app.*`.

Reutiliza sin modificar los componentes existentes. Deuda transitoria: `proyecto_de_grado`
y `src` se importan como namespace desde la raiz del repo (pythonpath ../..)."""
from __future__ import annotations

import json
from pathlib import Path

from auditoria_corpus.dominio import perfil_seccion
from proyecto_de_grado.src.data import exportar_corpus_top3 as _exp
from proyecto_de_grado.src.data.integrar_acl import integrar_contexto
from proyecto_de_grado.src.data.preparar_preetiquetado import leer_exclusiones
from proyecto_de_grado.src.data.validar_splits import load_split_index
# DEUDA: `_leer_etiquetas` es privado; lo cubre el test de equivalencia con evaluar_calibracion.
from proyecto_de_grado.src.evaluation.top3_humano import (
    ProtocoloError, _leer_etiquetas, leer_casos, puntajes_top3)
from src.app.fragment_retrieval import recuperar_top3

from . import dominio

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
lexico = recuperar_top3
puntuar = puntajes_top3
leer_casos_s22 = leer_casos


def cargar_exclusiones(rutas=EXCLUSIONES) -> set[str]:
    excluidos: set[str] = set()
    for ruta in rutas:
        excluidos |= leer_exclusiones(Path(ruta))
    return excluidos


def cargar_gold_calibracion(origen: Path, carpeta: Path) -> dict:
    """Consenso (context_id, chunk_id) -> 0/1. Verifica manifiesto y SHA de la fuente."""
    doc, digest = leer_casos(origen)
    try:
        manifest = json.loads((carpeta / "manifiesto.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProtocoloError("Falta manifiesto de anotacion.") from exc
    if manifest.get("estado") != dominio.ETIQUETA_GOLD or manifest.get("sha256_fuente") != digest:
        raise ProtocoloError("El corpus ha cambiado despues de preparar las hojas.")
    esperado = {(c["context_id"], ch["chunk_id"]) for c in doc["casos"] for ch in c["chunks"]}
    a_p, b_p = carpeta / "anotador_a.csv", carpeta / "anotador_b.csv"
    if a_p.resolve() == b_p.resolve():
        raise ProtocoloError("Los anotadores no pueden usar el mismo archivo.")
    a = _leer_etiquetas(a_p, esperado, parcial=False)
    b = _leer_etiquetas(b_p, esperado, parcial=False)
    adj = _leer_etiquetas(carpeta / "adjudicacion_plantilla.csv", esperado, parcial=True)
    try:
        cons, _ = dominio.consenso(a, b, adj, esperado)
    except ValueError as exc:
        raise ProtocoloError(str(exc)) from exc
    return cons
