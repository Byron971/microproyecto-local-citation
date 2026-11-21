"""Intervalo de confianza al 95 % del F1 macro por bootstrap (1.000 remuestreos de las 1.061 citas, semilla 2026).
Uso: python bootstrap_ic95.py <carpeta_con_resumen> (escribe bootstrap_ic95.json)"""
import json, random, sys
CL=['Background','Gap','Basis','Comparison','Application','Improvement / Modification','Evidence','Identification of the Originator','Further Reading']
gold={}
for i in range(1,5):
    for l in open(f'D:/tmp/costos/completo_{i}.jsonl',encoding='utf-8'):
        d=json.loads(l); gold[d['id']]=CL.index(d['gold'])
def f1m(pares):
    tp=[0]*9; fp=[0]*9; fn=[0]*9
    for g,p in pares:
        if g==p: tp[g]+=1
        else: fp[p]+=1; fn[g]+=1
    s=0
    for k in range(9):
        pr=tp[k]/(tp[k]+fp[k]) if tp[k]+fp[k] else 0; rc=tp[k]/(tp[k]+fn[k]) if tp[k]+fn[k] else 0
        s+=2*pr*rc/(pr+rc) if pr+rc else 0
    return s/9
random.seed(2026); out={}
for m in ('gemini','openai'):
    rs=[json.loads(l) for l in open(f'D:/tmp/costos/unido_{m}/results.jsonl',encoding='utf-8')]
    for pr in ('zero_shot_generic','zero_shot_detailed','few_shot'):
        pares=[(gold[r['case_id']],max(range(9),key=lambda k:(r['parsed_output'][k],-k))) for r in rs if r['prompt_name']==pr]
        v=sorted(f1m([random.choice(pares) for _ in pares]) for _ in range(1000))
        out[f'{m}|{pr}']=(round(f1m(pares),3),round(v[24],3),round(v[974],3))
json.dump(out,open(sys.argv[1]+'/bootstrap_ic95.json','w'),indent=1); print(out)
