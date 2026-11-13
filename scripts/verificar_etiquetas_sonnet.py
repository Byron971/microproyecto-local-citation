"""Verifica la idoneidad de etiquetas_sonnet.csv para entrenar (issue #104).

  uv run --project packages/clasificacion-funcion python scripts/verificar_etiquetas_sonnet.py [--rapido]

Comprueba estructura, las 9 clases permitidas, abstenciones, coherencia con los lotes de entrada
y el manifiesto, y (sin --rapido) que no haya ids de gold/taller/piloto ni de 2014/2015.
Sale con codigo 1 si hay errores. Informe en proyecto_de_grado/anotacion/sonnet/verificacion_etiquetas.json."""
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from clasificacion_funcion import adaptador_proyecto_grado as ad  # noqa: E402
from clasificacion_funcion import verificacion_sonnet as vs  # noqa: E402

SONNET = REPO / "proyecto_de_grado/anotacion/sonnet"
LOTES = REPO / "proyecto_de_grado/artifacts/anotacion_sonnet/lotes"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--csv", type=Path, default=ad.ETIQUETAS_SONNET)
    ap.add_argument("--rapido", action="store_true", help="omite la carga de fuentes (fugas y titulo/abstract)")
    args = ap.parse_args()
    manifiesto = SONNET / "manifiesto_lotes.json"
    fuentes = papers = None
    if not args.rapido:
        fuentes, papers = ad.cargar_fuentes_104(), ad.cargar_papers()
    informe = vs.verificar(args.csv, json.loads(manifiesto.read_text(encoding="utf-8")) if manifiesto.is_file() else None,
                           LOTES, fuentes, papers)
    destino = SONNET / "verificacion_etiquetas.json"
    destino.write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
    r = informe["resumen"].get("distribucion", {})
    print(f"{'APTO' if informe['apto'] else 'NO APTO'} | filas={r.get('filas')} usables={r.get('usables_entrenamiento')} "
          f"abstenciones={r.get('abstenciones')}")
    for c, n in r.get("por_clase", {}).items():
        print(f"  {c:34s} {n:6d}")
    for m in informe["errores"]:
        print("ERROR:", m)
    for m in informe["avisos"]:
        print("aviso:", m)
    print("informe ->", destino)
    return 0 if informe["apto"] else 1


if __name__ == "__main__":
    sys.exit(main())
