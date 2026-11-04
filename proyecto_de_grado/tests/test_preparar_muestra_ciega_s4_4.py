"""S4.4: pruebas offline con ACL-200 sintético, sin Gold ni modelos."""
import csv
import json
from pathlib import Path

import pytest

from proyecto_de_grado.src.evaluation.preparar_muestra_ciega_s4_4 import preparar


def fixture(tmp_path, *, n_val=16):
    raw = tmp_path / "raw"
    raw.mkdir()
    contexts, papers = {}, {}
    splits = {s: [] for s in ("train", "val", "test")}
    for split, ids in (("train", ["TR_0", "TR_1"]),
                       ("val", [f"VA_{i:02d}" for i in range(n_val)]),
                       ("test", ["TE_0", "TE_1"])):
        for i, cid in enumerate(ids):
            cited = f"REF{i % 7}"
            contexts[cid] = {
                "citing_id": f"CITING_{cid}", "refid": cited,
                "masked_text": f"Case {cid} applies TARGETCIT and OTHERCIT in a passage.",
            }
            papers[cited] = {"title": f"Paper {cited}", "abstract": f"Abstract of {cited}"}
            splits[split].append({"context_id": cid, "positive_ids": [cited]})
    (raw / "contexts.json").write_text(json.dumps(contexts), encoding="utf-8")
    (raw / "papers.json").write_text(json.dumps(papers), encoding="utf-8")
    for split, rows in splits.items():
        (raw / f"{split}.json").write_text(json.dumps(rows), encoding="utf-8")
    exclude = tmp_path / "ids_excluir.txt"
    history = tmp_path / "ids_historia.txt"
    exclude.write_text("# ignora\nVA_00\nTE_0\n", encoding="utf-8")
    history.write_text("VA_01\nVA_01\n", encoding="utf-8")
    return raw, exclude, history, contexts, papers, splits


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def test_generar_muestra_a_b_sin_etiquetas_ni_test(tmp_path):
    raw, exc, hist, _, _, _ = fixture(tmp_path)
    out = tmp_path / "out"
    m = preparar(raw, exc, hist, out, limit=12, seed=44)
    a, b = rows(out / "anotador_a.csv"), rows(out / "anotador_b.csv")
    assert m["split"] == "val" and m["etiquetas_humanas_generadas"] == 0
    assert len(a) == len(b) == 12
    assert set(r["context_id"] for r in a) == set(r["context_id"] for r in b)
    assert [r["context_id"] for r in a] != [r["context_id"] for r in b]
    assert all(r["context_id"].startswith("VA_") for r in a)
    assert all(r["context_id"] not in ("VA_00", "VA_01") for r in a)
    assert all(r["primary_label"] == r["secondary_label"] == r["annotation_status"] == "" for r in a)
    assert all("TARGETCIT" in r["citation_context"] and "OTHERCIT" in r["citation_context"] for r in a)
    assert all("predic" not in field.lower() and "score" not in field.lower() for field in a[0])
    assert all(not x["revision_contexto"] for x in rows(out / "revision_elegibilidad.csv"))
    assert len(rows(out / "auditoria_marco_val.csv")) == 16
    assert len(rows(out / "adjudicacion_plantilla.csv")) == 12
    assert m["sha256_archivos_generados"] and m["sha256_fuentes"]


def test_muestra_estable_independiente_orden_val(tmp_path):
    raw, exc, hist, _, _, splits = fixture(tmp_path)
    m1 = preparar(raw, exc, hist, tmp_path / "a", limit=8, seed=45)
    (raw / "val.json").write_text(json.dumps(splits["val"][::-1]), encoding="utf-8")
    m2 = preparar(raw, exc, hist, tmp_path / "b", limit=8, seed=45)
    assert m1["ids_preseleccionados"] == m2["ids_preseleccionados"]


def test_dos_listas_de_exclusiones_se_suman(tmp_path):
    raw, exc, hist, _, _, _ = fixture(tmp_path)
    m = preparar(raw, exc, hist, tmp_path / "out", limit=3)
    assert m["excluidos_ids_union"] == 3
    assert m["exclusiones_por_motivo"]["excluido_piloto_calibracion"] == 2


def test_extra_exclusiones(tmp_path):
    raw, exc, hist, _, _, _ = fixture(tmp_path)
    extra = tmp_path / "adicional.txt"
    extra.write_text("VA_02\n", encoding="utf-8")
    m = preparar(raw, exc, hist, tmp_path / "out", limit=5, extra_exclude=extra)
    assert "VA_02" not in m["ids_preseleccionados"]
    assert m["exposiciones_adicionales_incluidas"] is True


