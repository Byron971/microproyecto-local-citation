"""`verificacion_sonnet` con CSV sinteticos: estructura, 9 clases, abstenciones y fugas."""
import csv

from clasificacion_funcion import anotacion_sonnet as an
from clasificacion_funcion import dominio, verificacion_sonnet as vs


def _fila(i, cid, evaluable="Evaluable", funcion="Background", conf="Alta", just="ok", lote=1):
    estado = "COMPLETO" if evaluable == "Evaluable" else "REGISTRADO"
    return [i, cid, evaluable, funcion, conf, just, estado, lote, 1]


def _csv(tmp_path, filas, columnas=None):
    ruta = tmp_path / "e.csv"
    with ruta.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(columnas or an.COLUMNAS_SALIDA)
        w.writerows(filas)
    return ruta


def _buenas():
    filas = []
    for i in range(1, 10):
        filas.append(_fila(i, f"P10-{1000 + i}_P09-0001_0", funcion=dominio.CATEGORIAS[i - 1]))
    return filas


def test_archivo_valido_es_apto(tmp_path):
    r = vs.verificar(_csv(tmp_path, _buenas()))
    assert r["apto"], r["errores"]
    assert r["resumen"]["distribucion"]["usables_entrenamiento"] == 9


def test_funcion_fuera_de_las_nueve_clases_bloquea(tmp_path):
    filas = _buenas()
    filas[0][3] = "Contrast"
    r = vs.verificar(_csv(tmp_path, filas))
    assert not r["apto"] and any("9 clases" in e for e in r["errores"])


def test_abstencion_con_funcion_o_sin_justificacion_bloquea(tmp_path):
    filas = _buenas() + [_fila(10, "P10-2000_P09-0001_0", "Ambiguo", "Gap", just="x"),
                         _fila(11, "P10-2001_P09-0001_0", "No evaluable", "", just="")]
    r = vs.verificar(_csv(tmp_path, filas))
    assert any("Abstencion con funcion" in e for e in r["errores"])
    assert any("sin justificacion" in e for e in r["errores"])


def test_duplicados_columnas_y_numeracion(tmp_path):
    filas = _buenas()
    filas[1][1] = filas[0][1]
    filas[2][0] = 7
    r = vs.verificar(_csv(tmp_path, filas))
    assert any("duplicados" in e for e in r["errores"]) and any("numeracion" in e for e in r["errores"])
    r = vs.verificar(_csv(tmp_path, [], columnas=["a", "b"]))
    assert not r["apto"] and "Columnas" in r["errores"][0]


def test_clase_ausente_y_confianza_invalida(tmp_path):
    filas = _buenas()[:-1]
    filas[0][4] = "Muy alta"
    r = vs.verificar(_csv(tmp_path, filas))
    assert any("Clase sin ningun ejemplo" in e for e in r["errores"])
    assert any("Confianza" in e for e in r["errores"])


def test_manifiesto_de_lotes_y_ids(tmp_path):
    filas = _buenas()
    ids = [f[1] for f in filas]
    ok = {"ids": 9, "sha256_ids": dominio.sha_ids(sorted(ids))}
    assert vs.verificar(_csv(tmp_path, filas), ok)["apto"]
    r = vs.verificar(_csv(tmp_path, filas), {"ids": 10, "sha256_ids": "x"})
    assert any("manifiesto" in e for e in r["errores"])


def test_inexistente(tmp_path):
    assert not vs.verificar(tmp_path / "nada.csv")["apto"]
