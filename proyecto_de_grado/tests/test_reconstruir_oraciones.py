"""G1.2: conservacion del contexto, abstenciones y oraciones candidatas."""
from proyecto_de_grado.src.data.reconstruir_oraciones import (
    enmascarar_span_de_cita, grupo_ambiguo, limites_oracion, reconstruir_caso,
)


def ejemplo():
    cid = "CIT-REF-0"
    original = (
        "An earlier method established these procedures. "
        "Our approach adopts rich features from the previous system "
        "( TARGETCIT . However scalability remains limited."
    )
    ctx = {cid: {"citing_id": "CIT", "refid": "REF", "masked_text": original}}
    papers = {"REF": {"title": "An Effective Scientific Method for Citations"}}
    txt = (
        "An earlier method established these procedures. "
        "Our approach adopts rich features from the previous system "
        "(Feng and Hirst, 2012) . However scalability remains limited."
    )
    span_start = txt.index("(Feng and Hirst, 2012)")
    span = {
        "ref_id": "BIBREF4", "text": "(Feng and Hirst, 2012)",
        "start": span_start,
        "end": span_start + len("(Feng and Hirst, 2012)")
    }
    doc = {"paper_id": "CIT", "pdf_parse": {
        "bib_entries": {"BIBREF4": {"title": papers["REF"]["title"]}},
        "body_text": [{"text": txt, "section": "Methods", "cite_spans": [span]}],
    }}
    fila = {"context_id": cid, "split": "train", "citing_id": "CIT",
            "cited_id": "REF", "parrafo_texto": "0", "score_texto": "1.0"}
    return fila, ctx, papers, doc


def test_unica_referencia_con_evidencia_da_candidato_para_revision():
    fila, ctx, papers, doc = ejemplo()
    r = reconstruir_caso(fila, ctx, papers, doc)
    assert r["estado"] == "reconstruccion_candidata_revision_humana"
    assert "Feng and Hirst" in r["oracion_ocl_original"]
    assert r["oracion_con_targetcit"].count("TARGETCIT") == 1
    assert r["oracion_con_targetcit"].endswith("system (TARGETCIT).")
    assert r["oracion_ocl_original"].endswith("(Feng and Hirst, 2012) .")
    assert "Feng and Hirst" not in r["oracion_con_targetcit"]
    assert r["contexto_acl200"] == ctx[fila["context_id"]]["masked_text"]
    assert "requiere" in r["nota"]


def test_otros_citantes_en_el_grupo_fuerzan_revision_manual():
    fila, ctx, papers, doc = ejemplo()
    ctx[fila["context_id"]]["masked_text"] = (
        "Our approach adopts rich features from the previous system "
        "(OTHERCIT; TARGETCIT ; OTHERCIT). However scalability remains limited."
    )
    r = reconstruir_caso(fila, ctx, papers, doc)
    assert r["estado"] == "revision_manual"
    assert r["motivo"] == "TARGETCIT_cerca_de_OTHERCIT_grupo_potencial"


def test_no_confunde_otra_referencia_del_parrafo():
    fila, ctx, papers, doc = ejemplo()
    doc["pdf_parse"]["body_text"][0]["cite_spans"][0]["ref_id"] = "OTRA"
    r = reconstruir_caso(fila, ctx, papers, doc)
    assert r["estado"] == "revision_manual"
    assert r["oracion_ocl_original"] is None


def test_dos_citas_al_mismo_articulo_no_pueden_asignarse_por_adivinacion():
    fila, ctx, papers, doc = ejemplo()
    otro = dict(doc["pdf_parse"]["body_text"][0]["cite_spans"][0])
    doc["pdf_parse"]["body_text"][0]["cite_spans"].append(otro)
    r = reconstruir_caso(fila, ctx, papers, doc)
    assert r["estado"] == "revision_manual"
    assert r["motivo"] == "referencia_candidata_no_unica_en_parrafo"


def test_offset_invalido_no_se_reconstruye():
    fila, ctx, papers, doc = ejemplo()
    doc["pdf_parse"]["body_text"][0]["cite_spans"][0]["end"] = 99999
    r = reconstruir_caso(fila, ctx, papers, doc)
    assert r["estado"] == "revision_manual"


def test_parrafo_no_localizado_no_pasa():
    fila, ctx, papers, doc = ejemplo()
    fila["parrafo_texto"] = "77"
    r = reconstruir_caso(fila, ctx, papers, doc)
    assert r["estado"] == "revision_manual"


def test_abreviatura_et_al_no_corta_la_oracion_en_mitad():
    texto = "We reviewed Smith et al. 2012 results and then used (Jones, 2015). Next step."
    inicio = texto.index("(Jones, 2015)")
    a, b = limites_oracion(texto, inicio, inicio + len("(Jones, 2015)"))
    assert texto[a:b].strip().startswith("We reviewed")
    assert texto[a:b].strip().endswith("(Jones, 2015).")


def test_detector_de_grupo_no_confunde_otras_citas_distantes():
    assert grupo_ambiguo("We cited OTHERCIT in prior work. Now we cite TARGETCIT.")
    assert not grupo_ambiguo("We cited OTHERCIT in a lengthy earlier passage about alternative systems "
                             "but new evidence uses TARGETCIT here.")


def test_sin_doc_ocl_obliga_revision():
    fila, ctx, papers, _ = ejemplo()
    assert reconstruir_caso(fila, ctx, papers, None)["estado"] == "revision_manual"


def test_enmascarado_preserva_parentesis_sin_inventar_segunda_cita():
    assert enmascarar_span_de_cita("(Feng and Hirst, 2012)") == "(TARGETCIT)"
    assert enmascarar_span_de_cita("(Evans & Gazdar 1989)") == "(TARGETCIT)"
    assert enmascarar_span_de_cita("Smith 2012") == "TARGETCIT"


def test_enmascarado_rechaza_grupo_y_parentesis_incompletos():
    assert enmascarar_span_de_cita("(Smith, 2011; Jones, 2012)") is None
    assert enmascarar_span_de_cita("Jones, 2012)") is None
    assert enmascarar_span_de_cita("(Jones, 2012") is None
    assert enmascarar_span_de_cita("") is None


def test_cita_ambigua_por_span_grupal_es_revision_manual():
    fila, ctx, papers, doc = ejemplo()
    span = doc["pdf_parse"]["body_text"][0]["cite_spans"][0]
    texto = doc["pdf_parse"]["body_text"][0]["text"]
    texto_nuevo = texto.replace("(Feng and Hirst, 2012)", "(Feng and Hirst, 2012; Smith, 2013)")
    doc["pdf_parse"]["body_text"][0]["text"] = texto_nuevo
    span["text"] = "(Feng and Hirst, 2012; Smith, 2013)"
    span["end"] = span["start"] + len(span["text"])
    res = reconstruir_caso(fila, ctx, papers, doc)
    assert res["estado"] == "revision_manual"
    assert res["oracion_con_targetcit"] is None
