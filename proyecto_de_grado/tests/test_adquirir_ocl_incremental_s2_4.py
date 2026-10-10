"""S2.4: la descarga exige opt-in, límites y validación de identidad."""
import io
import json
import urllib.error

import pytest

from proyecto_de_grado.src.data.adquirir_ocl_incremental_s2_4 import (
    _descargar_uno, ejecutar_plan, leer_prioridades, planificar, main
)


class Respuesta:
    def __init__(self, contenido, headers=None):
        self.contenido = contenido
        self.headers = headers or {}
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, n):
        return self.contenido[:n]


def _json_acl(cited_id):
    return json.dumps({"paper_id": cited_id, "pdf_parse": {
        "body_text": [{"text": "A long example paragraph.", "section": "Intro"}]
    }}).encode("utf-8")


def _diagnostico(tmp_path):
    p = tmp_path / "diagnostico.json"
    filas = [
        ("P07-2045", 473), ("N03-1017", 464), ("P03-1021", 431),
        ("J07-2003", 394), ("P03-1054", 328), ("P05-1033", 262),
        ("W98-2127", 210), ("P08-1028", 158)
    ]
    p.write_text(json.dumps({"tipo": "diagnostico_offline_s2_4_solo_train",
                             "prioridad_descarga_train": [
                                 {"cited_id": pid, "contextos_train_potenciales": n}
                                 for pid, n in filas
                             ]}), encoding="utf-8")
    return p


def test_planificacion_equilibra_decadas_y_limita_a_diez(tmp_path):
    p = _diagnostico(tmp_path)
    filas = leer_prioridades(p)
    plan = planificar(filas, tmp_path / "cache", limite=6)
    ids = [x["cited_id"] for x in plan["documentos"]]
    assert len(ids) == 6
    assert ids[:3] == ["P07-2045", "N03-1017", "P03-1021"]
    assert "W98-2127" in ids
    assert plan["sin_descargas"] is True
    assert plan["contextos_train_potenciales_suma_no_verificada"] > 0
    with pytest.raises(ValueError, match="entre 1 y 10"):
        planificar(filas, tmp_path, 11)


def test_prioridad_debe_ser_exclusivamente_train_y_sin_ids_duplicados(tmp_path):
    p = _diagnostico(tmp_path)
    j = json.loads(p.read_text())
    j["tipo"] = "gold_test"
    p.write_text(json.dumps(j))
    with pytest.raises(ValueError, match="train"):
        leer_prioridades(p)
    j["tipo"] = "diagnostico_offline_s2_4_solo_train"
    j["prioridad_descarga_train"].append(j["prioridad_descarga_train"][0])
    p.write_text(json.dumps(j))
    with pytest.raises(ValueError, match="duplicado"):
        leer_prioridades(p)


def test_dry_run_no_crea_cache_ni_solicita_red(tmp_path):
    p = _diagnostico(tmp_path)
    cache = tmp_path / "no_existe_cache"
    rc = main(["--diagnostico", str(p), "--cache", str(cache), "--limite", "6"])
    assert rc == 0
    assert not cache.exists()


def test_descarga_verificada_es_atómica_y_reusable(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    calls = []
    def abrir(url, timeout):
        calls.append((url, timeout))
        return Respuesta(_json_acl("P07-2045"))
    resultado = _descargar_uno("P07-2045", cache, max_bytes=500_000,
                              pausa=1, abrir=abrir, dormir=lambda *_: None)
    assert resultado["estado"] == "descargado"
    assert (cache / "P07-2045.json").is_file()
    assert not (cache / ".P07-2045.partial").exists()
    assert len(resultado["sha256"]) == 64
    assert calls[0][0].endswith("/prefixP/json/P07/P07-2045.json")
    def prohibir(*args, **kw):
        raise AssertionError("No debe consultar la red")
    again = _descargar_uno("P07-2045", cache, max_bytes=500_000,
                          pausa=1, abrir=prohibir)
    assert again["estado"] == "ya_existia"


def test_no_guarda_identidad_invalida_ni_respuesta_demasiado_grande(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    r = _descargar_uno("P07-2045", cache, max_bytes=500_000, pausa=1,
                       abrir=lambda *_args, **_kw: Respuesta(_json_acl("P03-1054")))
    assert r["estado"] == "estructura_o_id_invalido"
    assert not (cache / "P07-2045.json").exists()
    r = _descargar_uno("P07-2045", cache, max_bytes=100, pausa=1,
                       abrir=lambda *_args, **_kw: Respuesta(_json_acl("P07-2045")))
    assert r["estado"] == "supera_limite_bytes"
    assert not (cache / "P07-2045.json").exists()


def test_solo_http_404_real_guarda_marca_de_no_disponibilidad(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    def error_http(code):
        def lanzar(url, timeout):
            raise urllib.error.HTTPError(url, code, "test", {}, io.BytesIO())
        return lanzar
    r = _descargar_uno("P07-2045", cache, max_bytes=500_000, pausa=1,
                       abrir=error_http(404))
    assert r["estado"] == "404_confirmado"
    assert (cache / "P07-2045.404").exists()
    assert not (cache / "P07-2045.json").exists()
    r = _descargar_uno("P07-2045", cache, max_bytes=500_000, pausa=1,
                       abrir=lambda *_: pytest.fail("No debe descargar"))
    assert r["estado"] == "404_anterior"


def test_http_429_reintenta_de_forma_acotada_y_403_no(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    attempts = []
    sleeps = []
    def abrir(url, timeout):
        attempts.append(url)
        if len(attempts) < 3:
            raise urllib.error.HTTPError(url, 429, "rate limit", {}, io.BytesIO())
        return Respuesta(_json_acl("P07-2045"))
    r = _descargar_uno("P07-2045", cache, max_bytes=500_000, pausa=1,
                       abrir=abrir, dormir=sleeps.append)
    assert r["estado"] == "descargado"
    assert len(attempts) == 3
    assert sleeps == [1, 2]
    other = _descargar_uno("P03-1054", cache, max_bytes=500_000, pausa=1,
                          abrir=lambda url, timeout: (
                              (_ for _ in ()).throw(
                                  urllib.error.HTTPError(url, 403, "forbidden", {}, io.BytesIO())
                              )
                          ))
    assert other["estado"] == "http_403"
    assert not (cache / "P03-1054.404").exists()


def test_ejecucion_rechaza_maximo_bytes_o_pausa_inseguros(tmp_path):
    plan = {"documentos": [{"cited_id": "P07-2045"}]}
    with pytest.raises(ValueError, match="Máximo 5 MB"):
        ejecutar_plan(plan, tmp_path / "cache", max_bytes=6_000_000)
    with pytest.raises(ValueError, match="pausa mínima"):
        ejecutar_plan(plan, tmp_path / "cache", pausa=0)
    assert not (tmp_path / "cache").exists()


def test_omite_archivos_ya_presentes_antes_de_planificar(tmp_path):
    filas = leer_prioridades(_diagnostico(tmp_path))
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "P07-2045.json").write_text("{}")
    (cache / "P03-1021.404").write_text("")
    plan = planificar(filas, cache, limite=3)
    ids = [x["cited_id"] for x in plan["documentos"]]
    assert "P07-2045" not in ids and "P03-1021" not in ids
    assert plan["descartes"]["ya_existe_en_cache"] == 1
    assert plan["descartes"]["404_ya_conocido"] == 1
