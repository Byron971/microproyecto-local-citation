"""Pruebas unitarias sin red, sin descargas ni costos."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from proyecto_de_grado.src.data.preetiquetar_local import (
    ETIQUETAS,
    cargar_candidatos,
    crear_prompt,
    ejecutar,
    fingerprint,
    interpretar_puntajes,
)


def casos():
    return [{
        "id": f"CTX-{i}", "split": "train", "citation_context": f"We use TARGETCIT for experiment {i}. OTHERCIT is unrelated.",
        "cited_title": "A Study", "cited_abstract": "Short abstract.",
    } for i in range(3)]


class FakeClient:
    model = "fake-4b"
    def __init__(self):
        self.calls = 0
    def generate(self, prompt):
        self.calls += 1
        assert "TARGETCIT" in prompt
        return SimpleNamespace(text="[0.1, 0.9, 0, 0, 0, 0, 0, 0, 0]", input_tokens=10, output_tokens=9)


def parser_fake(text):
    return json.loads(text)


def test_marcador_y_taxonomia():
    texto = crear_prompt(casos()[0])
    assert "TARGETCIT" in texto and "OTHERCIT" in texto
    assert "EXACTLY ONE" in texto and "A Study" in texto
    assert len(ETIQUETAS) == 9


def test_rechazar_ganador_ambiguo():
    assert interpretar_puntajes([0.0] * 9)[2] == "ambiguo"
    assert interpretar_puntajes([0.9, 0.9] + [0.0] * 7)[0] is None
    assert interpretar_puntajes([0.0, 0.8] + [0.0] * 7)[0] == "Gap"


def test_validacion_sin_fuga_y_sin_gold(tmp_path):
    ruta = tmp_path / "candidatos.jsonl"
    ruta.write_text(json.dumps(casos()[0]) + "\n", encoding="utf-8")
    seleccion, h = cargar_candidatos(ruta)
    assert len(seleccion) == 1 and len(h) == 64
    ruta.write_text(json.dumps({**casos()[0], "gold": "Background"}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="etiquetas previas"):
        cargar_candidatos(ruta)


def test_ejecucion_y_reanudacion(tmp_path):
    cli = FakeClient()
    ruta = tmp_path / "predicciones.jsonl"
    run = fingerprint(cli.model, "abcd")
    resumen = ejecutar(casos(), cliente=cli, parser=parser_fake, ruta_resultados=ruta, id_run=run, limite=2)
    assert resumen["estados"] == {"ok": 2}
    assert cli.calls == 2
    assert sum(resumen["distribucion_sugerida_no_validada"].values()) == 2
    resumen2 = ejecutar(casos(), cliente=cli, parser=parser_fake, ruta_resultados=ruta, id_run=run, limite=3)
    assert cli.calls == 3 and resumen2["nuevas_inferencias"] == 1
    assert len(ruta.read_text(encoding="utf-8").splitlines()) == 3
    fila = json.loads(ruta.read_text(encoding="utf-8").splitlines()[0])
    assert fila["is_human_label"] is False and fila["suggested_label"] == "Gap"
    with pytest.raises(ValueError, match="incompatible"):
        ejecutar(casos(), cliente=cli, parser=parser_fake, ruta_resultados=ruta, id_run="otro", limite=3)


def test_error_proveedor_no_detiene_el_lote(tmp_path):
    class Broken(FakeClient):
        def generate(self, prompt):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("Servidor fuera de línea")
            return SimpleNamespace(text="[0.8, 0, 0, 0, 0, 0, 0, 0, 0]")
    cli = Broken()
    resumen = ejecutar(casos(), cliente=cli, parser=parser_fake, ruta_resultados=tmp_path / "r.jsonl", id_run="id", limite=2)
    assert resumen["estados"] == {"ok": 1, "provider_error": 1}
    assert cli.calls == 2
