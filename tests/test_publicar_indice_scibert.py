import hashlib
import io
import json
from types import SimpleNamespace

import pytest
from scripts.publicar_indice_scibert import publicar


class Missing(Exception):
    pass


class Storage:
    exceptions = SimpleNamespace(NoSuchKey=Missing)
    def __init__(self):
        self.objects, self.writes = {}, []
    def get_object(self, *, Bucket, Key):
        if Key not in self.objects:
            raise Missing()
        return {'Body': io.BytesIO(self.objects[Key])}
    def upload_file(self, path, bucket, key, ExtraArgs):
        self.put_object(Bucket=bucket, Key=key, Body=__import__('pathlib').Path(path).read_bytes())
    def put_object(self, *, Bucket, Key, Body, **kwargs):
        self.objects[Key] = Body; self.writes.append(Key)


def local_index(root):
    for name in ['papers.json', 'embeddings.npy']:
        (root / name).write_bytes(b'public-metadata-fixture')
    data = {'total_articulos': 19776, 'revision_scibert': 'a' * 40, 'perfil': 'test',
            'files': {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                      for name in ['papers.json', 'embeddings.npy']}}
    (root / 'indice.json').write_text(json.dumps(data))


def test_inventory_published_last_and_replay_does_not_overwrite(tmp_path):
    local_index(tmp_path); client = Storage()
    manifest = publicar(tmp_path, client, 'private-bucket')
    assert client.writes[-1].endswith('release.json')
    previous_writes = list(client.writes)
    assert publicar(tmp_path, client, 'private-bucket') == manifest
    assert client.writes == previous_writes


def test_changed_remote_release_is_rejected(tmp_path):
    local_index(tmp_path); client = Storage()
    manifest = publicar(tmp_path, client, 'private-bucket')
    key = manifest['prefix'] + manifest['files'][0]['path']
    client.objects[key] = b'different-content'
    previous_writes = list(client.writes)
    with pytest.raises(ValueError, match='contenido distinto'):
        publicar(tmp_path, client, 'private-bucket')
    assert client.writes == previous_writes
