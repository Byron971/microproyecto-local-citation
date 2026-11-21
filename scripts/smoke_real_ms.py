"""Smoke reproducible M/S con pesos reales, sin Gold ni salida de texto privado.

Entrada: JSON de solicitud con contexto, titulo, abstract y candidatos.
Ejecuta directamente el pipeline de inferencia y compara contra una respuesta
anterior en tolerancia explicita. No registra el texto de los candidatos.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path


def digest_archivo(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def resumen(r: dict) -> dict:
    return {
        "recuperador": r["modelo_recuperacion"],
        "revision_scibert": r["revision_scibert"],
        "dispositivo": r["dispositivo"],
        "tokens_ab": r["tokens_ab"],
        "top3_ids": [x["chunk_id"] for x in r["top3"]],
        "clasificacion": {
            p: {"clase": r["clasificadores"][p]["clase"],
                "probabilidad": r["clasificadores"][p]["probabilidad"]}
            for p in ("M", "S")
        },
    }


def comparar(obtenido: dict, referencia: dict, tolerancia: float) -> list[str]:
    errores = []
    for campo in ("recuperador", "revision_scibert", "tokens_ab", "top3_ids"):
        if obtenido[campo] != referencia[campo]:
            errores.append(f"{campo} no coincide")
    # Un clon puede tener un dispositivo diferente; no exigir CPU/CUDA iguales.
    for pista in ("M", "S"):
        a = obtenido["clasificacion"][pista]
        b = referencia["clasificacion"][pista]
        if a["clase"] != b["clase"]:
            errores.append(f"{pista}: clase no coincide")
        if abs(a["probabilidad"] - b["probabilidad"]) > tolerancia:
            errores.append(f"{pista}: softmax fuera de tolerancia")
    return errores


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--solicitud", required=True, type=Path)
    p.add_argument("--referencia", required=True, type=Path)
    p.add_argument("--tolerancia", default=0.005, type=float)
    p.add_argument("--salida", type=Path)
    a = p.parse_args()
    if not 0 <= a.tolerancia <= 0.1:
        p.error("La tolerancia debe estar entre 0 y 0.1")
    try:
        solicitud = json.loads(a.solicitud.read_text(encoding="utf-8-sig"))
        referencia = json.loads(a.referencia.read_text(encoding="utf-8-sig"))
        if not all(k in solicitud for k in ("contexto", "titulo", "abstract", "candidatos")):
            raise ValueError("Faltan campos de la solicitud")
        if len(solicitud["candidatos"]) < 3:
            raise ValueError("Se requieren al menos tres candidatos")
        # Solo se importa el entorno científico después de leer el input.
        import torch
        import transformers
        import huggingface_hub
        from src.app.ms_runtime import analizar_seguro

        resultado = analizar_seguro(
            solicitud["contexto"], solicitud["titulo"], solicitud["abstract"],
            solicitud["candidatos"],
        )
        actual = resumen(resultado)
        esperado = resumen(referencia)
        errores = comparar(actual, esperado, a.tolerancia)
        reporte = {
            "ok": not errores,
            "errores": errores,
            "entrada_sha256": digest_archivo(a.solicitud),
            "referencia_sha256": digest_archivo(a.referencia),
            "python": platform.python_version(),
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "huggingface_hub": huggingface_hub.__version__,
            "tolerancia_softmax": a.tolerancia,
            "actual": actual,
            "esperado": esperado,
            "nota": "Caso TRAIN, no evalua calidad ni usa etiquetas Gold.",
        }
    except (ImportError, OSError, ValueError, KeyError, RuntimeError, TypeError) as exc:
        # No volcar texto de la solicitud, rutas absolutas, ni tracebacks en CI.
        print(json.dumps({"ok": False, "errores": [type(exc).__name__ + ": " + str(exc)[:180]]}, ensure_ascii=False))
        return 1
    if a.salida:
        a.salida.parent.mkdir(parents=True, exist_ok=True)
        a.salida.write_text(json.dumps(reporte, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(reporte, indent=2, ensure_ascii=False))
    return 0 if reporte["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
