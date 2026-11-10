"""La limpieza no debe borrar estados activos ni contenido de otros proyectos."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.destruir_init import destroy


def fake_aws(calls, *, resources=None, foreign=False, deletion_error=False, count=2):
    def run(*args):
        calls.append(args)
        if args[0] == 'sts':
            return {'Account': '123456789012'}
        if args[1] == 'list-object-versions':
            return {'Versions': [{'Key': 'other.txt' if foreign else 'api/terraform.tfstate',
                                  'VersionId': str(i)} for i in range(count)],
                    'DeleteMarkers': [{'Key': 'api/terraform.tfstate', 'VersionId': 'old-marker'}]}
        if args[1] == 'list-objects-v2':
            return {'Contents': [{'Key': 'api/terraform.tfstate'}]}
        if args[1] == 'get-object':
            Path(args[-1]).write_text(json.dumps({'version': 4, 'resources': resources or []}))
        if args[1] == 'delete-objects' and deletion_error:
            return {'Errors': [{'Code': 'AccessDenied'}]}
        return {}
    return run


def test_rejects_foreign_content_before_any_deletion():
    calls = []
    with patch('scripts.destruir_init.aws', side_effect=fake_aws(calls, foreign=True)):
        with pytest.raises(ValueError, match='otros archivos'):
            destroy('bucket', 'ecr', 'api/terraform.tfstate')
    assert not any('delete' in call[1] for call in calls)


def test_rejects_resources_before_any_deletion():
    calls = []
    resources = [{'mode': 'managed', 'instances': [{'attributes': {'id': 'active'}}]}]
    with patch('scripts.destruir_init.aws', side_effect=fake_aws(calls, resources=resources)):
        with pytest.raises(ValueError, match='Quedan recursos'):
            destroy('bucket', 'ecr', 'api/terraform.tfstate')
    assert not any('delete' in call[1] for call in calls)


def test_deletes_all_versions_and_markers_in_batches_after_empty_states():
    calls = []
    with patch('scripts.destruir_init.aws', side_effect=fake_aws(calls, count=1001)):
        destroy('bucket', 'ecr', 'api/terraform.tfstate')
    batches = [json.loads(call[call.index('--delete') + 1])['Objects']
               for call in calls if call[1] == 'delete-objects']
    assert [len(batch) for batch in batches] == [1000, 2]
    assert batches[-1][-1]['VersionId'] == 'old-marker'
    assert calls[-1][1] == 'delete-bucket'
    assert '--expected-bucket-owner' in calls[-1]


def test_stops_if_s3_reports_partial_failure():
    calls = []
    with patch('scripts.destruir_init.aws', side_effect=fake_aws(calls, deletion_error=True)):
        with pytest.raises(ValueError, match='algunas versiones'):
            destroy('bucket', 'ecr', 'api/terraform.tfstate')
    assert not any(call[1] == 'delete-bucket' for call in calls)
