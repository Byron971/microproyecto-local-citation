"""S2.5.b: no descargar por defecto, no mezclar etiquetas externas."""
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from proyecto_de_grado.src.data import perfilar_multicite_s2_5 as m


def _fake_source():
    return [
        {"id": "ABC_0001", "x": ["Citation to previous research.", "Continuation."],
         "y": "background uses"},
        {"id": "ABC_0002", "x": "Unlike earlier methods, our work ...",
         "y": "differences"},
        {"id": "ABC_0003", "x": "We adapt their earlier approach.",
         "y": "extends"},
        {"id": "ABC_0004", "x": "Previous work discussed the area.",
         "y": "motivation future_work"},
        {"id": "ABC_0005", "x": "We use a similar setup.",
         "y": "similarities"},
        {"id": "ABC_0006", "x": "This citation has another use.",
         "y": "uses"},
    ]


def test_sin_execute_no_descarga_ni_escribe(capsys, tmp_path, monkeypatch):
    def bloquear(*args, **kwargs):
        raise AssertionError("Se intentó acceder a red")
    monkeypatch.setattr(m, "descargar_train", bloquear)
    carpeta = tmp_path / "no_crear"
    assert m.main(["--out", str(carpeta)]) == 0
    assert not carpeta.exists()
    salida = capsys.readouterr().out
    assert "PLAN SIN RED" in salida
    assert "0 descargas" in salida


def test_perfil_estratificado_reproducible_no_homologa():
    parsed = m.cargar_y_validar(json.dumps(_fake_source()).encode())
    p1 = m.perfil_muestra(parsed, muestra=5, semilla=42)
    p2 = m.perfil_muestra(parsed[::-1], muestra=5, semilla=42)
    assert p1 == p2
    assert p1["filas_train"] == 6
    assert p1["filas_con_multiples_etiquetas"] == 2
    assert p1["muestra"] == 5
    assert p1["ids_que_parecen_acl_anthology"] == 0
    assert p1["clases_internas_validadas"] == 0
    assert p1["equivalencias_externas_aprobadas"] == 0
    assert {l for f in p1["muestra_local"] for l in f["external_labels"]} <= m.LABELS
    assert all(len(f["context_preview"]) <= 250 for f in p1["muestra_local"])


def test_parser_multilabel_rechaza_unknown_y_duplicates():
    for invalida in [
        {"id": "a", "x": "text", "y": "background unsure"},
        {"id": "a", "x": "text", "y": "background background"},
        {"id": "a", "x": "text", "y": "Background"},
        {"id": "a", "x": "text", "y": ""},
        {"id": "a", "x": {"unexpected": "object"}, "y": "uses"},
    ]:
        with pytest.raises(ValueError):
            m.cargar_y_validar(json.dumps([invalida]).encode())
    with pytest.raises(ValueError, match="repetido"):
        m.cargar_y_validar(json.dumps([_fake_source()[0]] * 2).encode())


def test_descarga_controlada_con_hash_git_mockeado(monkeypatch):
    datos = json.dumps(_fake_source()).encode()
    esperado = hashlib.sha1(f"blob {len(datos)}\0".encode() + datos).hexdigest()
    class Fake:
        headers = {"Content-Length": str(len(datos))}
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self, limit):
            return datos[:limit]
    calls = []
    def fake_open(req, timeout):
        calls.append((req.full_url, timeout))
        return Fake()
    monkeypatch.setattr(m, "SOURCE_BLOB_SHA1", esperado)
    assert m.descargar_train(abrir=fake_open) == datos
    assert len(calls) == 1
    assert "classification_1_context/train.json" in calls[0][0]


def test_descarga_rechaza_mutacion_y_exceso_de_bytes(monkeypatch):
    datos = json.dumps(_fake_source()).encode()
    class Fake:
        headers = {}
        def __init__(self, data):
            self.data = data
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self, n):
            return self.data[:n]
    with pytest.raises(ValueError, match="SHA-1"):
        m.descargar_train(abrir=lambda *a, **kw: Fake(datos))
    monkeypatch.setattr(m, "MAX_BYTES", 10)
    with pytest.raises(ValueError, match="límite"):
        m.descargar_train(abrir=lambda *a, **kw: Fake(datos))


