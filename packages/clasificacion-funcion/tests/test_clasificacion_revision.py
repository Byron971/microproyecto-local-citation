import re

import pytest

from clasificacion_funcion import revision
from recuperacion_densa import revision as revision_a1

SHA = re.compile(r"[0-9a-f]{40}")


def test_scibert_reutiliza_la_revision_de_a1():
    assert revision.MODELOS["scibert"] == {
        "model_id": revision_a1.MODEL_ID, "revision": revision_a1.REVISION_SCIBERT}
    assert revision.modelo("scibert") == (revision_a1.MODEL_ID, revision_a1.REVISION_SCIBERT)


def test_specter_fijado_a_un_sha_de_commit():
    model_id, rev = revision.modelo("specter")
    assert model_id == "allenai/specter" and SHA.fullmatch(rev)


def test_encoders_disponibles():
    assert revision.ENCODERS == ("scibert", "specter")


def test_encoder_desconocido():
    with pytest.raises(ValueError, match="desconocido"):
        revision.modelo("bert")


def test_revision_no_fijada_o_mutable_se_rechaza(monkeypatch):
    for mala in (None, "main", "abc123"):
        monkeypatch.setitem(revision.MODELOS, "specter", {"model_id": "x", "revision": mala})
        with pytest.raises(ValueError, match="SHA"):
            revision.modelo("specter")
