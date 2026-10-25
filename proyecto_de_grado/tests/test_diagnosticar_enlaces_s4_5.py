"""Pruebas locales de S4.5 (no requieren red ni ACL OCL reales)."""
import hashlib
import json
from pathlib import Path

import pytest

from proyecto_de_grado.src.evaluation.diagnosticar_enlaces_s4_5 import (
    parentesis_target, spans_por_ref, resumen_spans, verificar_fuentes,
)


def test_grupo_mismo_parentesis():
    assert parentesis_target('See (OTHERCIT; TARGETCIT).') == ('si', 'parentesis_visible')


def test_citas_parentesis_distintos():
    assert parentesis_target('Use (OTHERCIT) and (TARGETCIT).') == ('no', 'parentesis_visible')


def test_parentesis_incompleto_no_se_adivina():
    assert parentesis_target('Compare (TARGETCIT in this work')[0] == 'desconocido'


def test_entrada_sin_target_falla():
    with pytest.raises(ValueError):
        parentesis_target('No marker')


def test_spans_referencia_correcta_en_parrafo_y_en_otro():
    doc={'pdf_parse':{'body_text':[
        {'text':'Read (A).','cite_spans':[{'ref_id':'BIBREF1','start':5,'end':8,'text':'(A)'}]},
        {'text':'New (B).','cite_spans':[{'ref_id':'BIBREF1','start':4,'end':7,'text':'(B)'}]},
    ]}}
    got, all_p, outer=spans_por_ref(doc, {'BIBREF1'}, 0)
    assert len(got)==2 and len(all_p)==1 and len(outer)==1
    assert got[0]['offset_valido'] and got[0]['span_coincide_texto']


def test_span_incorrecto_no_se_acepta_por_indice():
    doc={'pdf_parse':{'body_text':[
        {'text':'See (A).','cite_spans':[{'ref_id':'BIBREF1','start':50,'end':52,'text':'(A)'}]}
    ]}}
    got, _, _=spans_por_ref(doc, {'BIBREF1'}, 0)
    assert len(got)==1 and not got[0]['offset_valido']


def test_spans_de_otra_referencia_no_cuentan():
    doc={'pdf_parse':{'body_text':[
        {'text':'See (A).','cite_spans':[{'ref_id':'BIBREF2','start':4,'end':7,'text':'(A)'}]}
    ]}}
    got, all_p, _=spans_por_ref(doc, {'BIBREF1'}, 0)
    assert got==[] and len(all_p)==1


def test_resumen_spans_limitado():
    datos=[{'parrafo':i,'ref_id':'BIBREF1','start':1,'end':2,'offset_valido':True,'span_coincide_texto':True} for i in range(5)]
    s=resumen_spans(datos, limite=2)
    assert '3 spans adicionales' in s


def test_manifest_hash_valido(tmp_path):
    for name in ('contexts.json','papers.json','train.json','val.json','test.json'):
        (tmp_path/name).write_text('{}',encoding='utf-8')
    hashes={n:hashlib.sha256((tmp_path/n).read_bytes()).hexdigest() for n in ('contexts.json','papers.json','train.json','val.json','test.json')}
    verificar_fuentes({'sha256_fuentes':hashes}, tmp_path)


def test_manifest_hash_cambiado_rechazado(tmp_path):
    for name in ('contexts.json','papers.json','train.json','val.json','test.json'):
        (tmp_path/name).write_text('{}',encoding='utf-8')
    hashes={n:hashlib.sha256((tmp_path/n).read_bytes()).hexdigest() for n in ('contexts.json','papers.json','train.json','val.json','test.json')}
    (tmp_path/'val.json').write_text('[]',encoding='utf-8')
    with pytest.raises(ValueError,match='val.json'):
        verificar_fuentes({'sha256_fuentes':hashes},tmp_path)
