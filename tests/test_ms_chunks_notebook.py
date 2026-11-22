"""Compare preparation against the actual notebook functions without running training."""
import ast
import json
from pathlib import Path
import re

from scripts.preparar_corpus_ms import fragmentar_ms


def test_v2_and_dedup_match_notebook_10():
    notebook = json.loads(Path('notebooks/10_modelos_finales_M_S.ipynb').read_text())
    names = {'fragmentar', '_dividir_parrafo_largo_v2', 'fragmentar_v2', 'deduplicar_chunks'}
    nodes = []
    for cell in notebook['cells']:
        if cell['cell_type'] != 'code':
            continue
        tree = ast.parse(''.join(cell['source']))
        nodes.extend(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names)
    assert len(nodes) == len(names)
    namespace = {'re': re, 'MAX_PALABRAS': 300, 'MAX_CARACTERES': 5000, 'MAX_PARRAFOS_CHUNK': 2}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<notebook-fragmentacion>', 'exec'), namespace)
    paragraphs = [
        {'numero': 0, 'texto': 'A short scientific paragraph.', 'seccion': 'Introduction'},
        {'numero': 1, 'texto': 'A separate short scientific paragraph.', 'seccion': 'Methods'},
        {'numero': 2, 'texto': ' '.join(['A complete scientific sentence.'] * 170), 'seccion': 'Results'},
        {'numero': 3, 'texto': 'A short scientific paragraph.', 'seccion': 'Conclusion'},
    ]
    expected = namespace['deduplicar_chunks'](namespace['fragmentar_v2'](paragraphs))
    assert fragmentar_ms(paragraphs) == expected
    assert any('-s' in c['chunk_id'] for c in expected)
    assert not any(c['chunk_id'] == 'p00003-p00003' for c in expected)
