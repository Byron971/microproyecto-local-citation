"""Comprueba las rutas públicas sin dependencias del modelo en el runner."""
import json
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def check(base_url):
    for path in ("/", "/static/top3.html"):
        with urlopen(base_url + path, timeout=30) as response:
            if response.status != 200:
                raise ValueError(f"Respuesta inesperada en {path}")
    with urlopen(base_url + "/api/estado", timeout=30) as response:
        if json.load(response).get("listo") is not True:
            raise ValueError("El modelo todavía no está listo")
    request = Request(
        base_url + "/api/recomendar",
        data=json.dumps({"contexto": "Neural networks for natural language processing", "top_k": 3}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=30) as response:
        if not json.load(response).get("recomendaciones"):
            raise ValueError("El API no devolvió recomendaciones")


def main():
    base_url = sys.argv[1].rstrip("/")
    for attempt in range(6):
        try:
            check(base_url)
            print(f"Smoke correcto: {base_url}")
            return
        except (HTTPError, URLError, TimeoutError, ValueError) as error:
            if attempt == 5:
                raise SystemExit(f"Smoke fallido: {error}") from error
            time.sleep(10)


if __name__ == "__main__":
    main()
