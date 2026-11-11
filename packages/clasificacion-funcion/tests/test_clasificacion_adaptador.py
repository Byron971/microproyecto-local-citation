import csv

import pytest

from clasificacion_funcion import adaptador_proyecto_grado as ad

COLS = ["N°", "context_id", "Contexto TARGETCIT", "Título citado", "Resumen citado",
        "¿Evaluable?", "Función principal"]


def escribir(ruta, filas, columnas):
    with open(ruta, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(columnas)
        w.writerows(filas)


def fuentes(tmp_path, **kw):
    return ad.FuentesProyectoGrado(**{"raw": tmp_path, "haiku": tmp_path / "h.csv",
                                      "split": tmp_path / "s.json", "test_gold": tmp_path / "t.csv",
                                      "manifiesto": tmp_path / "m.csv", "gold_v2": tmp_path / "g.csv",
                                      "exclusiones": (tmp_path / "x.txt",), **kw})


def test_filas_haiku_etiqueta_o_abstencion(tmp_path):
    escribir(tmp_path / "h.csv", [
        [1, "a", "c", "T", "R", "Evaluable", "Gap"],
        [2, "b", "c", "T", "R", "Ambiguo", ""],
        [3, "c", "c", "T", "R", "No evaluable", ""]], COLS)
    filas = fuentes(tmp_path).filas_haiku()
    assert [(f["context_id"], f["etiqueta"]) for f in filas] == [
        ("a", "Gap"), ("b", "Ambiguo"), ("c", "No evaluable")]
    assert filas[0]["titulo"] == "T" and filas[0]["abstract"] == "R"


def test_evaluable_sin_funcion_y_estado_desconocido_fallan(tmp_path):
    escribir(tmp_path / "h.csv", [[1, "a", "c", "T", "R", "Evaluable", ""]], COLS)
    with pytest.raises(ValueError, match="sin funcion"):
        fuentes(tmp_path).filas_haiku()
    escribir(tmp_path / "h.csv", [[1, "a", "c", "T", "R", "Quiza", "Gap"]], COLS)
    with pytest.raises(ValueError, match="desconocido"):
        fuentes(tmp_path).filas_haiku()


def test_test_gold_une_anio_del_manifiesto(tmp_path):
    escribir(tmp_path / "t.csv", [[1, "a", "c", "T", "R", "Evaluable", "Basis"]], COLS)
    escribir(tmp_path / "m.csv", [[1, "a", "2015", "x", "0"]],
             ["N°", "context_id", "anio_citante", "prelabel_qlora", "citado_en_entrenamiento"])
    assert fuentes(tmp_path).filas_test_gold()[0]["anio_citante"] == "2015"
    escribir(tmp_path / "m.csv", [[1, "otro", "2015", "x", "0"]],
             ["N°", "context_id", "anio_citante", "prelabel_qlora", "citado_en_entrenamiento"])
    with pytest.raises(ValueError, match="sin manifiesto"):
        fuentes(tmp_path).filas_test_gold()


def test_gold_v2_solo_grupo_testgold(tmp_path):
    escribir(tmp_path / "g.csv", [["a", "testgold", ""], ["b", "calibracion3", ""], ["c", "testgold", ""]],
             ["context_id", "grupo", "tanda"])
    assert fuentes(tmp_path).ids_gold_v2() == ["a", "c"]


def test_split_y_exclusiones(tmp_path):
    (tmp_path / "s.json").write_text('{"train": ["a"], "val": ["b"], "method": "x"}', encoding="utf-8")
    (tmp_path / "x.txt").write_text("# nota\nz1\n\nz2\n", encoding="utf-8")
    f = fuentes(tmp_path)
    assert f.split_entrenamiento() == {"train": ["a"], "val": ["b"]}
    assert f.exclusiones() == {"z1", "z2"}


def test_archivos_faltantes_fallan_con_mensaje(tmp_path):
    with pytest.raises(FileNotFoundError):
        fuentes(tmp_path).filas_haiku()
    with pytest.raises(FileNotFoundError):
        fuentes(tmp_path).split_entrenamiento()
    with pytest.raises(FileNotFoundError):
        fuentes(tmp_path).exclusiones()
