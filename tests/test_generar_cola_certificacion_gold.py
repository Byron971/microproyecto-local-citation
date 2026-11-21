"""Pruebas de cola privada; no usan anotaciones ni textos reales."""
import csv

from scripts.generar_cola_certificacion_gold import generar


def escribir(ruta, filas):
    with ruta.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)


def test_cola_sin_texto_y_sin_adjudicar(tmp_path):
    escribir(tmp_path / "concordancias.csv", [
        {"context_id": "a", "Estado_A": "COMPLETO", "Estado_B": "COMPLETO"}])
    escribir(tmp_path / "una_anotacion.csv", [
        {"context_id": "b", "Estado_A": "COMPLETO", "Estado_B": "PENDIENTE"}])
    escribir(tmp_path / "discrepancia_opus.csv", [
        {"context_id": "c", "acuerdo_opus": "Ninguno", "Estado_A": "COMPLETO", "Estado_B": "COMPLETO"}])
    escribir(tmp_path / "anotado_opus.csv", [{"context_id": "d", "Estado": "COMPLETO"}])
    filas = generar(tmp_path)
    assert len(filas) == 3  # B unica, C discrepancia, D Opus; A concordancia completa
    assert {x["tarea"] for x in filas} == {
        "segunda_anotacion_humana_independiente",
        "adjudicacion_humana_desacuerdo",
        "anotacion_humana_independiente",
    }
    assert all(x["etiqueta_adjudicada"] == "" for x in filas)
    assert all("Contexto original (inglés)" not in x for x in filas)
    assert all(x["estado_revision"] == "PENDIENTE" for x in filas)
