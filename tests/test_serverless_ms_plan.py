import pytest
from scripts.serverless_ms_ops import check_plan


def change(address, kind, actions, after):
    return {'mode': 'managed', 'address': address, 'type': kind, 'change': {'actions': actions, 'after': after}}


def test_plan_rejects_production_changes_and_replacements():
    for item in [change('aws_ecs_service.scientific', 'aws_ecs_service', ['update'], {}),
                 change('aws_iam_role.probe[0]', 'aws_iam_role', ['delete', 'create'], {}),
                 change('aws_ecr_repository.probe', 'aws_ecr_repository', ['create'], {'name': 'citas-api'})]:
        with pytest.raises(ValueError):
            check_plan({'resource_changes': [item]})


def test_plan_rejects_provisioned_concurrency():
    variant = {'serverless_config': [{'memory_size_in_mb': 6144, 'max_concurrency': 1, 'provisioned_concurrency': 1}]}
    item = change('aws_sagemaker_endpoint_configuration.probe[0]', 'aws_sagemaker_endpoint_configuration', ['create'], {'production_variants': [variant]})
    with pytest.raises(ValueError, match='Capacidad'):
        check_plan({'resource_changes': [item]})


def test_destroy_is_limited_to_owned_probe_resources():
    item = change('aws_sagemaker_endpoint.probe[0]', 'aws_sagemaker_endpoint', ['delete'], None)
    assert check_plan({'resource_changes': [item]}, destroy=True) == [item['address']]
    with pytest.raises(ValueError):
        check_plan({'resource_changes': [change('aws_s3_bucket.models', 'aws_s3_bucket', ['delete'], None)]}, destroy=True)
