"""Extrae JSON del snapshot Git local fijado; verifica cada blob, sin red ni LFS."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

REVISION='300ee6c5e5629d042bfc07cbc406e2f330b53659'


def descargar(source, cache, papers_path, batch_size=250, limit=None):
    env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_LFS_SKIP_SMUDGE':'1','GIT_NO_LAZY_FETCH':'1'}
    git=['git','-C',str(source),'-c','protocol.version=1']
    if subprocess.check_output(git+['rev-parse','HEAD'],text=True).strip()!=REVISION:
        raise ValueError('Revisión Git del corpus distinta')
    tree=subprocess.check_output(git+['ls-tree','-r','HEAD','Base_JSON'],text=True)
    paths={}
    for line in tree.splitlines():
        spec,path=line.split('\t',1)
        mode,kind,oid=spec.split()
        if mode=='100644' and kind=='blob': paths[path]=oid
    papers=json.loads(papers_path.read_text())
    cache.mkdir(parents=True,exist_ok=True)
    todo=[]; verified=0;missing=0
    for pid in sorted(papers):
        path=f'Base_JSON/prefix{pid[0]}/json/{pid[:3]}/{pid}.json'
        if path not in paths:
            missing+=1;continue
        oid=paths[path];target=cache/(pid+'.json')
        if target.exists():
            raw=target.read_bytes()
            if hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()!=oid:
                raise ValueError('Caché distinta del blob de origen: '+pid)
            verified+=1
        else: todo.append((pid,oid))
    if limit: todo=todo[:limit]
    present=set(subprocess.check_output(git+['cat-file','--batch-all-objects','--batch-check=%(objectname)'],text=True,env=env).splitlines())
    if any(oid not in present for _,oid in todo):
        raise ValueError('Complete primero la transferencia Git del snapshot; faltan blobs locales')
    started=time.monotonic()
    for start in range(0,len(todo),batch_size):
        batch=todo[start:start+batch_size]
        proc=subprocess.Popen(git+['cat-file','--batch'],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE)
        proc.stdin.write(('\n'.join(oid for _,oid in batch)+'\n').encode());proc.stdin.close()
        for pid,oid in batch:
            head=proc.stdout.readline().decode().strip().split()
            if len(head)!=3 or head[0]!=oid or head[1]!='blob' or int(head[2])>10_000_000:
                proc.kill();raise ValueError('Blob de origen inválido: '+pid)
            raw=proc.stdout.read(int(head[2]))
            if len(raw)!=int(head[2]) or proc.stdout.read(1)!=b'\n':
                proc.kill();raise ValueError('Blob incompleto: '+pid)
            if hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()!=oid:
                proc.kill();raise ValueError('Hash del blob distinto: '+pid)
            target=cache/(pid+'.json');temporary=target.with_suffix('.partial')
            temporary.write_bytes(raw);temporary.replace(target)
        if proc.wait()!=0: raise RuntimeError('No se pudo leer el lote Git')
        print(json.dumps(dict(descargados=min(start+len(batch),len(todo)),reutilizados=verified,pendientes=max(0,len(todo)-start-len(batch)),sin_archivo=missing,segundos=round(time.monotonic()-started))),flush=True)
    return dict(revision=REVISION,descargados=len(todo),reutilizados=verified,sin_archivo=missing)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--cache',type=Path,default=Path('artifacts/coverage_expansion/cache')/REVISION)
    p.add_argument('--papers',type=Path,default=Path('data/raw/papers.json'))
    p.add_argument('--batch-size',type=int,choices=range(1,251),default=250)
    p.add_argument('--limit',type=int)
    a=p.parse_args()
    print(json.dumps(descargar(a.source,a.cache,a.papers,a.batch_size,a.limit)),flush=True)


if __name__=='__main__':main()
