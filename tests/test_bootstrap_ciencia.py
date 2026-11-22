"""El arranque nunca publica pesos corruptos ni acepta otra release."""
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from scripts.iniciar_ciencia import preparar


class BootstrapTest(unittest.TestCase):
    def manifest(self):
        return {"release_id": "test", "bucket": "private", "prefix": "releases/test/",
                "files": [{"path": "weights/model", "bytes": 5,
                           "sha256": hashlib.sha256(b"model").hexdigest()}]}

    def client(self, manifest, payload=b"model"):
        class Client:
            downloads = 0
            def get_object(self, **kwargs):
                return {"Body": io.BytesIO(json.dumps({k: v for k, v in manifest.items() if k not in ("bucket", "prefix")}).encode())}
            def download_file(self, bucket, key, target):
                self.downloads += 1
                Path(target).write_bytes(payload)
        return Client()

    def test_validated_cache_and_repair(self):
        manifest = self.manifest()
        client = self.client(manifest)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            preparar(client, manifest, root)
            preparar(client, manifest, root)
            self.assertEqual(client.downloads, 1)
            (root / "weights/model").write_bytes(b"wrong")
            preparar(client, manifest, root)
            self.assertEqual(client.downloads, 2)

    def test_corruption_does_not_publish(self):
        manifest = self.manifest()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(RuntimeError):
                preparar(self.client(manifest, b"wrong"), manifest, root)
            self.assertFalse((root / "weights/model").exists())
            self.assertFalse((root / "weights/model.partial").exists())

    def test_different_remote_release_rejected(self):
        manifest = self.manifest()
        remote = dict(manifest, release_id="unexpected")
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(RuntimeError):
                preparar(self.client(remote), manifest, Path(directory))


if __name__ == "__main__":
    unittest.main()
