import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from src.revision_manual import create_app


def make_client(tmp_path):
    source=tmp_path/'dataset_consolidado.json'
    source.write_text(json.dumps([
        {'context_id':'pending','requiere_revision':True,'funcion_consenso':'',
         'contexto_original':'TARGETCIT discusses this.','titulo_citado':'Title',
         'resumen_citado':'Summary','revision_humana_pendiente':True,
         'final_evaluabilidad':'','funcion_final':'','revisor':'','fecha_revision':'','justificacion_revision':''},
        {'context_id':'accepted','requiere_revision':False,'funcion_consenso':'Background',
         'revision_humana_pendiente':False,'final_evaluabilidad':'','funcion_final':'','revisor':''}
    ]))
    return TestClient(create_app(source,tmp_path/'reviews.sqlite3')),source


def decision(**kwargs):
    return {'evaluabilidad':'Evaluable','funcion':'Evidence','confianza':'Alta',
            'justificacion':'Respalda una afirmación concreta.','version':0,**kwargs}


def test_revision_persiste_historial_y_conflictos(tmp_path):
    client,source=make_client(tmp_path);original=source.read_bytes()
    assert len(client.get('/api/session').json()['cases'])==1
    assert client.put('/api/decisions/accepted',json=decision()).status_code==404
    saved=client.put('/api/decisions/pending',json=decision())
    assert saved.status_code==200 and saved.json()['version']==1
    assert client.put('/api/decisions/pending',json=decision()).status_code==409
    changed=client.put('/api/decisions/pending',json=decision(version=1,funcion='Background'))
    assert changed.status_code==200
    reopened=TestClient(create_app(source,tmp_path/'reviews.sqlite3'))
    assert reopened.get('/api/session').json()['decisions']['pending']['funcion']=='Background'
    with sqlite3.connect(tmp_path/'reviews.sqlite3') as conn:
        assert conn.execute('select count(*) from history').fetchone()[0]==2
    assert source.read_bytes()==original


def test_validacion_no_evaluable_y_exportacion_sin_inventar_decisiones(tmp_path):
    client,source=make_client(tmp_path)
    before=client.get('/api/export/dataset.json').json()
    assert before[0]['origen_resolucion']=='pendiente'
    assert before[1]['funcion_resuelta']=='Background'
    assert before[1]['funcion_final']==''
    assert client.put('/api/decisions/pending',json=decision(evaluabilidad='Ambiguo')).status_code==422
    assert client.put('/api/decisions/pending',json=decision(justificacion='   ')).status_code==422
    assert client.put('/api/decisions/pending',json=decision(funcion='Unknown')).status_code==422
    assert client.put('/api/decisions/pending',json=decision(evaluabilidad='No evaluable',funcion='')).status_code==200
    after=client.get('/api/export/dataset.json').json()
    assert after[0]['evaluabilidad_resuelta']=='No evaluable' and after[0]['funcion_resuelta']==''
    assert not after[0]['revision_humana_pendiente']
    assert client.get('/api/export/revisiones.csv').text.count('pending')==1
    assert client.get('/api/export/revisiones.csv').headers['content-disposition'].startswith('attachment')


def test_cambio_fuente_no_reutiliza_revisiones(tmp_path):
    import pytest
    client,source=make_client(tmp_path)
    source.write_text(source.read_text()+' ')
    with pytest.raises(ValueError,match='otro consolidado'):
        create_app(source,tmp_path/'reviews.sqlite3')


def test_csv_contiene_solo_campos_originales_y_id(tmp_path):
    import csv,io
    from src.resultado_anotaciones import CSV_FIELDS
    client,source=make_client(tmp_path)
    assert client.put('/api/decisions/pending',json=decision()).status_code==200
    text=client.get('/api/export/revisiones.csv').text.lstrip('\ufeff')
    reader=csv.DictReader(io.StringIO(text))
    assert reader.fieldnames==CSV_FIELDS
    rows=list(reader)
    assert len(rows)==1 and rows[0]['Función principal (una)']=='Evidence'
    assert 'revisor' not in rows[0] and 'fecha' not in rows[0]
