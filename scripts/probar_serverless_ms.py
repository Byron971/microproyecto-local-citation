"""Bounded acceptance probe: local /invocations or an existing SageMaker endpoint.

Never creates resources. At most six calls, no SDK/CLI automatic retries.
Only synthetic inputs and prepared public articles; outputs contain no input text.
"""
import argparse
import json
import os
import re
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument('--url')
    target.add_argument('--endpoint')
    parser.add_argument('--profile', default='josezambrana')
    parser.add_argument('--region', default='us-east-1')
    parser.add_argument('--include-long', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    synthetic = json.loads((ROOT / 'tests/fixtures/ms_sintetico_solicitud.json').read_text())
    reference = json.loads((ROOT / 'tests/fixtures/ms_sintetico_referencia.json').read_text())
    article = {'paper_id': 'W05-0821', 'contexto': 'We use the language modeling approach described in TARGETCIT to improve a statistical machine translation system.'}
    cases = [('synthetic_first', synthetic), ('synthetic_repeat', synthetic)] + [(f'article_repeat_{i}', article) for i in range(3)]
    if args.include_long:
        cases.append(('long_article', {'paper_id': 'D15-1167', 'contexto': 'We use the document sentiment classification approach described in TARGETCIT.'}))
    corpus = json.loads((ROOT / 'config/corpus_ms.json').read_text())['documentos']
    report = {'target': args.endpoint or args.url, 'calls_limit': len(cases), 'observations': [],
              'note': 'First request is not proof of a cloud cold start. Correlate with OverheadLatency/logs; local AMD64 may be emulated.'}
    ledger_path = args.output.parent / 'aws_call_ledger.json'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    ledger = json.loads(ledger_path.read_text()) if args.endpoint and ledger_path.exists() else {'calls': 0}
    with tempfile.TemporaryDirectory(prefix='ms-probe-') as directory:
        request_path, response_path = Path(directory) / 'request.json', Path(directory) / 'response.json'
        for label, payload in cases:
            started = time.monotonic()
            try:
                data = json.dumps(payload).encode()
                if args.url:
                    request = urllib.request.Request(args.url.rstrip('/') + '/invocations', data=data, headers={'Content-Type': 'application/json'})
                    with urllib.request.urlopen(request, timeout=75) as response:
                        result = json.load(response)
                else:
                    if ledger['calls'] >= 6:
                        raise RuntimeError('AWS_CALL_BUDGET_EXHAUSTED')
                    ledger['calls'] += 1
                    ledger_path.write_text(json.dumps(ledger, indent=2) + '\n')
                    request_path.write_bytes(data)
                    command = ['aws', 'sagemaker-runtime', 'invoke-endpoint', '--endpoint-name', args.endpoint,
                               '--body', 'fileb://' + str(request_path), '--content-type', 'application/json',
                               '--profile', args.profile, '--region', args.region, '--cli-connect-timeout', '5',
                               '--cli-read-timeout', '75', str(response_path)]
                    execution = subprocess.run(command, env={**os.environ, 'AWS_MAX_ATTEMPTS': '1'}, capture_output=True, timeout=85)
                    if execution.returncode:
                        failure = execution.stderr.decode(errors='replace')
                        code = re.search(r'An error occurred \(([^)]+)\)', failure)
                        raise RuntimeError('AWS_' + code.group(1) if code else 'AWS_INVOCATION_FAILED')
                    result = json.loads(response_path.read_text())
                assert len(result['top3']) == 3
                assert len({chunk['chunk_id'] for chunk in result['top3']}) == 3
                if 'paper_id' in payload:
                    assert result['articulo']['paper_id'] == payload['paper_id']
                    chunks = {chunk['chunk_id']: chunk['texto'] for chunk in corpus[payload['paper_id']]['candidatos']}
                    assert all(chunks[chunk['chunk_id']] == chunk['texto'] for chunk in result['top3'])
                else:
                    assert [chunk['chunk_id'] for chunk in result['top3']] == [chunk['chunk_id'] for chunk in reference['top3']]
                for variant in ('M', 'S'):
                    scores = result['clasificadores'][variant]['probabilidades']
                    assert len(scores) == 9 and len({score['clase'] for score in scores}) == 9
                    assert all(0 <= score['probabilidad'] <= 1 for score in scores)
                    assert abs(sum(score['probabilidad'] for score in scores) - 1) < .00002
                    if 'paper_id' not in payload:
                        assert result['clasificadores'][variant]['clase'] == reference['clasificadores'][variant]['clase']
                        for actual, expected in zip(scores, reference['clasificadores'][variant]['probabilidades']):
                            assert actual['clase'] == expected['clase']
                            assert abs(actual['probabilidad'] - expected['probabilidad']) <= .005
                observation = {'case': label, 'ok': True, 'seconds': round(time.monotonic() - started, 3),
                               'top3': [chunk['chunk_id'] for chunk in result['top3']],
                               'classes': {v: result['clasificadores'][v]['clase'] for v in ('M', 'S')}}
            except Exception as exc:
                observation = {'case': label, 'ok': False, 'seconds': round(time.monotonic() - started, 3), 'error_type': type(exc).__name__, 'error_code': str(exc) if isinstance(exc, RuntimeError) else None}
            report['observations'].append(observation)
            print(json.dumps(observation), flush=True)
            # Do not retry/overlap inference after a timeout or service failure.
            if not observation['ok']:
                break
    report['ok'] = len(report['observations']) == len(cases) and all(row['ok'] for row in report['observations'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
