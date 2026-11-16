"""Anotacion con Sonnet: validacion de salidas, reanudacion y aislamiento, con un `claude` simulado."""
import json
import os
import stat
import sys

import pytest

from clasificacion_funcion import anotacion_sonnet as an

PLANTILLA = "Instrucciones.\n## Casos\n{{CASOS}}\n"

FAKE = '''#!{py}
import json, os, re, sys
prompt = sys.stdin.read()
ids = [int(i) for i in re.findall(r'"n": ([0-9]+)', prompt)]
log = os.environ.get("FAKE_LOG")
if log:
    open(log, "a").write(json.dumps({{"argv": sys.argv[1:], "cwd": os.getcwd(), "ls": os.listdir("."),
                                      "n_ids": len(ids)}}) + "\\n")
modo = os.environ.get("FAKE_MODO", "ok")
cont = os.environ.get("FAKE_CONTADOR")
llamada = 0
if cont:
    llamada = int(open(cont).read() or 0) if os.path.exists(cont) else 0
    open(cont, "w").write(str(llamada + 1))
if modo == "error_proceso":
    sys.stderr.write("boom"); sys.exit(3)
filas = [{{"n": i, "evaluable": "Evaluable", "funcion": "background", "confianza": "Alta",
          "justificacion_breve": ""}} for i in ids]
if modo == "primero_incompleto" and llamada == 0:
    filas = filas[:-1]
if modo == "siempre_mal":
    filas[0]["funcion"] = "Inventada"
if modo == "abstencion":
    filas[0].update(evaluable="Ambiguo", funcion="", justificacion_breve="dos funciones plausibles")
texto = "```json\\n" + json.dumps(filas) + "\\n```"
print(json.dumps({{"result": texto, "is_error": False, "usage": {{"input_tokens": 10,
      "cache_read_input_tokens": 5, "output_tokens": 7}}}}))
'''


@pytest.fixture
def claude_falso(tmp_path):
    ruta = tmp_path / "claude_falso"
    ruta.write_text(FAKE.format(py=sys.executable), encoding="utf-8")
    ruta.chmod(ruta.stat().st_mode | stat.S_IEXEC)
    return str(ruta)


def casos(n):
    return {f"P10-{i:04d}_X00-0000_0": {"contexto": f"ctx {i} TARGETCIT", "titulo": f"t{i}", "abstract": f"a{i}"}
            for i in range(n)}


@pytest.fixture
def lotes(tmp_path):
    c = casos(5)
    l = an.crear_lotes(sorted(c), tam=2)
    an.escribir_lotes(l, c, tmp_path / "lotes")
    return tmp_path / "lotes", l


def ejecutor(claude_falso):
    return lambda prompt: an.ejecutar_claude(prompt, binario=claude_falso)


def test_lotes_disjuntos_deterministas_y_sin_etiquetas(tmp_path):
    c = casos(25)
    a, b = an.crear_lotes(sorted(c), tam=10), an.crear_lotes(sorted(c), tam=10)
    assert a == b and [len(v) for v in a.values()] == [10, 10, 5]
    assert sorted(i for v in a.values() for i in v) == sorted(c)
    an.escribir_lotes(a, c, tmp_path)
    cabecera = (tmp_path / "lote_001.csv").read_text(encoding="utf-8").splitlines()[0]
    assert cabecera == "context_id,Contexto TARGETCIT,Título citado,Resumen citado"
    assert an.COLUMNAS_LOTE == cabecera.split(",")


def test_seleccion_es_v_union_d1_sin_muestreo_nuevo():
    v, d1 = [{"context_id": "b"}, {"context_id": "a"}], [{"context_id": "b"}, {"context_id": "c"}]
    assert an.seleccionar_para_sonnet(v, d1) == ["a", "b", "c"]


def test_validar_respuesta_reglas():
    ids = ["x", "y"]
    ok = [{"n": 2, "evaluable": "Evaluable", "funcion": "gap", "confianza": "Alta"},
          {"n": 1, "evaluable": "Ambiguo", "funcion": "", "confianza": "Baja",
           "justificacion_breve": "duda"}]
    filas = an.validar_respuesta(ok, ids)
    assert [f["context_id"] for f in filas] == ["x", "y"] and filas[1]["funcion"] == "Gap"
    malos = [ok[:1], ok + [ok[0]], [{**ok[0], "funcion": "Otra"}, ok[1]],
             [ok[0], {**ok[1], "justificacion_breve": ""}], [ok[0], {**ok[1], "funcion": "Gap"}],
             [{**ok[0], "confianza": "Muy alta"}, ok[1]], [{**ok[0], "n": 3}, ok[1]],
             [{**ok[0], "n": "2"}, ok[1]], [{**ok[0], "n": True}, ok[1]]]
    for m in malos:
        with pytest.raises(ValueError):
            an.validar_respuesta(m, ids)