def test_no_sobrescribe(tmp_path):
    raw, exc, hist, _, _, _ = fixture(tmp_path)
    out = tmp_path / "out"
    preparar(raw, exc, hist, out, limit=4)
    with pytest.raises(FileExistsError, match="salida ya existe"):
        preparar(raw, exc, hist, out, limit=4)


def test_rechaza_targetcit_invalido(tmp_path):
    raw, exc, hist, ctx, _, _ = fixture(tmp_path)
    ctx["VA_03"]["masked_text"] = "No marker"
    (raw / "contexts.json").write_text(json.dumps(ctx), encoding="utf-8")
    with pytest.raises(ValueError, match="TARGETCIT"):
        preparar(raw, exc, hist, tmp_path / "out", limit=2)
    assert not (tmp_path / "out").exists()


def test_rechaza_ids_duplicados_entre_splits(tmp_path):
    raw, exc, hist, _, _, splits = fixture(tmp_path)
    splits["test"].append(splits["val"][2])
    (raw / "test.json").write_text(json.dumps(splits["test"]), encoding="utf-8")
    with pytest.raises(ValueError, match="repetido"):
        preparar(raw, exc, hist, tmp_path / "out", limit=2)


def test_rechaza_citantes_compartidos(tmp_path):
    raw, exc, hist, ctx, _, _ = fixture(tmp_path)
    ctx["VA_03"]["citing_id"] = ctx["TR_0"]["citing_id"]
    (raw / "contexts.json").write_text(json.dumps(ctx), encoding="utf-8")
    with pytest.raises(ValueError, match="Citante compartido"):
        preparar(raw, exc, hist, tmp_path / "out", limit=2)


def test_excluye_texto_duplicado_entre_splits(tmp_path):
    raw, exc, hist, ctx, _, _ = fixture(tmp_path)
    ctx["VA_04"]["masked_text"] = ctx["TR_0"]["masked_text"]
    (raw / "contexts.json").write_text(json.dumps(ctx), encoding="utf-8")
    m = preparar(raw, exc, hist, tmp_path / "out", limit=5)
    assert "VA_04" not in m["ids_preseleccionados"]
    assert m["exclusiones_por_motivo"]["texto_duplicado_en_train_o_test"] == 1


def test_rechaza_fuente_incompleta(tmp_path):
    raw, exc, hist, _, _, _ = fixture(tmp_path)
    (raw / "val.json").unlink()
    with pytest.raises(FileNotFoundError, match="val.json"):
        preparar(raw, exc, hist, tmp_path / "out")


def test_rechaza_exclusion_obligatoria_ausente(tmp_path):
    raw, exc, hist, _, _, _ = fixture(tmp_path)
    hist.unlink()
    with pytest.raises(FileNotFoundError, match="exclusiones"):
        preparar(raw, exc, hist, tmp_path / "out")


def test_rechaza_solicitud_mayor_a_elegibles(tmp_path):
    raw, exc, hist, _, _, _ = fixture(tmp_path, n_val=5)
    with pytest.raises(ValueError, match="Solo hay"):
        preparar(raw, exc, hist, tmp_path / "out", limit=10)
    assert not (tmp_path / "out").exists()


def test_rechaza_citado_no_en_positivos(tmp_path):
    raw, exc, hist, _, _, splits = fixture(tmp_path)
    splits["val"][4]["positive_ids"] = ["MAL"]
    (raw / "val.json").write_text(json.dumps(splits["val"]), encoding="utf-8")
    with pytest.raises(ValueError, match="positive_ids"):
        preparar(raw, exc, hist, tmp_path / "out", limit=2)


def test_solo_anotadores_revisan_truncacion(tmp_path):
    raw, exc, hist, ctx, _, _ = fixture(tmp_path)
    ctx["VA_08"]["masked_text"] = "fragment TARGETCIT ..."
    (raw / "contexts.json").write_text(json.dumps(ctx), encoding="utf-8")
    m = preparar(raw, exc, hist, tmp_path / "out", limit=12)
    assert m["estado"].endswith("pendiente_revision_humana")
    assert "truncacion" in m["advertencia"]


def test_archivos_diferentes_no_se_sobrescriben(tmp_path):
    raw, exc, hist, _, _, _ = fixture(tmp_path)
    a = preparar(raw, exc, hist, tmp_path / "v1", limit=3)
    b = preparar(raw, exc, hist, tmp_path / "v2", limit=3)
    assert a["ids_preseleccionados"] == b["ids_preseleccionados"]
    assert all((tmp_path / "v1" / n).exists() for n in a["sha256_archivos_generados"])
