"""POST de aceptación a una API científica ya iniciada (sin imprimir textos)."""
import argparse
import json
import time
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8012')
    parser.add_argument('--estado-path', default='/health/ready')
    parser.add_argument('--solicitud', type=Path, required=True)
    parser.add_argument('--referencia', type=Path, required=True)
    parser.add_argument('--salida', type=Path, required=True)
    parser.add_argument('--timeout', type=float, default=300, help='Segundos máximos para el POST')
    args = parser.parse_args()
    with urllib.request.urlopen(args.url + args.estado_path, timeout=10) as response:
        state = json.load(response)
        assert state.get('listo', state.get('modelos_cargados')) is True
    request = urllib.request.Request(args.url + '/api/analisis-cita-ms',
                                     data=args.solicitud.read_bytes(),
                                     headers={'Content-Type': 'application/json'})
    start = time.monotonic()
    with urllib.request.urlopen(request, timeout=args.timeout) as response:
        result = json.load(response)
    reference = json.loads(args.referencia.read_text(encoding='utf-8-sig'))
    assert [x['chunk_id'] for x in result['top3']] == [x['chunk_id'] for x in reference['top3']]
    for name in ('M', 'S'):
        model, expected = result['clasificadores'][name], reference['clasificadores'][name]
        assert model['clase'] == expected['clase']
        assert len(model['probabilidades']) == 9
        assert abs(sum(x['probabilidad'] for x in model['probabilidades']) - 1) < 0.00002
        for actual, wanted in zip(model['probabilidades'], expected['probabilidades']):
            assert actual['clase'] == wanted['clase']
            assert abs(actual['probabilidad'] - wanted['probabilidad']) <= 0.005
    report = {'ok': True, 'segundos_post': round(time.monotonic() - start, 3),
              'top3_ids': [x['chunk_id'] for x in result['top3']],
              'clasificadores': {name: {'clase': result['clasificadores'][name]['clase'],
                                      'probabilidad': result['clasificadores'][name]['probabilidad']}
                                for name in ('M', 'S')}}
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
