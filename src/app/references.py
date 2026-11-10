"""Metadatos oficiales para referencias; no depende del dataset de entrenamiento.

La descarga ocurre al copiar, no al recomendar. Se cachean solo respuestas válidas.
"""
from functools import lru_cache
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ReferenceUnavailable(Exception):
    pass


@lru_cache(maxsize=512)
def fetch_bibtex(paper_id: str) -> dict[str, str]:
    """Recibe un ID ya validado contra los artículos del modelo por el endpoint."""
    url = f"https://aclanthology.org/{paper_id}.bib"
    request = Request(url, headers={"Accept": "application/x-bibtex, text/plain", "User-Agent": "LocalCitation/0.1 (bibliographic metadata)"})
    try:
        with urlopen(request, timeout=8) as response:
            body = response.read(262_145)
        if len(body) > 262_144:
            raise ReferenceUnavailable("La respuesta bibliográfica es demasiado grande.")
        bibtex = body.decode("utf-8-sig").strip()
        if not bibtex.startswith("@"):
            raise ReferenceUnavailable("La fuente no devolvió metadatos bibliográficos válidos.")
    except (HTTPError, URLError, TimeoutError, UnicodeError, OSError) as exc:
        raise ReferenceUnavailable("No se pudieron consultar los metadatos de ACL Anthology. Inténtalo de nuevo.") from exc
    return {"paper_id": paper_id, "bibtex": bibtex, "source_url": f"https://aclanthology.org/{paper_id}/"}
