"""La imagen M/S copia cada módulo que importan sus propios módulos (evita builds rotos)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def copiados():
    archivos = set()
    for linea in (ROOT / 'Dockerfile.ms').read_text().splitlines():
        if linea.startswith('COPY src/app/'):
            archivos.update(p for p in linea.split()[1:-1] if p.startswith('src/app/'))
    return archivos


def test_modulos_copiados_existen_e_importaciones_cerradas():
    archivos = copiados()
    assert {'src/app/ms_queue.py', 'src/app/ms_queue_aws.py'} <= archivos
    faltan = []
    for archivo in archivos:
        ruta = ROOT / archivo
        assert ruta.is_file(), f'{archivo} no existe'
        for modulo in re.findall(r'from src\.app\.(\w+) import|import src\.app\.(\w+)', ruta.read_text()):
            nombre = f"src/app/{modulo[0] or modulo[1]}.py"
            if nombre not in archivos:
                faltan.append((archivo, nombre))
    assert not faltan, f'Módulos importados pero no copiados en Dockerfile.ms: {faltan}'
