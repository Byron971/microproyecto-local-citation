"""Pruebas locales de los controles de CI, sin AWS ni Docker."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("smoke_ci", ROOT / "scripts/ci/smoke-api.py")
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


class DeploymentTest(unittest.TestCase):
    def run_deploy(self, failure):
        with tempfile.TemporaryDirectory() as folder:
            temp = Path(folder)
            stub = '''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
command = [Path(sys.argv[0]).name, *sys.argv[1:]]
with open(os.environ['CALL_LOG'], 'a') as log:
    log.write(json.dumps(command) + '\\n')
if command[0] == 'aws':
    if 'describe-parameters' in command: print('/citas-api/api/image_tag')
    elif 'get-parameter' in command: print('anterior')
    elif 'describe-services' in command:
        if 'services[0].desiredCount' in command: print('0')
        else: print('revertida' if os.environ['FAILURE'] == 'rollback' else 'revision-nueva')
else:
    if 'plan' in command and os.environ['FAILURE'] == 'plan': sys.exit(1)
    if 'apply' in command and os.environ['FAILURE'] == 'apply': sys.exit(1)
    if 'output' in command: print('revision-nueva')
'''
            for name in ("aws", "terraform"):
                path = temp / name
                path.write_text(stub)
                path.chmod(0o755)
            log = temp / "calls.jsonl"
            result = subprocess.run(
                ["bash", "scripts/ci/deploy-api.sh"], cwd=ROOT,
                env={**os.environ, "PATH": f"{temp}:{os.environ['PATH']}",
                     "IMAGE_TAG": "nueva", "FAILURE": failure, "CALL_LOG": str(log)},
                capture_output=True, text=True,
            )
            return result, [json.loads(line) for line in log.read_text().splitlines()]

    def test_failed_plan_or_apply_restores_previous_tag(self):
        for failure in ("plan", "apply", "rollback"):
            with self.subTest(failure=failure):
                result, calls = self.run_deploy(failure)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("put-parameter", calls[-1])
                self.assertEqual(calls[-1][calls[-1].index("--value") + 1], "anterior")

    def test_success_does_not_restore_tag(self):
        result, calls = self.run_deploy("")
        self.assertEqual(result.returncode, 0, result.stderr)
        writes = [call for call in calls if "put-parameter" in call]
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0][writes[0].index("--value") + 1], "nueva")

    def test_smoke_retries_and_fails_if_model_is_not_ready(self):
        with patch.object(smoke, "check", side_effect=ValueError("Modelo no listo")) as check:
            with patch.object(smoke.time, "sleep"), patch.object(smoke.sys, "argv", ["smoke", "https://example.test"]):
                with self.assertRaises(SystemExit):
                    smoke.main()
        self.assertEqual(check.call_count, 6)

    def test_smoke_retries_transient_failure(self):
        with patch.object(smoke, "check", side_effect=[ValueError("Arrancando"), None]) as check:
            with patch.object(smoke.time, "sleep"), patch.object(smoke.sys, "argv", ["smoke", "https://example.test"]):
                smoke.main()
        self.assertEqual(check.call_count, 2)