def test_input_offline_con_hash_fijado_y_salida_ignorada_por_git(monkeypatch, tmp_path):
    datos = json.dumps(_fake_source()).encode()
    esperado = m.git_blob_sha1(datos)
    monkeypatch.setattr(m, "SOURCE_BLOB_SHA1", esperado)
    entrada = tmp_path / "train.json"
    entrada.write_bytes(datos)
    salida = tmp_path / "reportes"
    assert m.main(["--input", str(entrada), "--sample", "3",
                   "--out", str(salida)]) == 0
    obj = json.loads((salida / "perfil_multicite_train.json").read_text())
    assert obj["muestra"] == 3
    assert obj["particion_fuente"] == "train"
    assert len(obj["fuente_sha256"]) == 64
    assert obj["clases_internas_validadas"] == 0
    assert list(salida.iterdir()) == [salida / "perfil_multicite_train.json"]


def test_no_permite_input_y_execute_simultaneos(tmp_path):
    with pytest.raises(SystemExit):
        m.main(["--input", str(tmp_path / "train.json"), "--execute"])
    with pytest.raises(SystemExit):
        m.main(["--sample", "100"])


def test_fuente_pinneada_es_train_no_test_ni_full():
    assert "/train.json" in m.SOURCE_URL
    assert "classification_1_context" in m.SOURCE_URL
    assert "/test" not in m.SOURCE_URL
    assert "full-v" not in m.SOURCE_URL
    assert len(m.SOURCE_COMMIT) == 40
    assert len(m.SOURCE_BLOB_SHA1) == 40
    assert m.SOURCE_SIZE < m.MAX_BYTES


def test_contextos_vacios_reales_se_excluyen_con_trazabilidad_y_sin_fusion():
    """Reproduce x=[] de MultiCite train, incluido el caso de la fila 833."""
    filas = _fake_source() + [
        {"id": "264bdb348c13f167768fd859b047e8_7",
         "x": [], "y": "differences"},
        {"id": "264bdb348c13f167768fd859b047e8_12",
         "x": [], "y": "similarities"},
        {"id": "espacios", "x": ["  "], "y": "background"},
    ]
    parsed = m.cargar_y_validar(json.dumps(filas).encode())
    assert len(parsed) == 9
    assert parsed[6]["estado_contexto"] == "excluido_contexto_vacio"
    assert parsed[6]["fila_original"] == 6
    perfil = m.perfil_muestra(parsed, muestra=8, semilla=42)
    assert perfil["filas_train"] == 9
    assert perfil["filas_train_utilizables"] == 6
    assert perfil["filas_excluidas_contexto_vacio"] == 3
    assert len(perfil["exclusiones_contexto_vacio"]) == 3
    assert perfil["muestra"] == 6
    assert all(x["external_id"] not in {
        "264bdb348c13f167768fd859b047e8_7",
        "264bdb348c13f167768fd859b047e8_12", "espacios",
    } for x in perfil["muestra_local"])
    assert perfil["codigos_externos_observados"]["differences"] == 2
    assert perfil["codigos_externos_en_filas_utilizables"]["differences"] == 1
    assert perfil["clases_internas_validadas"] == 0


def test_contexto_vacio_no_tapa_errores_reales_de_taxonomia_o_duplicados():
    with pytest.raises(ValueError, match="etiquetas no válidas"):
        m.cargar_y_validar(json.dumps([
            {"id": "a", "x": [], "y": "unsure"}
        ]).encode())
    with pytest.raises(ValueError, match="repetido"):
        m.cargar_y_validar(json.dumps([
            {"id": "a", "x": [], "y": "uses"},
            {"id": "a", "x": ["texto"], "y": "uses"},
        ]).encode())
    with pytest.raises(ValueError, match="No existen contextos utilizables"):
        m.perfil_muestra(m.cargar_y_validar(json.dumps([
            {"id": "a", "x": [], "y": "uses"},
        ]).encode()))


def test_muestreo_no_incluye_vacios_aunque_solo_sean_categorias_raras():
    filas = [
        {"id": "zero", "x": [], "y": "future_work"},
        {"id": "full", "x": ["Sample valid example."], "y": "background"},
    ]
    perfil = m.perfil_muestra(
        m.cargar_y_validar(json.dumps(filas).encode()), muestra=2
    )
    assert [x["external_id"] for x in perfil["muestra_local"]] == ["full"]
    assert perfil["filas_excluidas_contexto_vacio"] == 1
    assert perfil["codigos_externos_observados"]["future_work"] == 1
    assert "future_work" not in perfil["codigos_externos_en_filas_utilizables"]
