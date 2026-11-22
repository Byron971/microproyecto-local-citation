"""Revisión local de citas. Ejecutar: .venv/bin/python -m src.revision_manual"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

ROOT = Path(__file__).resolve().parents[1]
STATIC = Path(__file__).with_name('revision_manual_static')
CLASSES = ['Background', 'Gap', 'Basis', 'Comparison', 'Application',
           'Improvement / Modification', 'Evidence', 'Identification of the Originator', 'Further Reading']
DEFINITIONS = [
    'Sitúa el trabajo en el contexto general de la literatura.',
    'Señala un vacío o limitación que justifica la investigación.',
    'Constituye el fundamento conceptual del trabajo actual.',
    'Contrasta explícitamente enfoques, propiedades o resultados.',
    'Usa directamente un método, herramienta o datos citados.',
    'Adapta, amplía o modifica un método o herramienta citados.',
    'Respalda una afirmación concreta del texto citante.',
    'Atribuye explícitamente el origen de una idea o método.',
    'Remite al lector a detalles o información complementaria.',
]


def latest_dataset():
    files = sorted((ROOT / 'notebooks/anotaciones/consolidado').glob('*/dataset_consolidado.json'))
    if not files:
        raise ValueError('No se encontró dataset_consolidado.json. Usa --dataset RUTA.')
    return files[-1]


class Decision(BaseModel):
    evaluabilidad: Literal['Evaluable', 'Ambiguo', 'No evaluable']
    funcion: str = Field(default='', max_length=100)
    confianza: Literal['Alta', 'Media', 'Baja']
    justificacion: str = Field(min_length=1, max_length=4000)
    version: int = Field(default=0, ge=0)

    @model_validator(mode='after')
    def check_decision(self):
        self.justificacion = self.justificacion.strip()
        if not self.justificacion:
            raise ValueError('Indica una justificación.')
        if self.evaluabilidad == 'Evaluable' and self.funcion not in CLASSES:
            raise ValueError('Selecciona una de las nueve funciones.')
        if self.evaluabilidad != 'Evaluable' and self.funcion:
            raise ValueError('Ambiguo o No evaluable debe tener función vacía.')
        return self


class ReviewStore:
    def __init__(self, dataset, database=None):
        self.dataset = Path(dataset).resolve()
        data = self.dataset.read_bytes()
        self.sha = hashlib.sha256(data).hexdigest()
        self.rows = json.loads(data)
        self.index = {r['context_id']: r for r in self.rows}
        if not self.rows or len(self.index) != len(self.rows):
            raise ValueError('Dataset vacío o con IDs duplicados.')
        self.queue = [r for r in self.rows if r['requiere_revision']]
        self.ids = {r['context_id'] for r in self.queue}
        self.database = Path(database) if database else self.dataset.parent / f'revision_humana_{self.sha[:12]}.sqlite3'
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.lock = Lock()
        with self.connect() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS source (sha TEXT PRIMARY KEY)')
            existing = conn.execute('SELECT sha FROM source').fetchone()
            if existing and existing[0] != self.sha:
                raise ValueError('La base de revisiones pertenece a otro consolidado.')
            conn.execute('INSERT OR IGNORE INTO source VALUES (?)', (self.sha,))
            conn.execute('CREATE TABLE IF NOT EXISTS decisions (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
            conn.execute('CREATE TABLE IF NOT EXISTS history (event INTEGER PRIMARY KEY, id TEXT, payload TEXT NOT NULL)')

    def connect(self):
        return sqlite3.connect(self.database, timeout=10)

    def decisions(self):
        with self.connect() as conn:
            return {i: json.loads(payload) for i, payload in conn.execute('SELECT id, payload FROM decisions')}

    def save(self, cid, decision):
        if cid not in self.ids:
            raise HTTPException(404, 'La cita no pertenece a la cola de revisión humana.')
        with self.lock, self.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT payload FROM decisions WHERE id=?', (cid,)).fetchone()
            current_version = json.loads(row[0])['version'] if row else 0
            if decision.version != current_version:
                raise HTTPException(409, 'La decisión cambió en otra pestaña. Recarga antes de guardar.')
            record = {**decision.model_dump(), 'version': current_version + 1,
                      'fecha': datetime.now(timezone.utc).isoformat(), 'context_id': cid}
            encoded = json.dumps(record, ensure_ascii=False)
            conn.execute('INSERT OR REPLACE INTO decisions VALUES (?,?)', (cid, encoded))
            conn.execute('INSERT INTO history (id,payload) VALUES (?,?)', (cid, encoded))
        return record

    def export(self, only_human=False):
        decisions = self.decisions()
        result = []
        for original in self.rows:
            r = original.copy()
            d = decisions.get(r['context_id'])
            if only_human and d is None:
                continue
            if d:
                r.update(final_evaluabilidad=d['evaluabilidad'], funcion_final=d['funcion'],
                         revisor=d.get('revisor',''), fecha_revision=d['fecha'],
                         justificacion_revision=d['justificacion'], confianza_humana=d['confianza'],
                         revision_humana_pendiente=False, evaluabilidad_resuelta=d['evaluabilidad'],
                         funcion_resuelta=d['funcion'], origen_resolucion='revision_humana', version_revision=d['version'])
            elif not r['requiere_revision']:
                r.update(evaluabilidad_resuelta='Evaluable', funcion_resuelta=r['funcion_consenso'],
                         origen_resolucion='consenso_automatico', confianza_humana='', version_revision='')
            else:
                r.update(evaluabilidad_resuelta='', funcion_resuelta='', origen_resolucion='pendiente',
                         confianza_humana='', version_revision='')
            result.append(r)
        return result


def create_app(dataset=None, database=None):
    store = ReviewStore(dataset or latest_dataset(), database)
    app = FastAPI(title='Mesa de revisión de citas', docs_url=None, redoc_url=None)
    app.state.store = store
    app.mount('/static', StaticFiles(directory=STATIC), name='static')

    @app.get('/')
    def index():
        return FileResponse(STATIC / 'index.html')

    @app.get('/api/session')
    def session():
        return {'source': store.dataset.parent.name, 'source_sha256': store.sha,
                'total_dataset':len(store.rows), 'accepted_automatically':len(store.rows)-len(store.queue),
                'cases':store.queue, 'decisions':store.decisions(),
                'classes':[{'name':name,'definition':definition} for name,definition in zip(CLASSES,DEFINITIONS)]}

    @app.put('/api/decisions/{cid}')
    def save(cid: str, decision: Decision):
        return store.save(cid, decision)

    @app.get('/api/export/{kind}')
    def export(kind: str):
        if kind == 'resultado.xlsx':
            path=ROOT/'notebooks/anotaciones/TestGold_T1_v2_Zambrana__resultado.xlsx'
            metadata=path.with_suffix('.procedencia.json')
            if not path.exists() or not metadata.exists():
                raise HTTPException(404,'Todavía no se ha generado el Excel de resultado.')
            if json.loads(metadata.read_text(encoding='utf-8')).get('dataset_sha256')!=store.sha:
                raise HTTPException(409,'El Excel de resultado corresponde a otra versión del consolidado.')
            return FileResponse(path,filename=path.name)
        if kind not in {'dataset.json', 'dataset.csv', 'revisiones.csv'}:
            raise HTTPException(404, 'Exportación no disponible.')
        rows = store.export(only_human=kind=='revisiones.csv')
        if kind.endswith('.json'):
            payload = json.dumps(rows, ensure_ascii=False, indent=2).encode()
            mime = 'application/json'
        else:
            if kind=='revisiones.csv':
                from src.resultado_anotaciones import CSV_FIELDS
                decisions=store.decisions()
                rows=[dict(zip(CSV_FIELDS,[r['context_id'],d['evaluabilidad'],d['funcion'],d['confianza'],d['justificacion']]))
                      for r in sorted(store.queue,key=lambda r:r.get('fila_excel',0))
                      if (d:=decisions.get(r['context_id'])) is not None]
            # Protege la apertura en Excel: textos que podrían interpretarse como
            # fórmulas se exportan como texto. El JSON mantiene los valores originales.
            def safe(value):
                if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@')):
                    return "'" + value
                return value
            headers = CSV_FIELDS if kind=='revisiones.csv' else list(dict.fromkeys(k for row in rows for k in row)) or ['context_id']
            buffer = io.StringIO(newline='')
            writer = csv.DictWriter(buffer, fieldnames=headers)
            writer.writeheader()
            writer.writerows({k:safe(v) for k,v in r.items()} for r in rows)
            payload = buffer.getvalue().encode('utf-8-sig')
            mime = 'text/csv; charset=utf-8'
        return Response(payload, media_type=mime, headers={'Content-Disposition':f'attachment; filename="revision_{kind}"'})

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',type=Path)
    parser.add_argument('--port',type=int,default=8765)
    args = parser.parse_args()
    import uvicorn
    app = create_app(args.dataset)
    print(f'Revisión local: http://127.0.0.1:{args.port}')
    print(f'Dataset: {app.state.store.dataset}')
    print(f'Decisiones: {app.state.store.database}')
    uvicorn.run(app,host='127.0.0.1',port=args.port)


if __name__ == '__main__':
    main()
