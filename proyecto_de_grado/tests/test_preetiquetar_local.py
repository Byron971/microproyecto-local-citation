"""Pruebas unitarias sin red, sin descargas ni costos."""
import json
import hashlib
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
    interpretar_etiqueta_directa,
    PROMPT,
    PROMPT_ETIQUETA_DIRECTA,
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


def test_etiqueta_directa_reproduce_prompt_del_piloto_manual():
    caso = casos()[0]
    esperado = crear_prompt(caso).split("Reply ONLY with a JSON array")[0]
    esperado += (
        "\nReturn exactly ONE category name from this list:\n"
        + "\n".join(ETIQUETAS)
        + "\nNo scores. No explanation. No additional text."
    )
    assert crear_prompt(caso, formato="label") == esperado
    assert "Reply ONLY with a JSON array" in PROMPT
    assert "Reply ONLY with a JSON array" not in PROMPT_ETIQUETA_DIRECTA
    assert "TARGETCIT" in crear_prompt(caso, formato="label")
    with pytest.raises(ValueError, match="Formato"):
        crear_prompt(caso, formato="otro")


def test_etiqueta_directa_no_confunde_subcadenas_o_explicaciones():
    for etiqueta in ETIQUETAS:
        assert interpretar_etiqueta_directa(f"\n{etiqueta}\n") == etiqueta
    for invalida in (
        "Background / Evidence",
        "The answer is Background.",
        "background",
        "Background\nGap",
        "[0.95, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01]",
        "", None,
    ):
        with pytest.raises(ValueError, match="Respuesta|etiquetas"):
            interpretar_etiqueta_directa(invalida)


def test_fingerprint_historico_se_preserva_y_label_se_aisla():
    modelo, entrada = "qwen3:4b-instruct", "hash_entrada"
    configuracion_original = json.dumps({
        "modelo": modelo,
        "input_sha256": entrada,
        "prompt_sha256": hashlib.sha256(PROMPT.encode("utf-8")).hexdigest(),
    }, sort_keys=True, ensure_ascii=False)
    anterior = hashlib.sha256(configuracion_original.encode("utf-8")).hexdigest()
    assert fingerprint(modelo, entrada) == anterior
    assert fingerprint(modelo, entrada, formato="scores") == anterior
    assert fingerprint(modelo, entrada, formato="label") != anterior


def test_etiqueta_directa_no_fabrica_puntajes_y_reanuda(tmp_path):
    class ClienteDirecto:
        model = "qwen-simulado"
        def __init__(self):
            self.calls = []
        def generate(self, prompt):
            self.calls.append(prompt)
            assert "No scores." in prompt
            etiqueta = "Application" if "experiment 0" in prompt else "Basis"
            return SimpleNamespace(text=etiqueta, input_tokens=42, output_tokens=1)

    cli = ClienteDirecto()
    ruta = tmp_path / "directos.jsonl"
    huella = fingerprint(cli.model, "abc", formato="label")
    res = ejecutar(casos(), cliente=cli, parser=parser_fake, ruta_resultados=ruta,
                  id_run=huella, limite=2, formato="label")
    assert res["estados"] == {"ok": 2}
    assert res["response_format"] == "label"
    assert len(cli.calls) == 2
    registros = [json.loads(l) for l in ruta.read_text(encoding="utf-8").splitlines()]
    assert [r["suggested_label"] for r in registros] == ["Application", "Basis"]
    assert all(r["scores"] is None and r["top1_top2_margin_uncalibrated"] is None for r in registros)
    assert all(r["is_human_label"] is False and r["response_format"] == "label" for r in registros)
    assert all(r["raw_response"] == r["suggested_label"] for r in registros)
    res2 = ejecutar(casos(), cliente=cli, parser=parser_fake, ruta_resultados=ruta,
                   id_run=huella, limite=3, formato="label")
    assert res2["nuevas_inferencias"] == 1
    assert res2["omitidos_por_reanudacion"] == 2
    assert len(cli.calls) == 3
    with pytest.raises(ValueError, match="incompatible"):
        ejecutar(casos(), cliente=cli, parser=parser_fake, ruta_resultados=ruta,
               id_run=fingerprint(cli.model, "abc", formato="scores"),
               limite=3, formato="scores")


def test_etiqueta_directa_invalida_se_conserva_como_error_de_formato(tmp_path):
    class ClienteMal:
        model = "mock"
        def generate(self, prompt):
            return SimpleNamespace(text="Background or Gap",
                                   input_tokens=None, output_tokens=None)
    ruta = tmp_path / "bad.jsonl"
    resumen = ejecutar(casos(), cliente=ClienteMal(), parser=parser_fake,
                       ruta_resultados=ruta, id_run="directo",
                       limite=1, formato="label")
    assert resumen["estados"] == {"parse_error": 1}
    fila = json.loads(ruta.read_text(encoding="utf-8").strip())
    assert fila["raw_response"] == "Background or Gap"
    assert fila["suggested_label"] is None
    assert fila["scores"] is None
    assert fila["is_human_label"] is False
