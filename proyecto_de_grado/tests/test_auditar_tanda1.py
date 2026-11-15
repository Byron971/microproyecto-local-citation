"""Pruebas de la auditoría de la tanda 1 del Test Gold (issue #97)."""
import zipfile
from xml.sax.saxutils import escape

from proyecto_de_grado.src.data.auditar_tanda1 import (ENCABEZADOS, HOJAS_LIBRO, auditar, columna, estado, leer_xlsx,
                                                       reparto, tabla_anotacion)

MAN = [{"context_id": c, "grupo": "testgold", "tanda": "1"} for c in ("P15-1001_A01-0001_0", "P15-1002_A01-0002_0",
                                                                     "P15-1003_A01-0003_0")]
MAN += [{"context_id": "P15-2001_A01-0009_0", "grupo": "testgold", "tanda": "2"},
        {"context_id": "W14-0001_A01-0001_0", "grupo": "calibracion3", "tanda": ""}]
A, B, C = (r["context_id"] for r in MAN[:3])


def letra(i):
    return chr(65 + i)


def xlsx(ruta, hojas):
    """Libro mínimo: textos en sharedStrings, salvo los que empiezan con '!', que van como texto en línea."""
    compartidos, cuerpos = [], []
    for filas in hojas.values():
        celdas = []
        for f, fila in enumerate(filas, start=1):
            for c, v in enumerate(fila):
                if v == "":
                    continue
                ref = f"{letra(c)}{f}"
                if v.startswith("!"):
                    celdas.append(f'<c r="{ref}" t="inlineStr"><is><t>{escape(v[1:])}</t></is></c>')
                else:
                    compartidos.append(v)
                    celdas.append(f'<c r="{ref}" t="s"><v>{len(compartidos) - 1}</v></c>')
        cuerpos.append(f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
                       f'<row>{"".join(celdas)}</row></sheetData></worksheet>')
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    rel = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
    with zipfile.ZipFile(ruta, "w") as z:
        z.writestr("xl/workbook.xml", f'<workbook {ns} {rel}><sheets>' + "".join(
            f'<sheet name="{n}" sheetId="{i + 1}" r:id="rId{i + 1}"/>' for i, n in enumerate(hojas)) + "</sheets></workbook>")
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + "".join(
                       f'<Relationship Id="rId{i + 1}" Target="worksheets/sheet{i + 1}.xml" Type="x"/>'
                       for i in range(len(hojas))) + "</Relationships>")
        z.writestr("xl/sharedStrings.xml", f"<sst {ns}>" + "".join(f"<si><t>{escape(s)}</t></si>" for s in compartidos) + "</sst>")
        for i, cuerpo in enumerate(cuerpos):
            z.writestr(f"xl/worksheets/sheet{i + 1}.xml", cuerpo)
    return ruta


def fila(cid, evaluable="", funcion="", confianza="", justificacion=""):
    return ["1", cid, "x TARGETCIT y", "", "", "", "", "", evaluable, funcion, confianza, justificacion, ""]


def libro(filas, encabezado=ENCABEZADOS, guia=(), extra=None):
    hojas = {"Mis_anotaciones": [["TEST GOLD"], [], list(encabezado)] + filas}
    hojas |= {n: [["Paso"], *[[g] for g in guia]] for n in HOJAS_LIBRO[1:]}
    return hojas | (extra or {})


def test_columna():
    assert columna("A1") == (1, 0)
    assert columna("J12") == (12, 9)
    assert columna("AB3") == (3, 27)


def test_lector_xlsx_lee_texto_compartido_y_en_linea(tmp_path):
    ruta = xlsx(tmp_path / "x.xlsx", {"Uno": [["a", "", "!en línea"], ["", "b & c"]], "Dos": [["z"]]})
    assert leer_xlsx(ruta) == {"Uno": [["a", "", "en línea"], ["", "b & c", ""]], "Dos": [["z"]]}


def test_estado_replica_la_columna_de_las_hojas():
    r = lambda *a: dict(zip(("evaluable", "funcion", "confianza", "justificacion"), a))
    assert estado(r("", "", "", "")) == "PENDIENTE"
    assert estado(r("Evaluable", "Gap", "Alta", "")) == "COMPLETO"
    assert estado(r("Evaluable", "Gap", "", "")) == "INCOMPLETO"
    assert estado(r("Evaluable", "", "Alta", "")) == "INCOMPLETO"
    assert estado(r("Ambiguo", "Gap", "", "porque")) == "COMPLETO"
    assert estado(r("Ambiguo", "Gap", "Alta", "")) == "INCOMPLETO"
    assert estado(r("No evaluable", "", "", "")) == "REVISAR"
    assert estado(r("No evaluable", "", "", "texto roto")) == "REGISTRADO"


