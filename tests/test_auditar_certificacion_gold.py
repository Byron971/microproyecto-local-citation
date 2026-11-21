"""Pruebas sinteticas de integridad de consolidacion, sin leer el Test Gold real."""
import csv
from pathlib import Path

from scripts.auditar_certificacion_gold import auditar


def escribir(ruta: Path, registros: list[dict]):
    columnas = list(registros[0])
    with ruta.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columnas)
        writer.writeheader()
        writer.writerows(registros)


def preparar(tmp_path: Path):
    escribir(tmp_path / "concordancias.csv", [
        {"context_id": "a", "etiqueta_final": "Background", "Estado_A": "COMPLETO", "Estado_B": "COMPLETO"}])
    escribir(tmp_path / "una_anotacion.csv", [
        {"context_id": "b", "etiqueta_unica": "Evidence", "Estado_A": "COMPLETO", "Estado_B": "PENDIENTE"}])
    escribir(tmp_path / "discrepancia_opus.csv", [
        {"context_id": "c", "etiqueta_opus": "Gap", "acuerdo_opus": "Ninguno"}])
    escribir(tmp_path / "anotado_opus.csv", [
        {"context_id": "d", "Función principal (una)": "Comparison", "¿Evaluable?": "Evaluable"}])
    escribir(tmp_path / "test_gold_final.csv", [
        {"context_id": "a", "etiqueta": "Background", "evaluable": "True", "fuente": "concordancia"},
        {"context_id": "b", "etiqueta": "Evidence", "evaluable": "True", "fuente": "una_anotacion"},
        {"context_id": "c", "etiqueta": "Gap", "evaluable": "True", "fuente": "discrepancia_opus"},
        {"context_id": "d", "etiqueta": "Comparison", "evaluable": "True", "fuente": "solo_opus"},
    ])


def test_integridad_sin_certificacion(tmp_path):
    preparar(tmp_path)
    r = auditar(tmp_path)
    assert r["integridad_consolidacion"]
    assert r["certificacion_humana"] == "no_demostrada"
    assert r["total_gold"] == 4
    assert r["anotaciones_unicas_con_estado_pendiente"] == 1
    assert r["discrepancias_opus_sin_acuerdo_humano"] == 1
    assert r["concordancias_humanas_reportadas"] == 1
    assert len(r["sha256_archivos"]) == 5


def test_detecta_inconsistencia_etiqueta(tmp_path):
    preparar(tmp_path)
    p = tmp_path / "test_gold_final.csv"
    s = p.read_text(encoding="utf-8")
    p.write_text(s.replace("b,Evidence", "b,Gap"), encoding="utf-8")
    r = auditar(tmp_path)
    assert not r["integridad_consolidacion"]
    assert any("etiqueta_no_coincide_con_fuente" in x for x in r["errores"])


def test_detecta_ids_faltantes(tmp_path):
    preparar(tmp_path)
    p = tmp_path / "test_gold_final.csv"
    s = p.read_text(encoding="utf-8")
    p.write_text("\n".join(x for x in s.splitlines() if not x.startswith("d,")) + "\n", encoding="utf-8")
    r = auditar(tmp_path)
    assert not r["integridad_consolidacion"]
    assert any("IDs de Gold" in x for x in r["errores"])


def test_no_evaluable_opus(tmp_path):
    preparar(tmp_path)
    p = tmp_path / "anotado_opus.csv"
    p.write_text(p.read_text(encoding="utf-8").replace("Comparison,Evaluable", "Comparison,No evaluable"), encoding="utf-8")
    p = tmp_path / "test_gold_final.csv"
    p.write_text(p.read_text(encoding="utf-8").replace("d,Comparison,True", "d,No evaluable,False"), encoding="utf-8")
    r = auditar(tmp_path)
    assert r["integridad_consolidacion"]
    assert r["no_evaluable"] == 1
