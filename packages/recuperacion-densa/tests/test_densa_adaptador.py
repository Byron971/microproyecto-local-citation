import pytest

from recuperacion_densa import adaptador_proyecto_grado as ad
from recuperacion_densa.cache_embeddings import CacheDisco, clave_embedding


def test_clave_cambia_con_entorno():
    base = clave_embedding("m", "r", 512, "mean", "t", "cpu", "bs=16;torch=1")
    assert base != clave_embedding("m", "r", 512, "mean", "t", "cpu", "bs=8;torch=1")
    assert base != clave_embedding("m", "r", 512, "mean", "t", "cpu", "bs=16;torch=2")


def test_adaptador_expone_componentes_del_proyecto():
    assert callable(ad.fragmentar) and callable(ad.integrar) and callable(ad.lexico)
    assert ad.perfil_seccion(None) == "vacia"
    assert ad.REPO.is_dir()


def test_exclusiones_inexistentes_fallan_o_vacias(tmp_path):
    f = tmp_path / "ex.txt"
    f.write_text("a1\nb2\n", encoding="utf-8")
    assert {"a1", "b2"} <= ad.cargar_exclusiones([f])


def test_cache_disco_roundtrip_y_corrupcion(tmp_path):
    c = CacheDisco(tmp_path / "e")
    k = clave_embedding("m", "r", 512, "mean", "texto")
    assert c.get(k) is None
    c.put(k, (0.5, -1.25, 3.0))
    assert c.get(k) == (0.5, -1.25, 3.0)
    (tmp_path / "e" / f"{k}.f64").write_bytes(b"123")  # truncado
    assert c.get(k) is None
    assert not list((tmp_path / "e").glob("*.tmp"))
    with pytest.raises(ValueError):
        c.get("../x")


def test_clave_cambia_con_cada_parametro():
    b = clave_embedding("m", "r", 512, "mean", "t")
    assert len({b, clave_embedding("m2", "r", 512, "mean", "t"),
                clave_embedding("m", "r2", 512, "mean", "t"),
                clave_embedding("m", "r", 256, "mean", "t"),
                clave_embedding("m", "r", 512, "cls", "t"),
                clave_embedding("m", "r", 512, "mean", "u")}) == 6
