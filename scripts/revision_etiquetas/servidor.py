"""Interfaz local para revisar las etiquetas de Haiku y Sonnet.

Lee los CSV de proyecto_de_grado/anotacion/revision_etiquetas_llm/ (generados por
scripts/muestrear_revision_etiquetas.py) y guarda cada revisión en el mismo CSV.

    python scripts/revision_etiquetas/servidor.py      # abre http://localhost:3000
"""
import argparse
import csv
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from urllib.parse import parse_qs, urlparse

REPO = Path(__file__).resolve().parents[2]
CARPETA = REPO / "proyecto_de_grado/anotacion/revision_etiquetas_llm"
INDEX = Path(__file__).with_name("index.html")
CAMPOS_REVISION = ["veredicto", "etiqueta_correcta", "justificacion_coherente", "comentarios humanos"]
CANDADO = Lock()


def ruta_csv(nombre):
    """Solo acepta CSV que estén directamente en la carpeta de revisión."""
    disponibles = {p.name: p for p in CARPETA.glob("*.csv")}
    if nombre not in disponibles:
        raise KeyError(nombre)
    return disponibles[nombre]


def leer(ruta):
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        lector = csv.DictReader(f)
        columnas = list(lector.fieldnames or [])
        filas = list(lector)
    for campo in CAMPOS_REVISION:
        if campo not in columnas:
            columnas.append(campo)
    for fila in filas:
        for campo in CAMPOS_REVISION:
            fila.setdefault(campo, "")
    return columnas, filas


def escribir(ruta, columnas, filas):
    temporal = ruta.with_suffix(".csv.tmp")
    with temporal.open("w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=columnas)
        escritor.writeheader()
        escritor.writerows(filas)
    temporal.replace(ruta)


class Manejador(BaseHTTPRequestHandler):
    def _responder(self, codigo, cuerpo, tipo="application/json; charset=utf-8"):
        datos = cuerpo if isinstance(cuerpo, bytes) else json.dumps(cuerpo, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/":
            self._responder(200, INDEX.read_bytes(), "text/html; charset=utf-8")
        elif url.path == "/api/archivos":
            self._responder(200, sorted(p.name for p in CARPETA.glob("*.csv")))
        elif url.path == "/api/filas":
            try:
                _, filas = leer(ruta_csv(parse_qs(url.query).get("archivo", [""])[0]))
            except KeyError:
                self._responder(404, {"error": "archivo no encontrado"})
                return
            self._responder(200, filas)
        else:
            self._responder(404, {"error": "no encontrado"})

    def do_POST(self):
        if urlparse(self.path).path != "/api/guardar":
            self._responder(404, {"error": "no encontrado"})
            return
        cuerpo = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        try:
            ruta = ruta_csv(cuerpo.get("archivo", ""))
        except KeyError:
            self._responder(404, {"error": "archivo no encontrado"})
            return
        with CANDADO:
            columnas, filas = leer(ruta)
            fila = next((f for f in filas if f["context_id"] == cuerpo.get("context_id")), None)
            if fila is None:
                self._responder(404, {"error": "context_id no encontrado"})
                return
            for campo in CAMPOS_REVISION:
                if campo in cuerpo.get("campos", {}):
                    fila[campo] = str(cuerpo["campos"][campo])
            escribir(ruta, columnas, filas)
        self._responder(200, {"ok": True})

    def log_message(self, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--puerto", type=int, default=3000)
    args = parser.parse_args()
    servidor = ThreadingHTTPServer(("127.0.0.1", args.puerto), Manejador)
    print(f"Revisión de etiquetas en http://localhost:{args.puerto}  (Ctrl+C para salir)")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