def test_extraer_json_tolera_bloque_de_codigo():
    assert an.extraer_json('```json\n[{"a": 1}]\n```') == [{"a": 1}]
    with pytest.raises(ValueError):
        an.extraer_json("no hay json")


def test_anota_valida_registra_y_es_reanudable(lotes, claude_falso, tmp_path):
    carpeta, l = lotes
    salidas, registro = tmp_path / "salidas", tmp_path / "registro.jsonl"
    r = an.anotar_pendientes(carpeta, salidas, PLANTILLA, ejecutor(claude_falso), registro, paralelo=2)
    assert r == {"total_lotes": 3, "intentados": 3, "ok": 3, "error": 0, "ya_validos": 0}
    lineas = [json.loads(x) for x in registro.read_text(encoding="utf-8").splitlines()]
    assert len(lineas) == 3 and all(x["tokens_entrada"] == 15 and x["tokens_salida"] == 7 for x in lineas)
    assert all(x["prompt_sha256"] == an.sha_prompt(PLANTILLA)[:16] for x in lineas)
    filas = an.leer_csv(salidas / "lote_001.csv")
    assert list(filas[0]) == an.COLUMNAS_SALIDA and filas[0]["Estado"] == "COMPLETO"
    assert filas[0]["Función principal"] == "Background" and filas[0]["pasada"] == "1"
    # segunda ejecucion: no reprocesa nada ni llama a claude
    r2 = an.anotar_pendientes(carpeta, salidas, PLANTILLA, lambda p: pytest.fail("no debe llamar"), registro)
    assert r2["intentados"] == 0 and r2["ya_validos"] == 3


def test_max_lotes_dosifica(lotes, claude_falso, tmp_path):
    carpeta, _ = lotes
    r = an.anotar_pendientes(carpeta, tmp_path / "s", PLANTILLA, ejecutor(claude_falso),
                             tmp_path / "r.jsonl", max_lotes=1, paralelo=1)
    assert r["intentados"] == 1 and len(list((tmp_path / "s").glob("lote_*.csv"))) == 1


def test_reintenta_una_vez_si_la_validacion_falla(lotes, claude_falso, tmp_path, monkeypatch):
    carpeta, _ = lotes
    monkeypatch.setenv("FAKE_MODO", "primero_incompleto")
    monkeypatch.setenv("FAKE_CONTADOR", str(tmp_path / "cont"))
    linea = an.anotar_lote(1, carpeta, tmp_path / "s", PLANTILLA, ejecutor(claude_falso))
    assert linea["estado"] == "ok" and linea["intentos"] == 2 and linea["tokens_salida"] == 14


def test_falla_persistente_queda_error_sin_salida(lotes, claude_falso, tmp_path, monkeypatch):
    carpeta, _ = lotes
    monkeypatch.setenv("FAKE_MODO", "siempre_mal")
    linea = an.anotar_lote(1, carpeta, tmp_path / "s", PLANTILLA, ejecutor(claude_falso))
    assert linea["estado"] == "error" and linea["intentos"] == 2 and "funcion invalida" in linea["error"]
    assert not (tmp_path / "s" / "lote_001.csv").exists()


def test_proceso_que_falla_no_detiene_la_tanda(lotes, claude_falso, tmp_path, monkeypatch):
    carpeta, _ = lotes
    monkeypatch.setenv("FAKE_MODO", "error_proceso")
    r = an.anotar_pendientes(carpeta, tmp_path / "s", PLANTILLA, ejecutor(claude_falso), tmp_path / "r.jsonl")
    assert r["error"] == 3 and r["ok"] == 0


def test_abstencion_queda_registrada(lotes, claude_falso, tmp_path, monkeypatch):
    carpeta, l = lotes
    monkeypatch.setenv("FAKE_MODO", "abstencion")
    an.anotar_lote(1, carpeta, tmp_path / "s", PLANTILLA, ejecutor(claude_falso))
    primera = an.leer_csv(tmp_path / "s" / "lote_001.csv")[0]
    assert (primera["¿Evaluable?"], primera["Función principal"], primera["Estado"]) == ("Ambiguo", "", "REGISTRADO")


