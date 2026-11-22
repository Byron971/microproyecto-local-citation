"""Pruebas de notebooks/anotacion_asistida.py con datos sintéticos y un cliente falso.

No llaman a ningún proveedor ni leen hojas reales de anotación.
"""
import csv
import importlib.util
import json
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace
from xml.sax.saxutils import escape

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "notebooks" / "anotacion_asistida.py"
spec = importlib.util.spec_from_file_location("anotacion_asistida", MODULE_PATH)
aa = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = aa
spec.loader.exec_module(aa)

CONTEXT = "Prior work (TARGETCIT) uses dependency parsing for this task. We follow OTHERCIT closely."
EVIDENCE = "Prior work (TARGETCIT) uses dependency parsing"


def answer(evidence=EVIDENCE, **overrides):
    result = {"evaluabilidad": "Evaluable", "funcion": "Background", "confianza": "Media",
              "justificacion": "Sitúa el trabajo en la literatura previa.", "evidencia": evidence}
    return {**result, **overrides}


NO_EVALUABLE = answer("", evaluabilidad="No evaluable", funcion="", confianza="")


@pytest.fixture(autouse=True)
def sin_proveedor_real(monkeypatch):
    """Ninguna prueba puede crear un cliente real ni leer la clave del entorno."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(aa, "_anthropic_client", lambda: pytest.fail("la prueba intentó usar Anthropic real"))
    monkeypatch.setattr(aa, "_openai_client", lambda: pytest.fail("la prueba intentó usar el proveedor real"))


# --- Plantilla sintética -------------------------------------------------------

def _cell(ref, text):
    return f'<c r="{ref}" s="1" t="inlineStr"><is><t>{escape(text)}</t></is></c>'


def build_template(path, ids):
    cols = "ABCDEFGHIJKLM"
    header = ("#",) + aa.HEADER
    rows = ['<row r="1">' + "".join(_cell(f"{c}1", h) for c, h in zip(cols, header)) + "</row>"]
    for i, cid in enumerate(ids, start=2):
        values = {"A": str(i - 1), "B": cid, "C": CONTEXT, "E": "T", "G": "R"}
        cells = "".join(_cell(f"{c}{i}", values[c]) if c in values else f'<c r="{c}{i}" s="1"/>'
                        for c in cols[:12])
        rows.append(f'<row r="{i}">{cells}<c r="M{i}" s="1"><f>IF(I{i}="","PENDIENTE","COMPLETO")</f><v/></c></row>')
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    rns = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
    guide = (f'<row r="1">{_cell("A1", "Función")}{_cell("B1", "Definición")}</row>'
             f'<row r="2">{_cell("A2", "Background")}{_cell("B2", "Contexto general")}</row>')
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("xl/workbook.xml", f'<workbook {ns} {rns}><sheets>'
                   '<sheet name="Mis_anotaciones" sheetId="1" r:id="rId1"/>'
                   '<sheet name="9_funciones" sheetId="2" r:id="rId2"/></sheets><calcPr calcId="1"/></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/>'
                   '<Relationship Id="rId2" Target="worksheets/sheet2.xml"/></Relationships>')
        z.writestr("xl/worksheets/sheet1.xml", f'<worksheet {ns}><sheetData>{"".join(rows)}</sheetData></worksheet>')
        z.writestr("xl/worksheets/sheet2.xml", f'<worksheet {ns}><sheetData>{guide}</sheetData></worksheet>')
    return path


@pytest.fixture
def workspace(tmp_path):
    source = build_template(tmp_path / "plantilla.xlsx", ["a", "b", "c"])
    template = aa.read_template(source)
    log = aa.log_path_for(template, tmp_path / "logs")
    return SimpleNamespace(source=source, template=template, log=log, tmp=tmp_path,
                           cases={case["context_id"]: case for case in template["cases"]})


def entry(ws, cid, status, attempt=1, **extra):
    case = ws.cases[cid]
    return {"context_id": cid, "input_sha256": case["input_sha256"], "run_key": ws.template["run_key"],
            "status": status, "attempt": attempt, **extra}


def evidence_failures(ws, cid, n=aa.CONFIG["failure_limit"]):
    return [entry(ws, cid, "error", i, error_kind="respuesta", error_code="evidencia", detail="x",
                  evidence_mode="selection_v1")
            for i in range(1, n + 1)]


def write_log(ws, entries):
    for item in entries:
        aa.append_log(ws.log, item)


# --- Evidencia y validación ------------------------------------------------------

@pytest.mark.parametrize("evidence", ["TARGETCIT", "a", "We follow"])
def test_rechaza_evidencia_trivial_aunque_sea_literal(evidence):
    assert evidence in CONTEXT
    assert aa.literal_evidence(evidence, CONTEXT) is None


@pytest.mark.parametrize("evidence", ["rior work (TARGETCIT) uses", EVIDENCE + " pars"[:-1]])
def test_rechaza_fragmento_cortado_a_mitad_de_palabra(evidence):
    assert aa.literal_evidence(evidence, CONTEXT) is None


@pytest.mark.parametrize("evidence", [
    EVIDENCE, EVIDENCE + ".", "..." + EVIDENCE, "…" + EVIDENCE + "…",
    "Prior  work (TARGETCIT)\nuses dependency parsing",
])
def test_recupera_el_fragmento_original(evidence):
    assert aa.literal_evidence(evidence, CONTEXT) == EVIDENCE


def test_conserva_punto_que_existe_en_el_original():
    assert aa.literal_evidence("dependency parsing for this task.", CONTEXT) == "dependency parsing for this task."


@pytest.mark.parametrize("evidence", ["Prior work (TARGETCIT) ... for this task",
                                      "Earlier work (TARGETCIT) uses dependency parsing"])
def test_rechaza_elision_y_parafrasis(evidence):
    assert aa.literal_evidence(evidence, CONTEXT) is None


def test_evidencia_vacia_solo_en_no_evaluable():
    assert aa.validate_result(NO_EVALUABLE, CONTEXT)["evidencia"] == ""
    with pytest.raises(aa.ValidationError) as exc:
        aa.validate_result(answer(""), CONTEXT)
    assert exc.value.code == "evidencia"


def test_ambiguo_requiere_confianza_baja():
    with pytest.raises(aa.ValidationError) as exc:
        aa.validate_result(answer(evaluabilidad="Ambiguo", confianza="Alta"), CONTEXT)
    assert exc.value.code == "ambiguo"


# --- Plantilla ------------------------------------------------------------------

def test_template_lee_casos_y_guia(workspace):
    t = workspace.template
    assert [c["context_id"] for c in t["cases"]] == ["a", "b", "c"]
    assert [c["row"] for c in t["cases"]] == [2, 3, 4]
    assert all((not c["has_answers"] and c["valid_target"]) for c in t["cases"])
    assert t["prompt"].endswith("Función | Definición\nBackground | Contexto general")


def test_template_rechaza_columnas_inesperadas(tmp_path):
    path = build_template(tmp_path / "x.xlsx", ["a"])
    with zipfile.ZipFile(path) as z:
        parts = {n: z.read(n) for n in z.namelist()}
    parts["xl/worksheets/sheet1.xml"] = parts["xl/worksheets/sheet1.xml"].replace("Confianza".encode(), b"Otra")
    with zipfile.ZipFile(path, "w") as z:
        for name, data in parts.items():
            z.writestr(name, data)
    with pytest.raises(ValueError, match="columnas esperadas"):
        aa.read_template(path)


# --- Registro ---------------------------------------------------------------------

def test_estado_distingue_directas_recuperadas_y_fallos(workspace):
    ws = workspace
    write_log(ws, [
        entry(ws, "a", "ok", result=answer(), response_id="r-a"),
        # Formato antiguo: sin error_code; rechazado solo por el punto final.
        entry(ws, "b", "error", error_type="ValueError", response_id="r-b",
              detail="La evidencia debe ser una cita literal del contexto.",
              raw_response=json.dumps(answer(EVIDENCE + "."))),
        entry(ws, "c", "error", 1, error_kind="respuesta", error_code="evidencia", detail="x",
              raw_response=json.dumps(answer("Earlier work uses parsing heavily"))),
        entry(ws, "c", "error", 2, error_type="APIConnectionError", error_kind="proveedor", detail="x"),
        {**entry(ws, "a", "ok", result=answer()), "run_key": "otra-configuracion"},
    ])
    state = aa.load_state(ws.template, ws.log)
    assert (state["proposals"]["a"]["origin"], state["proposals"]["a"]["response_id"]) == ("llm_directa", "r-a")
    assert state["proposals"]["b"]["origin"] == "llm_recuperada"
    assert state["proposals"]["b"]["result"]["evidencia"] == EVIDENCE
    assert "c" not in state["proposals"]
    assert state["failures"]["c"] == 1   # el error del proveedor no cuenta


def test_ok_posterior_reemplaza_recuperada(workspace):
    ws = workspace
    write_log(ws, [entry(ws, "a", "error", 1, error_kind="respuesta", error_code="evidencia", detail="x",
                         raw_response=json.dumps(answer(EVIDENCE + "."))),
                   entry(ws, "a", "ok", 2, result=answer())])
    record = aa.load_state(ws.template, ws.log)["proposals"]["a"]
    assert (record["origin"], record["attempt"]) == ("llm_directa", 2)


def test_entrada_ok_antigua_invalida_se_omite(workspace):
    ws = workspace
    write_log(ws, [entry(ws, "a", "ok", result=answer("TARGETCIT"))])
    state = aa.load_state(ws.template, ws.log)
    assert state["skipped"] == 1 and not state["proposals"]


def test_casos_agotados_salen_de_pendientes(workspace):
    ws = workspace
    write_log(ws, evidence_failures(ws, "a"))
    state = aa.load_state(ws.template, ws.log)
    assert [c["context_id"] for c in state["pending"]] == ["b", "c"]
    assert [c["context_id"] for c in state["exhausted"]] == ["a"]


def test_fallos_del_metodo_anterior_se_pueden_reintentar(workspace):
    ws = workspace
    failures = evidence_failures(ws, "b")
    for item in failures:
        item.pop("evidence_mode")
    write_log(ws, [entry(ws, "a", "ok", result=answer()), *failures])
    state = aa.load_state(ws.template, ws.log)
    assert "a" in state["proposals"]
    assert [case["context_id"] for case in state["pending"]] == ["b", "c"]
    assert state["failures"]["b"] == aa.CONFIG["failure_limit"]
    assert state["selection_failures"]["b"] == 0


def test_opciones_son_fragmentos_originales_con_la_cita():
    context = " ".join(["prefix"] * 60 + ["TARGETCIT"] + ["suffix"] * 60)
    options = aa.evidence_options(context)
    assert len(options) == 3
    assert all(option in context and "TARGETCIT" in option for option in options)
    schema = aa.response_format(options)["json_schema"]["schema"]
    assert schema["properties"]["evidencia"]["enum"] == ["", *options]


def test_registro_corrupto_detiene_la_carga(workspace):
    workspace.log.parent.mkdir(parents=True)
    workspace.log.write_text('{"a": 1}\n{incompleto', encoding="utf-8")
    with pytest.raises(ValueError, match="línea 2"):
        aa.load_state(workspace.template, workspace.log)


# --- Annotator con cliente falso ----------------------------------------------------

class FakeAPIError(Exception):
    def __init__(self, status_code=None, retry_after=None):
        super().__init__("error del proveedor")
        self.status_code = status_code
        self.response = SimpleNamespace(headers={"retry-after": retry_after} if retry_after else {})


def response(content, finish_reason="stop"):
    message = SimpleNamespace(content=content, refusal=None)
    return SimpleNamespace(id="resp", model=aa.CONFIG["model"], usage=None,
                           choices=[SimpleNamespace(finish_reason=finish_reason, message=message)])


class FakeClient:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def annotate(ws, client, sleeps, case):
    return aa.annotate_case(case, client, ws.template, ws.log, provider_errors=(FakeAPIError,),
                            sleep=sleeps.append, progress=lambda *_: None)


def test_reintento_incluye_respuesta_previa_y_temperatura(workspace):
    bad = json.dumps(answer("Earlier work uses parsing heavily"))
    client = FakeClient([response(bad), response(json.dumps(answer()))])
    assert annotate(workspace, client, [], workspace.cases["a"]) == answer()
    assert all(call["temperature"] == aa.CONFIG["temperature"] and call["model"] == aa.CONFIG["model"] for call in client.calls)
    retry = client.calls[1]["messages"]
    assert retry[-2] == {"role": "assistant", "content": bad}
    assert retry[-1]["role"] == "user" and "rechazada" in retry[-1]["content"]
    first, second = aa.read_log(workspace.log)
    assert (first["error_kind"], first["error_code"]) == ("respuesta", "evidencia")
    assert second["status"] == "ok" and second["correction"] == retry[-1]["content"]


def test_agota_intentos_y_devuelve_none(workspace):
    bad = response(json.dumps(answer("Earlier work uses parsing heavily")))
    client = FakeClient([bad] * aa.CONFIG["max_attempts"])
    sleeps = []
    assert annotate(workspace, client, sleeps, workspace.cases["a"]) is None
    assert len(client.calls) == aa.CONFIG["max_attempts"] and len(sleeps) == aa.CONFIG["max_attempts"] - 1


def test_error_local_no_se_reintenta(workspace):
    client = FakeClient([SimpleNamespace(id="x", model=aa.CONFIG["model"], usage=object(), choices=[])])
    with pytest.raises(RuntimeError, match="Error local"):
        annotate(workspace, client, [], workspace.cases["a"])
    assert len(client.calls) == 1
    assert aa.read_log(workspace.log)[0]["error_kind"] == "local"


def test_429_respeta_retry_after(workspace):
    client = FakeClient([FakeAPIError(429, retry_after="7"), response(json.dumps(answer()))])
    sleeps = []
    assert annotate(workspace, client, sleeps, workspace.cases["a"])
    assert sleeps == [7.0]


def test_401_detiene_el_proceso(workspace):
    client = FakeClient([FakeAPIError(401)])
    with pytest.raises(RuntimeError, match="HTTP 401"):
        annotate(workspace, client, [], workspace.cases["a"])
    assert len(client.calls) == 1


# --- Flujo completo y salida única ----------------------------------------------------

def run(ws, client=None):
    return aa.run(ws.source, output_dir=ws.tmp / "anotaciones", log_dir=ws.tmp / "logs",
                  client=client, provider_errors=(FakeAPIError,), sleep=lambda _: None,
                  progress=lambda *_: None)


def _edit_cell(path, ref, text):
    with zipfile.ZipFile(path) as z:
        parts = {info.filename: z.read(info.filename) for info in z.infolist()}
    xml = parts["xl/worksheets/sheet1.xml"].decode("utf-8")
    parts["xl/worksheets/sheet1.xml"] = aa._patch_cell(xml, ref, text).encode("utf-8")
    with zipfile.ZipFile(path, "w") as z:
        for name, data in parts.items():
            z.writestr(name, data)


def test_salida_identifica_modelo_y_experimento(workspace):
    path = aa.output_path(workspace.source)
    assert path.parent == MODULE_PATH.parent / "anotaciones"
    assert path.name == f"plantilla__{aa.CONFIG['model']}.xlsx"


def test_run_solicita_solo_pendientes_y_omite_agotados(workspace):
    ws = workspace
    write_log(ws, [entry(ws, "a", "ok", result=answer()), *evidence_failures(ws, "c")])
    client = FakeClient([response(json.dumps(NO_EVALUABLE))])
    report = run(ws, client)
    assert len(client.calls) == 1
    assert json.loads(client.calls[0]["messages"][1]["content"])["context_id"] == "b"
    sheet = aa.read_sheets(report["output"])["Mis_anotaciones"]
    assert sheet[1][8:12] == ["Evaluable", "Background", "Media", answer()["justificacion"]]
    assert sheet[2][8:12] == ["No evaluable", "", "", answer()["justificacion"]]
    assert sheet[3][8:12] == ["", "", "", ""]
    rows = {r["context_id"]: r for r in csv.DictReader(report["review"].open(encoding="utf-8-sig"))}
    assert rows["c"]["motivo"] == "intentos_agotados"


def test_run_sin_pendientes_no_crea_cliente(workspace):
    ws = workspace
    write_log(ws, [entry(ws, cid, "ok", result=answer()) for cid in "abc"])
    assert run(ws)["filled"] == 3   # el fixture falla si se intenta crear el cliente


def test_actualizar_conserva_correcciones_y_revision(workspace):
    ws = workspace
    original = ws.source.read_bytes()
    write_log(ws, [entry(ws, "a", "ok", result=answer(), response_id="r-a"), *evidence_failures(ws, "b"),
                   *evidence_failures(ws, "c")])
    first = run(ws)
    assert first["created"] and first["filled"] == 1
    first_meta = json.loads(first["provenance"].read_text(encoding="utf-8"))

    # La persona corrige "a" en la salida y registra su revisión en el CSV.
    _edit_cell(first["output"], "J2", "Basis")
    rows = list(csv.DictReader(first["review"].open(encoding="utf-8-sig")))
    rows[0].update(estado_revision="revisado", revisor="JZ", notas="corregida")
    with first["review"].open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=aa.REVIEW_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    # Más tarde llega una propuesta para "b" (por ejemplo, tras corregir el registro).
    write_log(ws, [entry(ws, "b", "ok", 9, result=NO_EVALUABLE)])
    assert run(ws)["skipped"] is True
    # Exportación local explícita: no ejecuta ningún modelo.
    second = aa.export(ws.template, ws.log, aa.load_state(ws.template, ws.log), first["output"])

    assert not second["created"] and (second["filled"], second["kept"]) == (1, 1)
    assert sorted(p.name for p in second["output"].parent.iterdir()) == sorted(
        [second["output"].name, second["review"].name, second["provenance"].name, second["predictions"].name])
    sheet = aa.read_sheets(second["output"])["Mis_anotaciones"]
    assert sheet[1][9] == "Basis"
    assert sheet[2][8] == "No evaluable"
    rows = {r["context_id"]: r for r in csv.DictReader(second["review"].open(encoding="utf-8-sig"))}
    assert (rows["a"]["estado_revision"], rows["a"]["revisor"], rows["a"]["notas"]) == ("revisado", "JZ", "corregida")
    assert rows["a"]["origen_propuesta"] == "llm_directa" and rows["a"]["response_id"] == "r-a"
    assert rows["b"]["estado_revision"] == "pendiente"
    meta = json.loads(second["provenance"].read_text(encoding="utf-8"))
    assert meta["update_base"] == "salida_anterior" and meta["created_at"] == first_meta["created_at"]
    assert ws.source.read_bytes() == original


def test_salida_ajena_no_se_toca(workspace):
    ws = workspace
    write_log(ws, [entry(ws, "a", "ok", result=answer()), *evidence_failures(ws, "b"),
                   *evidence_failures(ws, "c")])
    other = build_template(ws.tmp / "otra.xlsx", ["z", "y", "x"]).read_bytes()
    output = aa.output_path(ws.source, ws.tmp / "anotaciones")
    output.parent.mkdir()
    output.write_bytes(other)
    assert run(ws)["skipped"] is True
    assert output.read_bytes() == other


def test_inserta_celda_que_excel_omitio():
    xml = '<sheetData><row r="2" spans="1:13"><c r="H2" s="1"/><c r="M2" s="1"><f>X</f></c></row></sheetData>'
    patched = aa._patch_cell(xml, "J2", "Basis")
    assert patched.index('r="H2"') < patched.index('r="J2"') < patched.index('r="M2"')
    assert aa._patch_cell('<row r="3"/>', "I3", "Evaluable").startswith('<row r="3"><c r="I3"')


def test_cli_solo_acepta_el_archivo_fuente(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(aa, "run", calls.append)
    assert aa.main([str(tmp_path / "x.xlsx")]) == 0
    assert calls == [tmp_path / "x.xlsx"]
    assert aa.main([]) == 0 and calls[-1] == aa.CONFIG["source"]
    with pytest.raises(SystemExit):
        aa.main(["x.xlsx", "--run"])


def test_modelos_separados_no_heredan_respuestas(workspace, monkeypatch):
    ws = workspace
    write_log(ws, [entry(ws, cid, 'ok', result=answer()) for cid in 'abc'])
    first = run(ws)
    monkeypatch.setitem(aa.CONFIG, 'model', 'otro/modelo')
    second_template = aa.read_template(ws.source)
    assert aa.log_path_for(second_template, ws.tmp / 'logs') != ws.log
    second = run(ws, FakeClient([response(json.dumps(NO_EVALUABLE)) for _ in 'abc']))
    assert first['output'] != second['output']
    assert 'otro-modelo' in second['output'].name
    assert aa.read_sheets(second['output'])['Mis_anotaciones'][1][8] == 'No evaluable'
    assert aa.read_sheets(first['output'])['Mis_anotaciones'][1][8] == 'Evaluable'


def test_temperatura_y_proveedor_separan_experimentos(workspace, monkeypatch):
    original = aa.experiment_tag(workspace.template)
    monkeypatch.setitem(aa.CONFIG, 'temperature', None)
    changed = aa.read_template(workspace.source)
    assert aa.experiment_tag(changed) != original
    monkeypatch.setitem(aa.CONFIG, 'base_url', 'https://example.invalid/v1/')
    assert aa.experiment_tag(aa.read_template(workspace.source)) != aa.experiment_tag(changed)


def test_omite_temperatura_si_es_none(workspace, monkeypatch):
    monkeypatch.setitem(aa.CONFIG, 'temperature', None)
    client = FakeClient([response(json.dumps(answer()))])
    annotate(workspace, client, [], workspace.cases['a'])
    assert 'temperature' not in client.calls[0]


def _comparator():
    spec = importlib.util.spec_from_file_location('comparar_anotaciones', MODULE_PATH.with_name('comparar_anotaciones.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.compare


def test_comparacion_consenso_y_abstencion(tmp_path):
    files = []
    for model, label in [('m1','Background'), ('m2','Background'), ('m3','Evidence')]:
        p=tmp_path / (model+'.json')
        p.write_text(json.dumps({'model': model, 'source_sha256': 'same', 'context_ids': ['a','b'],
                                'results': {'a':answer(funcion=label)}}))
        files.append(p)
    output = _comparator()(files,tmp_path/'comparison.csv')
    rows = list(csv.DictReader(output.open(encoding='utf-8-sig')))
    assert rows[0]['consenso_propuesto'] == 'Background'
    assert rows[0]['requiere_revision'] == 'True'
    assert rows[1]['consenso_propuesto'] == ''
    assert rows[1]['cobertura_completa'] == 'False'
    tied = _comparator()([files[0],files[2]],tmp_path/'tie.csv')
    assert list(csv.DictReader(tied.open(encoding='utf-8-sig')))[0]['consenso_propuesto'] == ''
    with pytest.raises(ValueError, match='votos duplicados'):
        _comparator()([files[0],files[0]],tmp_path/'duplicate.csv')
    data=json.loads(files[2].read_text());data['source_sha256']='different';files[2].write_text(json.dumps(data))
    with pytest.raises(ValueError, match='mismo Excel'):
        _comparator()([files[0],files[2]],tmp_path/'other.csv')


class FakeClaudeClient:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        value = self.outcomes.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def claude_response(content, stop_reason='end_turn'):
    return SimpleNamespace(id='msg-test', model=aa.CONFIG['model'], stop_reason=stop_reason,
                           usage=SimpleNamespace(model_dump=lambda: {'input_tokens': 100, 'output_tokens': 30}),
                           content=[SimpleNamespace(type='text', text=content)])


def test_claude_native_schema_retries_and_provenance(workspace, monkeypatch):
    ws=workspace
    monkeypatch.setitem(aa.CONFIG,'model','claude-haiku-5-5')
    monkeypatch.setitem(aa.CONFIG,'temperature',None)
    t=aa.read_template(ws.source)
    assert t['provider']=='anthropic' and t['run_key'] != ws.template['run_key']
    client=FakeClaudeClient([FakeAPIError(status_code=429), claude_response('invalido'),
                            *[claude_response(json.dumps(answer())) for _ in 'abc']])
    result=run(ws,client)
    assert len(client.calls)==5
    request=client.calls[0]
    assert request['system'].startswith('Realiza una PREANOTACIÓN')
    assert all(m['role']!='system' for m in request['messages'])
    assert request['output_config']['format']['schema']==aa.response_format(aa.evidence_options(CONTEXT))['json_schema']['schema']
    assert request['max_tokens']==2048
    assert 'temperature' not in request
    assert client.calls[2]['messages'][-1]['role']=='user'
    assert 'rechazada' in client.calls[2]['messages'][-1]['content']
    metadata=json.loads(result['provenance'].read_text())
    assert metadata['provider']=='anthropic'
    assert metadata['endpoint']=='https://api.anthropic.com'
    log=aa.read_log(aa.log_path_for(t,ws.tmp/'logs'))
    assert log[-1]['usage']['input_tokens']==100
    assert 'claude-haiku-5-5' in result['output'].name


@pytest.mark.parametrize('reason',['max_tokens','refusal'])
def test_claude_truncated_or_refused_not_accepted(workspace,monkeypatch,reason):
    monkeypatch.setitem(aa.CONFIG,'model','claude-haiku-5-5')
    monkeypatch.setitem(aa.CONFIG,'temperature',None)
    with pytest.raises(aa.ValidationError,match='incompleta'):
        aa._complete(FakeClaudeClient([claude_response(json.dumps(answer()),reason)]),
                     [{'role':'system','content':'guide'},{'role':'user','content':'case'}],{},[])


def test_claude_requires_no_temperature(workspace,monkeypatch):
    monkeypatch.setitem(aa.CONFIG,'model','claude-haiku-5-5')
    with pytest.raises(ValueError,match='temperature=None'):
        run(workspace)


def _multi():
    spec = importlib.util.spec_from_file_location('anotacion_multimodelo', MODULE_PATH.with_name('anotacion_multimodelo.py'))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_multimodel_discovery_filters_and_continues():
    multi=_multi()
    def broken():
        raise FakeAPIError(status_code=403)
    clients={
        'openai':SimpleNamespace(models=SimpleNamespace(list=lambda: iter([
            SimpleNamespace(id='gpt-text'),SimpleNamespace(id='gpt-audio'),
            SimpleNamespace(id='text-embedding'),SimpleNamespace(id='gpt-text')]))),
        'anthropic':SimpleNamespace(models=SimpleNamespace(list=broken))}
    catalog,errors=multi.discover(clients)
    assert len(catalog)==3
    assert [r['model'] for r in catalog if r['candidate']]==['gpt-text']
    assert errors[0]['http_status']==403


def test_budget_persists_and_blocks_before_paid_call(tmp_path):
    multi=_multi()
    path=tmp_path/'budget.json'
    budget=multi.Budget(path,limit='0.03')
    client=FakeClient([response(json.dumps(answer()))])
    proxy=multi.guarded_client(client,'openai','gpt-test',(1,1),budget,100)
    proxy.chat.completions.create(messages=[])
    assert len(client.calls)==1
    resumed=multi.Budget(path,limit='0.03')
    assert resumed.reserved==budget.reserved
    with pytest.raises(multi.BudgetExceeded):
        multi.guarded_client(client,'openai','gpt-test',(1,1),resumed,100).chat.completions.create(messages=[])
    assert len(client.calls)==1
    with pytest.raises(ValueError,match='entre 0 y 20'):
        multi.Budget(tmp_path/'other.json',21)


def test_queue_exports_partial_continues_and_restores_config(workspace,monkeypatch):
    multi=_multi();ws=workspace
    monkeypatch.setitem(aa.CONFIG,'output_dir',ws.tmp/'outputs')
    monkeypatch.setitem(aa.CONFIG,'log_dir',ws.tmp/'queue_logs')
    previous=aa.CONFIG.copy()
    client=FakeClient([response(json.dumps(answer())),FakeAPIError(status_code=404),
                       *[response(json.dumps(NO_EVALUABLE)) for _ in 'abc']])
    catalog=[{'provider':'openai','model':model,'candidate':True} for model in ['gpt-a','gpt-b','gpt-unknown']]
    def native_run(source,**kwargs):
        return aa.run(source,**kwargs,provider_errors=(FakeAPIError,),sleep=lambda _:None)
    budget=multi.Budget(ws.tmp/'budget.json',18)
    summary,files=multi.run_all(ws.source,catalog,{'openai':client},
                               {('openai','gpt-a'):(0.1,0.5),('openai','gpt-b'):(0.1,0.5)},
                               ws.tmp/'campaign',budget,run=native_run,progress=lambda _:None)
    assert [r['status'] for r in summary]==['error_modelo','procesado','falta_tarifa']
    assert [r.get('completed') for r in summary[:2]]==[1,3]
    assert len(files)==2 and all(p.exists() for p in files)
    assert aa.CONFIG==previous
    assert all(c['max_completion_tokens']==2048 for c in client.calls)
    # Incluso una salida parcial impide volver a ejecutar el modelo.
    resumed=FakeClient([response(json.dumps(answer())),response(json.dumps(answer()))])
    summary,files=multi.run_all(ws.source,catalog[:2],{'openai':resumed},
                               {('openai','gpt-a'):(0.1,0.5),('openai','gpt-b'):(0.1,0.5)},
                               ws.tmp/'campaign',budget,run=native_run,progress=lambda _:None)
    assert len(resumed.calls)==0
    assert all(r['status']=='omitido_archivo_existente' for r in summary)
    assert [r['completed'] for r in summary]==[1,3]


def test_mismo_modelo_salida_sin_hash_y_no_mezcla_configuraciones(workspace,monkeypatch):
    ws=workspace
    write_log(ws,[entry(ws,cid,'ok',result=answer()) for cid in 'abc'])
    first=run(ws)
    original=first['output'].read_bytes()
    monkeypatch.setitem(aa.CONFIG,'temperature',None)
    changed=aa.read_template(ws.source)
    assert aa.output_path(ws.source,ws.tmp/'anotaciones')==first['output']
    assert aa.log_path_for(changed,ws.tmp/'logs')!=ws.log
    with pytest.raises(ValueError,match='otro experimento'):
        aa.export(changed,ws.log,aa.load_state(ws.template,ws.log),first['output'])
    assert first['output'].read_bytes()==original


def test_salida_existente_omite_sin_cliente_tarifa_ni_reserva(workspace,monkeypatch):
    multi=_multi();ws=workspace
    monkeypatch.setitem(aa.CONFIG,'output_dir',ws.tmp/'outputs')
    with multi.configuration(model='gpt-existente'):
        output=aa.output_path(ws.source)
    output.parent.mkdir()
    output.write_bytes(b'archivo existente, no tocar')
    budget=multi.Budget(ws.tmp/'budget.json',18)
    summary,files=multi.run_all(ws.source,[{'provider':'openai','model':'gpt-existente','candidate':True}],
                               {},{},ws.tmp/'campaign',budget,run=lambda *a,**k:pytest.fail('No debe ejecutar'))
    assert summary[0]['status']=='omitido_archivo_existente'
    assert budget.reserved==0 and not files
    assert output.read_bytes()==b'archivo existente, no tocar'


def test_cliente_faltante_indica_sdk_y_kernel(monkeypatch,capsys):
    multi=_multi()
    monkeypatch.setenv('ANTHROPIC_API_KEY','fake-test-key-never-print')
    monkeypatch.setattr(multi.importlib.util,'find_spec',lambda _:None)
    with multi.connected_clients(['anthropic']) as clients:
        assert clients=={}
    message=capsys.readouterr().out
    assert '%pip install --upgrade anthropic' in message
    assert sys.executable in message
    assert 'fake-test-key' not in message


def test_presupuesto_concilia_tokens_y_conserva_reserva_si_falta_uso(tmp_path):
    multi=_multi();budget=multi.Budget(tmp_path/'budget.json',18)
    index=budget.reserve('openai','gpt-test',(1,2),{'messages':[]},2048)
    before=budget.reserved
    assert budget.settle(index,{'prompt_tokens':100,'completion_tokens':20},(1,2),'response-1')
    assert float(budget.reserved)==pytest.approx(0.00014)
    assert budget.data['reservations'][0]['reserved_usd_original']==str(before)
    assert not budget.settle(index,{},(1,2))
    assert not budget.settle(index,{'input_tokens':100,'output_tokens':20,'cache_creation_input_tokens':5},(1,2))


def test_conciliacion_historica_es_idempotente_y_respalda(tmp_path):
    multi=_multi();budget=multi.Budget(tmp_path/'budget.json',18)
    for _ in range(2):budget.reserve('openai','gpt-test',(1,2),{},2048)
    original=budget.path.read_bytes()
    log=tmp_path/'log.jsonl'
    for i in range(2):
        aa.append_log(log,{'provider':'openai','model':'gpt-test','response_id':str(i),
                           'usage':{'prompt_tokens':100,'completion_tokens':20}})
    assert budget.reconcile_logs([log],{('openai','gpt-test'):(1,2)})==2
    assert float(budget.reserved)==pytest.approx(0.00028)
    assert budget.path.with_name('budget.antes_conciliacion.json').read_bytes()==original
    assert budget.reconcile_logs([log],{('openai','gpt-test'):(1,2)})==0


def _consolidator():
    spec=importlib.util.spec_from_file_location('consolidar_anotaciones',MODULE_PATH.with_name('consolidar_anotaciones.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_consolidacion_votos_abstencion_auditoria_y_trazabilidad(workspace):
    module=_consolidator();ws=workspace
    predictions=ws.tmp/'predictions';predictions.mkdir()
    originals={}
    for index,(provider,model) in enumerate(module.DEFAULT_MODELS):
        results={'a':answer(funcion='Background' if index<5 else 'Evidence'),
                 'b':answer(funcion='Background' if index<3 else 'Evidence'),
                 'c':answer()}
        if index==3:results.pop('c')
        if index==5:results['c']=answer(evaluabilidad='Ambiguo',confianza='Baja')
        doc={'provider':provider,'model':model,'source_sha256':ws.template['sha256'],
             'context_ids':['a','b','c'],'results':results,'run_key':str(index)}
        path=predictions/f'{ws.source.stem}__{model}.predicciones.json'
        path.write_text(json.dumps(doc));originals[path]=path.read_bytes()
    metrics=module.consolidate(ws.source,predictions,ws.tmp/'consolidated')
    assert metrics['n_entradas']==3 and metrics['n_anotaciones_disponibles']==17
    assert metrics['n_consenso_provisional']==1 and metrics['n_revision_desacuerdos']==2
    assert metrics['n_auditoria_consensos']==1 and metrics['n_cola_revision_total']==3
    rows=json.loads((ws.tmp/'consolidated/dataset_consolidado.json').read_text())
    assert rows[0]['decision_automatica']=='consenso_provisional'
    assert rows[0]['votos_ganadores']==5 and rows[0]['seleccion_auditoria'] is True
    assert rows[1]['funcion_mas_votada']=='' and 'empate_o_sin_funcion' in rows[1]['motivos_revision']
    assert rows[2]['respuestas_disponibles']==5 and 'ambiguo_o_no_evaluable' in rows[2]['motivos_revision']
    assert all(r['funcion_final']=='' and r['revisor']=='' for r in rows)
    assert all(path.read_bytes()==content for path,content in originals.items())
    pairs=list(csv.DictReader((ws.tmp/'consolidated/acuerdo_entre_modelos.csv').open(encoding='utf-8-sig')))
    assert len(pairs)==15
    assert all(int(r['funcion_n'])<=3 for r in pairs)
    # Reproducible selection, independent of output directory.
    module.consolidate(ws.source,predictions,ws.tmp/'again')
    assert json.loads((ws.tmp/'again/dataset_consolidado.json').read_text())==rows
    # A different source must never be silently joined by matching IDs.
    path=next(iter(originals));doc=json.loads(path.read_text());doc['source_sha256']='wrong';path.write_text(json.dumps(doc))
    with pytest.raises(ValueError,match='Fuente distinta'):
        module.consolidate(ws.source,predictions,ws.tmp/'bad')
    assert not (ws.tmp/'bad').exists()


def test_kappa_sin_pares_y_categorias_constantes():
    module=_consolidator()
    assert module.agreement([])=={'n':0,'agreement':None,'kappa':None}
    assert module.agreement([('a','a'),('a','a')])['kappa'] is None
    assert module.agreement([('a','a'),('b','b')])['kappa']==1


def test_consolidacion_cuatro_votos_prevalece_sobre_alertas(workspace):
    module=_consolidator();ws=workspace
    predictions=ws.tmp/'four_votes';predictions.mkdir()
    for index,(provider,model) in enumerate(module.DEFAULT_MODELS):
        # Four OpenAI votes suffice, even with two Claude abstentions or dissent.
        results={'a':answer(funcion='Application' if index<4 else 'Evidence'),
                 'b':answer() if index<4 else answer(evaluabilidad='Ambiguo',confianza='Baja'),
                 'c':answer(funcion='Background' if index<3 else 'Evidence')}
        doc={'provider':provider,'model':model,'source_sha256':ws.template['sha256'],
             'context_ids':['a','b','c'],'results':results}
        (predictions/f'{ws.source.stem}__{model}.predicciones.json').write_text(json.dumps(doc))
    metrics=module.consolidate(ws.source,predictions,ws.tmp/'four_output',min_votes=4,audit_fraction=0)
    rows=json.loads((ws.tmp/'four_output/dataset_consolidado.json').read_text())
    assert metrics['n_consenso_provisional']==2
    assert rows[0]['funcion_consenso']=='Application' and not rows[0]['requiere_revision']
    assert 'sin_respaldo_entre_proveedores' in rows[0]['alertas_calidad']
    assert rows[1]['funcion_consenso']=='Background' and 'ambiguo_o_no_evaluable' in rows[1]['alertas_calidad']
    assert rows[2]['requiere_revision'] and rows[2]['funcion_consenso']==''
    assert all(r['funcion_final']=='' for r in rows)


def test_pareja_prioritaria_resuelve_pendientes_sin_reemplazar_mayoria(workspace):
    module=_consolidator();ws=workspace
    predictions=ws.tmp/'pair_inputs';predictions.mkdir()
    for index,(provider,model) in enumerate(module.DEFAULT_MODELS):
        # a: Sol/Opus agree on a minority of 2 vs plurality of 3.
        # b: 4 votes prevail even if Sol/Opus agree on a different function.
        # c: same function string but Sol says Ambiguo, so no pair acceptance.
        a='Evidence' if index in (3,5) else ('Background' if index in (0,1,2) else 'Basis')
        b='Evidence' if index in (3,5) else 'Background'
        c='Evidence' if index in (3,5) else ('Background' if index in (0,1) else 'Basis')
        results={'a':answer(funcion=a),'b':answer(funcion=b),'c':answer(funcion=c)}
        if index==3:results['c']=answer(funcion=c,evaluabilidad='Ambiguo',confianza='Baja')
        doc={'provider':provider,'model':model,'source_sha256':ws.template['sha256'],
             'context_ids':['a','b','c'],'results':results}
        (predictions/f'{ws.source.stem}__{model}.predicciones.json').write_text(json.dumps(doc))
    metrics=module.consolidate(ws.source,predictions,ws.tmp/'pair_output',min_votes=4,
                               agreement_pair=('claude-opus-5-5','gpt-6-sol'),audit_fraction=0)
    rows=json.loads((ws.tmp/'pair_output/dataset_consolidado.json').read_text())
    assert rows[0]['funcion_consenso']=='Evidence' and rows[0]['funcion_mas_votada']=='Background'
    assert rows[0]['regla_aceptacion']=='coincidencia_pareja_prioritaria'
    assert rows[0]['votos_funcion_consenso']==2
    assert rows[1]['funcion_consenso']=='Background' and rows[1]['regla_aceptacion']=='minimo_votos'
    assert rows[2]['requiere_revision'] and not rows[2]['funcion_consenso']
    assert metrics['aceptaciones_por_regla']=={'coincidencia_pareja_prioritaria':1,'minimo_votos':1}
    assert all(r['funcion_final']=='' for r in rows)


def test_excel_resultado_preserva_orden_y_csv_solo_rellena_pendientes(workspace):
    from src.resultado_anotaciones import build_result,CSV_FIELDS
    ws=workspace
    rows=[]
    for case in ws.template['cases']:
        rows.append({'context_id':case['context_id'],'contexto_original':case['contexto'],
                     'titulo_citado':case['titulo'],'resumen_citado':case['resumen'],
                     'requiere_revision':case['context_id']!='a','funcion_consenso':'Background',
                     'regla_aceptacion':'minimo_votos','claude-opus-5-5__evaluabilidad':'Evaluable',
                     'claude-opus-5-5__funcion':'Background','claude-opus-5-5__confianza':'Alta',
                     'claude-opus-5-5__justificacion':'Presenta antecedentes del trabajo.'})
    dataset=ws.tmp/'consolidado.json';dataset.write_text(json.dumps(rows))
    original=ws.source.read_bytes();output=ws.tmp/'resultado.xlsx'
    info=build_result(dataset,output,template=ws.source)
    assert info['automaticas']==1 and info['pendientes']==2
    sheet=aa.read_sheets(output)['Mis_anotaciones']
    assert [r[1] for r in sheet[1:]]==['a','b','c']
    assert sheet[1][8:12]==['Evaluable','Background','Alta','Presenta antecedentes del trabajo.']
    assert not any(sheet[2][8:12])
    csvfile=ws.tmp/'revisiones.csv'
    with csvfile.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f);writer.writerow(CSV_FIELDS)
        writer.writerow(['b','Evaluable','Evidence','Media','Respalda una afirmación.'])
    final=ws.tmp/'completado.xlsx'
    info=build_result(dataset,final,template=ws.source,reviews_csv=csvfile)
    assert info['humanas_importadas']==1 and info['pendientes']==1
    assert aa.read_sheets(final)['Mis_anotaciones'][2][9]=='Evidence'
    assert ws.source.read_bytes()==original
    # No se puede modificar una respuesta ya aceptada mediante el CSV humano.
    csvfile.write_text(csvfile.read_text(encoding='utf-8-sig').replace('b,Evaluable','a,Evaluable'),encoding='utf-8-sig')
    with pytest.raises(ValueError,match='ajeno'):
        build_result(dataset,ws.tmp/'rechazado.xlsx',template=ws.source,reviews_csv=csvfile)


def _v3_pipeline():
    directory=str(MODULE_PATH.parent)
    if directory not in sys.path:sys.path.insert(0,directory)
    spec=importlib.util.spec_from_file_location('anotacion_v3_dos_jueces',MODULE_PATH.with_name('anotacion_v3_dos_jueces.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_v3_coincidencia_exige_estado_y_funcion():
    pipeline=_v3_pipeline()
    assert pipeline.same_annotation(answer(),answer(confianza='Alta',justificacion='Otra explicación válida.'))
    assert not pipeline.same_annotation(answer(),answer(evaluabilidad='Ambiguo',confianza='Baja'))
    assert not pipeline.same_annotation(answer(),answer(funcion='Evidence'))
    with pytest.raises(ValueError):pipeline.validate_judgment({'eleccion':'C','confianza':'Alta','justificacion':'No válida'})


def test_v3_luna_solo_selecciona_una_respuesta_anonima(workspace):
    pipeline=_v3_pipeline();ws=workspace
    a=answer(funcion='Background');b=answer(funcion='Evidence')
    judgment={'eleccion':'B','confianza':'Media','justificacion':'La opción elegida respalda una afirmación concreta.'}
    client=FakeClient([response(json.dumps(judgment))])
    entries=[]
    result=pipeline.adjudicate(ws.cases['a'],a,b,client,ws.template,ws.tmp/'judge.jsonl',lambda p,r:entries.append(r))
    choices=pipeline.choices_for(ws.cases['a'],a,b)
    assert result['result']==choices['B']['result']
    assert result['selected_model']==choices['B']['model']
    payload=json.loads(client.calls[0]['messages'][1]['content'])
    assert set(payload['respuestas'])=={'A','B'}
    assert 'model' not in payload['respuestas']['A']
    assert client.calls[0]['model']=='gpt-6-luna'
    assert entries[0]['status']=='ok'
