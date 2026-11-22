"""Non-infrastructure T04 operations. Invoked exclusively by Makefile targets."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile

ACCOUNT, REGION, NAME = '646941583111', 'us-east-1', 'citas-ms-serverless-t04'
BUNDLE_HASH = 'b75e3075c4bf630d1b5aaf9c0ce7a2e43265446231ed550869e6df38b35def7f'
BUCKET = 'citas-api-models-646941583111-us-east-1'
KEY = f'experiments/t04-ms-serverless/{BUNDLE_HASH}/model.tar.gz'
ALLOWED = {'aws_ecr_repository.probe', 'aws_cloudwatch_log_group.probe[0]',
           'aws_iam_role.probe[0]', 'aws_iam_role_policy.probe[0]', 'aws_sagemaker_model.probe[0]',
           'aws_sagemaker_endpoint_configuration.probe[0]', 'aws_sagemaker_endpoint.probe[0]'}


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def check_plan(plan, destroy=False):
    changes = []
    for item in plan.get('resource_changes', []):
        if item['mode'] == 'data' or item['change']['actions'] == ['no-op']:
            continue
        if item['address'] not in ALLOWED:
            raise ValueError('Plan fuera del alcance T04: ' + item['address'])
        expected = ['delete'] if destroy else ['create']
        if item['change']['actions'] != expected:
            raise ValueError('Cambio no permitido: ' + item['address'])
        after = item['change']['after'] or {}
        if not destroy:
            if 'name' in after and item['type'] != 'aws_iam_role_policy' and after['name'] not in (NAME, '/aws/sagemaker/Endpoints/' + NAME):
                raise ValueError('Nombre fuera de la prueba')
            if item['type'] == 'aws_s3_object' and (after['bucket'] != BUCKET or after['key'] != KEY):
                raise ValueError('Objeto S3 fuera de la prueba')
            if item['type'] == 'aws_sagemaker_endpoint_configuration':
                variants = after['production_variants']
                config = variants[0]['serverless_config'][0]
                if len(variants) != 1 or config['memory_size_in_mb'] != 6144 or config['max_concurrency'] != 1 or config.get('provisioned_concurrency') not in (None, 0):
                    raise ValueError('Capacidad fuera del presupuesto de la prueba')
        changes.append(item['address'])
    return changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('action', choices=['preflight', 'check-plan', 'check-destroy', 'push', 'enable', 'observe', 'check-current', 'cancel-upload'])
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--image')
    parser.add_argument('--pid', type=int)
    args = parser.parse_args()
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    os.chmod(work, 0o700)
    if os.environ.get('AWS_PROFILE') != 'josezambrana' or os.environ.get('AWS_REGION', REGION) != REGION:
        raise SystemExit('Esta prueba exige AWS_PROFILE=josezambrana y us-east-1')
    env = {**os.environ, 'AWS_MAX_ATTEMPTS': '1', 'AWS_PAGER': ''}

    def aws(*command, optional=False):
        result = subprocess.run(['aws', '--profile', 'josezambrana', '--region', REGION,
                                 '--cli-connect-timeout', '8', '--cli-read-timeout', '30', *command],
                                env=env, text=True, capture_output=True)
        if result.returncode:
            if optional:
                return {'error': result.stderr.strip()[:1000]}
            raise RuntimeError(result.stderr.strip())
        return json.loads(result.stdout) if result.stdout.strip() else {}

    def current():
        data = aws('ecs', 'describe-services', '--cluster', 'citas-api', '--services', 'citas-api', 'citas-api-science')
        if data.get('failures') or len(data.get('services', [])) != 2:
            raise RuntimeError('No se pudieron identificar ambos servicios actuales')
        return sorted([{'service': s['serviceName'], 'task_definition': s['taskDefinition'],
                        'desired_count': s['desiredCount']} for s in data['services']], key=lambda s: s['service'])

    if args.action in ('check-plan', 'check-destroy'):
        destroy = args.action == 'check-destroy'
        changes = check_plan(json.loads((work / ('cleanup.json' if destroy else 'plan.json')).read_text()), destroy)
        print(json.dumps({'validated': True, 'changes': changes}))
        return
    if args.action == 'cancel-upload':
        command = subprocess.check_output(['ps', '-p', str(args.pid), '-o', 'command='], text=True)
        if 'terraform -chdir=terraform/serverless_ms_probe apply' not in command:
            raise ValueError('El PID no corresponde al apply de esta prueba')
        os.kill(args.pid, signal.SIGINT)
        print('Solicitada interrupción gradual del apply local; se preserva el estado Terraform.')
        return
    identity = aws('sts', 'get-caller-identity')
    if identity['Account'] != ACCOUNT:
        raise SystemExit('Cuenta diferente: no se continúa')
    if args.action == 'preflight':
        bundle = args.bundle.resolve()
        with bundle.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != BUNDLE_HASH:
                raise ValueError('Hash incorrecto del bundle')
        baseline = work / 'ecs_before.json'
        snapshot = current()
        if baseline.exists() and json.loads(baseline.read_text()) != snapshot:
            raise RuntimeError('ECS difiere del registro previo; revisar antes de continuar')
        if not baseline.exists():
            save(baseline, snapshot)
        # Never claim or replace an unmanaged object/repository.
        if not (Path('terraform/serverless_ms_probe/terraform.tfstate').exists()):
            for service, command in [('ecr', ['describe-repositories', '--repository-names', NAME]),
                                     ('s3api', ['head-object', '--bucket', BUCKET, '--key', KEY])]:
                check = aws(service, *command, optional=True)
                if 'error' not in check:
                    raise RuntimeError('Recurso experimental ya existe sin estado local; no se reemplaza')
                if not any(code in check['error'] for code in ('RepositoryNotFoundException', '404', 'Not Found')):
                    raise RuntimeError(check['error'])
        state_path = Path('terraform/serverless_ms_probe/terraform.tfstate')
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        managed_object = any(r.get('type') == 'aws_s3_object' and r.get('name') == 'probe' for r in state.get('resources', []))
        if not managed_object:
            versions = aws('s3api', 'list-object-versions', '--bucket', BUCKET, '--prefix', KEY)
            if any(item['Key'] == KEY for group in ('Versions', 'DeleteMarkers') for item in versions.get(group, [])):
                raise RuntimeError('La clave experimental ya tiene historial ajeno al estado; no se reclama ni reemplaza')
        vars_path = work / 'probe.tfvars.json'
        if not vars_path.exists():
            save(vars_path, {'profile': 'josezambrana', 'bundle_path': str(bundle), 'deploy_endpoint': False, 'image_digest': ''})
        save(work / 'preflight.json', {'account': ACCOUNT, 'region': REGION, 'bundle_sha256': BUNDLE_HASH,
                                     'timestamp_utc': datetime.now(timezone.utc).isoformat()})
        print('Identidad, bundle y estado previo verificados. Variables de Terraform preparadas.')
    elif args.action == 'push':
        metadata = json.loads(subprocess.check_output(['docker', 'image', 'inspect', args.image]))[0]
        if metadata['Architecture'] != 'amd64':
            raise ValueError('Solo se publica la imagen AMD64')
        repo = aws('ecr', 'describe-repositories', '--repository-names', NAME)['repositories'][0]
        registry, uri = repo['registryId'] + '.dkr.ecr.' + REGION + '.amazonaws.com', repo['repositoryUri']
        tag = 't04-' + metadata['Id'].split(':')[1][:16]
        existing = aws('ecr', 'describe-images', '--repository-name', NAME, '--image-ids', 'imageTag=' + tag, optional=True)
        if 'error' in existing:
            if 'ImageNotFoundException' not in existing['error']:
                raise RuntimeError(existing['error'])
            print('Publicando capas de la imagen AMD64 en el ECR temporal…', flush=True)
            auth = subprocess.run(['aws', '--profile', 'josezambrana', '--region', REGION, 'ecr', 'get-login-password'], env=env, capture_output=True, check=True).stdout
            host = json.loads(subprocess.check_output(['docker', 'context', 'inspect']))[0]['Endpoints']['docker']['Host']
            with tempfile.TemporaryDirectory(prefix='t04-docker-') as directory:
                docker_env = {**env, 'DOCKER_CONFIG': directory, 'DOCKER_HOST': host}
                subprocess.run(['docker', 'login', '--username', 'AWS', '--password-stdin', registry], input=auth, env=docker_env, capture_output=True, check=True)
                subprocess.run(['docker', 'tag', args.image, uri + ':' + tag], env=docker_env, check=True)
                subprocess.run(['docker', 'push', uri + ':' + tag], env=docker_env, check=True)
            existing = aws('ecr', 'describe-images', '--repository-name', NAME, '--image-ids', 'imageTag=' + tag)
        digest = existing['imageDetails'][0]['imageDigest']
        save(work / 'published_image.json', {'local_image': metadata['Id'], 'image_digest': digest, 'repository': uri, 'tag': tag})
        print('Imagen publicada y digest ECR registrado: ' + digest)
    elif args.action == 'enable':
        config = json.loads((work / 'probe.tfvars.json').read_text())
        builder = Path('artifacts/image_builder')
        image = json.loads((builder / 'published-images.json').read_text())['images']['serverless']
        model = json.loads((builder / 'published-models.json').read_text())
        digest = image['uri'].split('@')[1]
        if image['architecture'] != 'amd64' or not model['remote_bytes_verified'] or model['sha256'] != BUNDLE_HASH:
            raise ValueError('Artefactos EC2 sin validación suficiente')
        published = aws('ecr', 'describe-images', '--repository-name', NAME, '--image-ids', 'imageTag=' + image['tag'])['imageDetails'][0]
        manifest = aws('ecr', 'batch-get-image', '--repository-name', NAME, '--image-ids', 'imageDigest=' + digest)['images'][0]
        if json.loads(manifest['imageManifest'])['mediaType'] != 'application/vnd.docker.distribution.manifest.v2+json':
            raise ValueError('SageMaker exige manifiesto Docker V2; ejecutar builder-compatible')
        head = aws('s3api', 'head-object', '--bucket', BUCKET, '--key', KEY)
        if published['imageDigest'] != digest or head['ContentLength'] != model['bytes'] or head.get('VersionId') != model['version_id'] or head.get('Metadata', {}).get('sha256') != BUNDLE_HASH:
            raise ValueError('Los artefactos AWS cambiaron desde la validación')
        save(work / 'published_image.json', {'image_digest': digest, 'repository': image['uri'].split('@')[0], 'tag': image['tag']})
        config.update(deploy_endpoint=True, image_digest=digest)
        save(work / 'probe.tfvars.json', config)
        print('Variables locales actualizadas; aún se requiere plan/apply Terraform.')
    elif args.action == 'check-current':
        after = current()
        same = after == json.loads((work / 'ecs_before.json').read_text())
        save(work / 'ecs_after.json', {'unchanged': same, 'services': after})
        if not same:
            raise RuntimeError('ECS difiere del estado inicial')
        print('ECS conserva task definitions y capacidad anteriores.')
    else:
        now = datetime.now(timezone.utc)
        report = {'timestamp_utc': now.isoformat(), 'model': aws('sagemaker', 'describe-model', '--model-name', NAME, optional=True), 'endpoint': aws('sagemaker', 'describe-endpoint', '--endpoint-name', NAME, optional=True)}
        if 'error' not in report['endpoint']:
            report['endpoint_config'] = aws('sagemaker', 'describe-endpoint-config', '--endpoint-config-name', NAME, optional=True)
        report['logs'] = aws('logs', 'filter-log-events', '--log-group-name', '/aws/sagemaker/Endpoints/' + NAME,
                             '--start-time', str(int((now-timedelta(hours=2)).timestamp()*1000)), '--limit', '100', optional=True)
        report['metrics'] = {}
        for metric in ('OverheadLatency', 'ModelLatency', 'ModelSetupTime', 'MemoryUtilization', 'Invocations', 'Invocations4XXErrors', 'Invocations5XXErrors'):
            report['metrics'][metric] = aws('cloudwatch', 'get-metric-statistics', '--namespace', '/aws/sagemaker/Endpoints' if metric == 'MemoryUtilization' else 'AWS/SageMaker',
                '--metric-name', metric, '--dimensions', 'Name=EndpointName,Value=' + NAME, 'Name=VariantName,Value=AllTraffic',
                '--start-time', (now-timedelta(hours=2)).isoformat(), '--end-time', now.isoformat(), '--period', '60',
                '--statistics', 'Average', 'Maximum', 'Sum', 'SampleCount', optional=True)
        save(work / 'aws_observation.json', report)
        print(json.dumps({'endpoint_status': report['endpoint'].get('EndpointStatus'),
                          'failure_reason': report['endpoint'].get('FailureReason'),
                          'metrics_points': {k: len(v.get('Datapoints', [])) for k, v in report['metrics'].items()}}))


if __name__ == '__main__':
    main()
