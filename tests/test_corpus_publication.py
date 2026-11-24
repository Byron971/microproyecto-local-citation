"""A remote copy must match every byte before a release inventory is published."""
import hashlib
from pathlib import Path

import pytest

from scripts.publicar_corpus_ampliado import publish


@pytest.mark.parametrize('corrupt', [False, True])
def test_inventory_is_never_published_for_corrupt_remote_copy(tmp_path, corrupt):
    original = b'prepared article corpus'
    (tmp_path / 'corpus.sqlite').write_bytes(original)
    item = dict(path='artifacts/coverage_expansion/corpus.sqlite', bytes=len(original),
                sha256=hashlib.sha256(original).hexdigest())
    manifest = dict(bucket='unit-bucket', prefix='releases/unit/', files=[item], release_id='unit')
    published = []

    class Missing(Exception):
        pass

    class FakeS3:
        class exceptions:
            NoSuchKey = Missing

        def head_object(self, **kwargs):
            return {'ContentLength': len(original)}

        def download_file(self, bucket, key, target):
            # Equal byte count, different content: size alone cannot establish integrity.
            Path(target).write_bytes(original if not corrupt else b'X' * len(original))

        def get_object(self, **kwargs):
            raise Missing()

        def put_object(self, **kwargs):
            published.append(kwargs['Key'])

    if corrupt:
        with pytest.raises(ValueError, match='remoto no coincide'):
            publish(tmp_path, manifest, FakeS3())
        assert published == []
    else:
        publish(tmp_path, manifest, FakeS3())
        assert published == ['releases/unit/release.json']
