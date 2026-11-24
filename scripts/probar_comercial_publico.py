"""Una sola llamada sintética al comercial desplegado; no ejecuta evaluaciones."""
import json
from pathlib import Path
import time
import urllib.request

BASE = 'https://api.proyectocitas-grupo19.click'
with urllib.request.urlopen(BASE + '/api/clasificadores', timeout=15) as response:
    catalog = json.load(response)
assert all(m['id'] != 'commercial' for m in catalog['clasificadores']), 'Debe seguir oculto en preparación'
payload = {'paper_id': 'W05-0821', 'consentimiento': True,
           'contexto': 'We use the language modeling approach described in TARGETCIT to improve a statistical machine translation system.'}
request = urllib.request.Request(BASE + '/api/comercial/clasificar', data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'})
start = time.monotonic()
with urllib.request.urlopen(request, timeout=30) as response:
    data = json.load(response)
assert data['paper_id'] == payload['paper_id']
assert data['modelo_solicitado'] == 'gpt-6.1-sol' and data['modelo_efectivo'].startswith('gpt-6.1-sol')
assert data['perfil'] == 'zero_shot_detailed'
assert data['tipo_puntuacion'] == 'puntajes_generados_no_calibrados'
assert len(data['puntuaciones']) == len({p['clase'] for p in data['puntuaciones']}) == 9
assert all(0 <= p['valor'] <= 1 for p in data['puntuaciones'])
report = {**data, 'url': BASE, 'llamadas': 1, 'latencia_total_segundos': round(time.monotonic()-start, 3),
          'contexto_inventado_sin_train_gold': True, 'contrato_comercial_verificado': True}
Path('artifacts/t09-aceptacion-real.json').write_text(json.dumps(report, indent=2))
print(json.dumps({k:report[k] for k in ['proveedor','modelo_efectivo','perfil','clase','abstencion','latencia_total_segundos','contrato_comercial_verificado']}, indent=2))