def test_llamada_aislada(lotes, claude_falso, tmp_path, monkeypatch):
    carpeta, _ = lotes
    log = tmp_path / "log.jsonl"
    monkeypatch.setenv("FAKE_LOG", str(log))
    an.anotar_lote(1, carpeta, tmp_path / "s", PLANTILLA, ejecutor(claude_falso))
    llamada = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
    argv = llamada["argv"]
    assert argv[argv.index("--tools") + 1] == "" and "--strict-mcp-config" in argv
    assert "--disable-slash-commands" in argv and "--no-session-persistence" in argv
    assert "--bare" not in argv  # --bare omite el keychain: rompe la sesion de la cuenta
    assert llamada["ls"] == [] and "microproyecto" not in llamada["cwd"] and llamada["n_ids"] == 2


def test_el_prompt_no_lleva_etiquetas_ni_otras_pasadas(lotes):
    carpeta, l = lotes
    filas = an.leer_csv(carpeta / "lote_001.csv")
    prompt = an.construir_prompt(PLANTILLA, filas)
    assert '"n": 1' in prompt and "{{CASOS}}" not in prompt
    assert set(json.loads(prompt.split("## Casos\n")[1])[0]) == {"n", "contexto", "titulo", "resumen"}
    assert "context_id" not in prompt and not any(f["context_id"] in prompt for f in filas)


def test_piloto_y_informe(tmp_path, claude_falso):
    ctx = {f"P10-{i:04d}_X00-0000_0": {} for i in range(60)}
    ids = sorted(ctx)
    taller = {ids[0]: "Background", ids[1]: "Gap", "fuera": "Gap"}
    gpt = {ids[2]: "Background", ids[0]: "Gap"}
    jurado = {c: {"acuerdo": 3, "voto": "Background"} for c in ids[3:40]}
    jurado[ids[41]] = {"acuerdo": 2, "voto": "Gap"}
    sel = an.seleccionar_piloto(taller, gpt, jurado, ctx, n_jurado=10)
    refs = sel["referencias"]
    assert set(refs["taller"]) == {ids[0], ids[1]} and len(refs["jurado_3de3"]) == 10
    assert ids[41] not in sel["ids"] and set(refs["taller"]) | set(refs["gpt"]) | set(refs["jurado_3de3"]) == set(sel["ids"])
    c = {i: {"contexto": "c TARGETCIT", "titulo": "t", "abstract": "a"} for i in sel["ids"]}
    an.escribir_lotes(an.crear_lotes(sel["ids"], tam=8), c, tmp_path / "lotes")
    an.anotar_pendientes(tmp_path / "lotes", tmp_path / "s", PLANTILLA, ejecutor(claude_falso), tmp_path / "r.jsonl")
    rep = an.informe_piloto(tmp_path / "s", refs, tmp_path / "r.jsonl", lotes_totales=100)
    assert rep["acuerdo"]["jurado_3de3"] == {"n": 10, "acuerdo": 1.0}  # el falso siempre dice Background
    assert rep["acuerdo"]["taller"]["acuerdo"] == 0.5 and rep["extrapolacion"]["tokens_salida"] == 7 * 100
    assert an.consolidar(tmp_path / "s", tmp_path / "todo.csv") == len(sel["ids"])


def test_verificar_aislamiento_devuelve_tokens_y_respuesta(claude_falso, tmp_path, monkeypatch):
    log = tmp_path / "log.jsonl"
    monkeypatch.setenv("FAKE_LOG", str(log))
    rep = an.verificar_aislamiento(ejecutor(claude_falso))
    assert rep["tokens_entrada"] == 15 and rep["tokens_salida"] == 7 and "respuesta" in rep
    assert "--tools" in json.loads(log.read_text(encoding="utf-8").splitlines()[0])["argv"]


def test_guarda_la_respuesta_cruda_de_los_intentos_fallidos(lotes, claude_falso, tmp_path, monkeypatch):
    carpeta, _ = lotes
    monkeypatch.setenv("FAKE_MODO", "siempre_mal")
    errores = tmp_path / "errores"
    linea = an.anotar_lote(1, carpeta, tmp_path / "s", PLANTILLA, ejecutor(claude_falso), carpeta_errores=errores)
    assert linea["estado"] == "error"
    crudas = sorted(p.name for p in errores.iterdir())
    assert crudas == ["lote_001_pasada1_intento1.txt", "lote_001_pasada1_intento2.txt"]
    assert "Inventada" in (errores / crudas[0]).read_text(encoding="utf-8")


def test_salida_con_ids_de_otro_orden_no_es_valida(lotes, claude_falso, tmp_path):
    carpeta, l = lotes
    an.anotar_lote(1, carpeta, tmp_path / "s", PLANTILLA, ejecutor(claude_falso))
    ruta = tmp_path / "s" / "lote_001.csv"
    assert an.salida_valida(ruta, l[1]) and not an.salida_valida(ruta, list(reversed(l[1])))
