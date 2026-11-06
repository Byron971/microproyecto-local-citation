import pytest

pytest.importorskip("recuperacion_densa")
from recuperacion_densa.dominio import construir_lotes  # noqa: E402


def test_ventanas_no_pierden_tokens():
    ids = [list(range(10, 10 + 25)), [7]]
    seqs, idx, pesos = construir_lotes(ids, 10, 101, 102)
    assert idx == [0, 0, 0, 1] and pesos == [10, 10, 5, 1]
    assert all(s[0] == 101 and s[-1] == 102 for s in seqs)
    assert [t for s, i in zip(seqs, idx) if i == 0 for t in s[1:-1]] == ids[0]


def test_secuencia_vacia_rechazada():
    with pytest.raises(ValueError):
        construir_lotes([[]], 10, 1, 2)