def test_tabla_anotacion_salta_titulo_y_filas_vacias(tmp_path):
    hojas = leer_xlsx(xlsx(tmp_path / "h.xlsx", libro([fila(A, "Evaluable", "Gap", "Alta"), ["", "", "", ""], fila(B)])))
    encabezado, registros = tabla_anotacion(hojas["Mis_anotaciones"])
    assert encabezado == ENCABEZADOS
    assert [r["context_id"] for r in registros] == [A, B]
    assert registros[0]["funcion"] == "Gap" and registros[1]["evaluable"] == ""


def test_auditoria_reparto_doble_y_avance():
    libros = {"Ana": libro([fila(A, "Evaluable", "Gap", "Alta"), fila(B, "No evaluable")]),
              "Beto": libro([fila(A), fila(C, "Evaluable", "Basis", "Media", "porque")]),
              "Ceci": libro([fila(B, "No evaluable", justificacion="texto roto"), fila(C)])}
    a = auditar(MAN, libros, set(), set())
    assert a["por_persona"]["Ceci"]["terminadas"] == 1 and a["por_persona"]["Ceci"]["pendientes"] == 1
    assert a["tanda1"] == 3 and a["cobertura"] == {2: 3} and a["sin_hoja"] == 0
    assert a["parejas"] == {("Ana", "Beto"): 1, ("Ana", "Ceci"): 1, ("Beto", "Ceci"): 1}
    assert a["por_persona"]["Ana"] == {"citas": 2, "repetidas": 0, "fuera_de_tanda1": 0, "terminadas": 1,
                                            "pendientes": 0, "por_corregir": 1, "evaluables_sin_justificacion": 1}
    assert a["por_persona"]["Beto"]["terminadas"] == 1 and a["por_persona"]["Beto"]["evaluables_sin_justificacion"] == 0
    assert reparto(a) == [{"context_id": A, "anotador_1": "Ana", "anotador_2": "Beto"},
                          {"context_id": B, "anotador_1": "Ana", "anotador_2": "Ceci"},
                          {"context_id": C, "anotador_1": "Beto", "anotador_2": "Ceci"}]


def test_auditoria_detecta_citas_sin_pareja_repetidas_y_ajenas():
    tanda2 = MAN[3]["context_id"]
    libros = {"Ana": libro([fila(A), fila(A), fila(tanda2)]), "Beto": libro([fila(A), fila(B)]), "Ceci": libro([fila(A)])}
    a = auditar(MAN, libros, set(), set())
    assert a["cobertura"] == {3: 1, 1: 1, 0: 1} and a["sin_hoja"] == 1          # A en tres hojas, B en una, C en ninguna
    assert a["por_persona"]["Ana"]["repetidas"] == 1
    assert a["por_persona"]["Ana"]["fuera_de_tanda1"] == 1


def test_auditoria_a_ciegas():
    tanda2 = MAN[3]["context_id"]
    libros = {"Ana": libro([fila(A)], encabezado=ENCABEZADOS[:9] + ["Voto jurado"] + ENCABEZADOS[9:]),
              "Beto": libro([fila(A)], guia=[f"ejemplo {tanda2}"], extra={"Clave": [["x"]]}),
              "Ceci": libro([fila(A)], guia=["W14-0001_A01-0001_0 es de calibración, no del Test Gold"])}
    c = auditar(MAN, libros, {tanda2, "N10-1073_D08-1037_0"}, {"P99-0001_A01-0001_0", "W14-0001_A01-0001_0"})
    assert c["ciego"]["Ana"]["columnas_esperadas"] is False and c["ciego"]["Ana"]["columnas_extra"] == ["Voto jurado"]
    assert c["ciego"]["Beto"]["hojas_extra"] == ["Clave"] and c["ciego"]["Beto"]["gold_en_otras_hojas"] == 1
    assert c["ciego"]["Ceci"] == {"columnas_esperadas": True, "columnas_extra": [], "hojas_extra": [], "gold_en_otras_hojas": 0}
    assert c["ejemplos_en_gold"] == 1 and c["excluidas_en_gold"] == 0
