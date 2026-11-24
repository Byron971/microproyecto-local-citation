"""Una segunda petición no debe quedar en cola detrás de la inferencia activa."""
import importlib.util
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch


@unittest.skipUnless(importlib.util.find_spec('torch'), 'Requiere entorno científico')
class ConcurrenciaTest(unittest.TestCase):
    def test_ocupado_sin_encolar_y_liberacion_posterior(self):
        from src.app import ms_runtime as runtime
        started, release = threading.Event(), threading.Event()
        class Service:
            def analizar(self, *args):
                started.set()
                if not release.wait(timeout=5):
                    raise TimeoutError('La prueba no liberó la inferencia')
                return {'ok': True}
        with patch.object(runtime, 'obtener_servicio', return_value=Service()):
            with ThreadPoolExecutor(max_workers=1) as pool:
                first = pool.submit(runtime.analizar_seguro, '', '', '', [])
                try:
                    self.assertTrue(started.wait(timeout=2))
                    with self.assertRaises(runtime.ServicioOcupado):
                        runtime.analizar_seguro('', '', '', [])
                finally:
                    release.set()
                self.assertEqual(first.result(timeout=2), {'ok': True})
            self.assertEqual(runtime.analizar_seguro('', '', '', []), {'ok': True})


if __name__ == '__main__':
    unittest.main()
