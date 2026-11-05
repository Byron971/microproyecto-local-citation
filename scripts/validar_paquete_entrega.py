"""Gate auditable del paquete de entrega de despliegue (#119).

No afirma despliegue externo por tener Docker en GitHub Actions. Sin URLs HTTPS
comprobables y evidencia de verificación independiente, es BORRADOR.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import ipaddress
import json
from pathlib import Path
import sys
from typing import Any
from urllib.parse import urlsplit

REPO_URL = "https://github.com/Byron971/microproyecto-local-citation"
MAX_TEAM = 5
REQUIRED_CHECKS = {
    "liveness", "readiness", "modelo_empacado_real", "capacidades",
    "inferencia_de_articulos", "top3_bm25", "validacion_422",
    "tablero_nginx", "interfaz_top3", "css_top3", "js_top3", "proxy_api",
}


def validate_external_url(value: object, name: str) -> str:
    """Validación sintáctica, NO comprobación DNS/red/certificado."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name}: no se proporcionó una URL")
    raw = value.strip()
    try:
        url = urlsplit(raw)
        host = url.hostname
        port = url.port
    except ValueError as exc:
        raise ValueError(f"{name}: URL inválida") from exc
    if (
        url.scheme != "https" or not host or url.username or url.password
        or url.query or url.fragment or url.path not in ("", "/")
        or (port is not None and not 1 <= port <= 65535)
    ):
        raise ValueError(
            f"{name}: requiere base HTTPS sin credenciales, query, fragmento ni ruta"
        )
    normalized = host.lower().rstrip(".")
    if (
        normalized == "localhost" or normalized.endswith(".localhost")
        or normalized.endswith((".local", ".internal", ".test", ".example", ".invalid"))
        or "." not in normalized
    ):
        raise ValueError(f"{name}: no corresponde a un dominio externo candidato")
    try:
        ip = ipaddress.ip_address(normalized)
    except ValueError:
        pass  # Host DNS público candidato; NO se realiza resolución aquí.
    else:
        if not ip.is_global:
            raise ValueError(f"{name}: dirección no pública")
    return raw.rstrip("/")


def read_manifest(path: Path) -> dict[str, Any]:
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("El manifiesto debe ser un objeto JSON")
    return parsed


def audit_manifest(
    manifest: dict[str, Any], *, external_probe: dict[str, Any] | None = None
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    title = manifest.get("project_title")
    if not isinstance(title, str) or not title.strip():
        blockers.append("Falta nombre del proyecto.")

    team = manifest.get("team")
    if (
        not isinstance(team, list) or len(team) != MAX_TEAM
        or not all(isinstance(name, str) and name.strip() for name in team)
        or len(set(name.strip().casefold() for name in team)) != MAX_TEAM
    ):
        blockers.append("Deben constar cinco integrantes únicos y completos.")

    if manifest.get("repository_url") != REPO_URL:
        blockers.append("El enlace GitHub no coincide con el repositorio canónico.")

    checked_urls: dict[str, str] = {}
    for key in ("application_url", "api_url"):
        try:
            checked_urls[key] = validate_external_url(manifest.get(key), key)
        except ValueError as exc:
            blockers.append(str(exc))

    instructions = manifest.get("reviewer_access_instructions")
    if (
        not isinstance(instructions, str) or not instructions.strip()
        or "PENDIENTE" in instructions.upper()
    ):
        blockers.append("Faltan instrucciones de acceso para evaluadores.")
    elif any(secret in instructions.lower() for secret in ("password=", "token=", "api_key=")):
        blockers.append("Posibles credenciales incrustadas en instrucciones.")

    evidence = manifest.get("evidence")
    if not isinstance(evidence, dict):
        blockers.append("Falta sección de evidencias versionadas.")
        evidence = {}
    ci_url = evidence.get("docker_ci_url")
    if not isinstance(ci_url, str) or not ci_url.startswith(REPO_URL + "/actions/runs/"):
        warnings.append("No se documentó un workflow de Docker CI del repositorio.")
    else:
        warnings.append(
            "El workflow Docker de GitHub prueba una red local de CI; NO es verificación externa."
        )

    external = manifest.get("external_validation")
    if not isinstance(external, dict) or external.get("performed") is not True:
        blockers.append("Falta comprobación independiente desde una red externa.")
    else:
        observer = external.get("observer")
        timestamp = external.get("checked_at_utc")
        proof_url = external.get("proof_url")
        if not isinstance(observer, str) or not observer.strip():
            blockers.append("Falta el responsable de la comprobación externa.")
        try:
            stamp = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
            if stamp.utcoffset() is None:
                raise ValueError()
            if stamp > datetime.now(timezone.utc):
                raise ValueError()
        except ValueError:
            blockers.append("Fecha UTC de comprobación externa inválida.")
        if not isinstance(proof_url, str) or not proof_url.startswith(REPO_URL + "/"):
            blockers.append("Falta URL de evidencia externa en el repositorio.")
        warnings.append("La comprobación humana declarada debe revisarse; el manifiesto no la certifica.")

    features = manifest.get("expected_final_features")
    if not isinstance(features, dict) or not (
        features.get("scibert_top3_required") is True
        and features.get("nine_function_classifier_required") is True
    ):
        blockers.append("El alcance final debe exigir SciBERT Top-3 y clasificación de nueve funciones.")
    warnings.append(
        "La API hoy expone TF-IDF+BM25; SciBERT y nueve funciones no están verificados como servicios."
    )

    if external_probe is None:
        blockers.append("No existe smoke externo ejecutado en esta evaluación.")
    else:
        checks = external_probe.get("checks")
        names = {c.get("name") for c in checks if isinstance(c, dict)} if isinstance(checks, list) else set()
        if external_probe.get("status") != "ok" or not REQUIRED_CHECKS.issubset(names):
            blockers.append("Smoke externo incompleto o fallido.")
        else:
            warnings.append(
                "Smoke de infraestructura OK desde este proceso; no prueba accesibilidad desde otra red."
            )
            blockers.append(
                "Smoke actual verifica el baseline, no SciBERT ni clasificador de 9 funciones."
            )

    return {
        "status": "NO_APTO_PARA_ENTREGA_FINAL" if blockers else "PENDIENTE_REVISION_HUMANA",
        "scope": "Despliegue: entrega de aplicación (35+15+15+35), no artículo científico",
        "project_title": title if isinstance(title, str) else "",
        "team": team if isinstance(team, list) else [],
        "repository_url": REPO_URL,
        "application_url": checked_urls.get("application_url"),
        "api_url": checked_urls.get("api_url"),
        "blockers": blockers,
        "warnings": warnings,
        "external_probe": external_probe,
        "manifest_is_not_proof": True,
    }


def report_markdown(result: dict[str, Any]) -> str:
    def safe(value: object) -> str:
        return str(value).replace("|", "/").replace("\n", " ").replace("<", "&lt;")

    lines = [
        "# Paquete de entrega de despliegue — BORRADOR",
        "",
        f"Estado: **{safe(result['status'])}**.",
        "",
        f"Proyecto: {safe(result['project_title'])}",
        "",
        "Integrantes:",
    ]
    lines += [f"- {safe(name)}" for name in result["team"]]
    lines += [
        "",
        f"Repositorio: {result['repository_url']}",
        "",
        f"Aplicación externa: {result['application_url'] or 'PENDIENTE: no verificada'}",
        "",
        f"API externa: {result['api_url'] or 'PENDIENTE: no verificada'}",
        "",
        "## Bloqueos de entrega",
    ]
    lines += [f"- {safe(x)}" for x in result["blockers"]] or ["- Sin bloqueos automáticos; revisión humana pendiente."]
    lines += ["", "## Limitaciones y advertencias"]
    lines += [f"- {safe(x)}" for x in result["warnings"]]
    lines += [
        "", "## Cobertura de rúbrica de despliegue",
        "", "| Criterio | Puntos | Evidencia pendiente |",
        "|---|---:|---|",
        "| Funcionamiento | 35 | Servicio público, modelos finales, latencia y memoria verificadas |",
        "| Reproducibilidad | 15 | Clon limpio, README y recursos/versiones |",
        "| Parametrización | 15 | Settings aprobados y comprobados en entorno real |",
        "| Interfaz | 35 | Prueba externa y explicación honesta de resultados |",
        "",
        "Este borrador NO se debe presentar como entrega final hasta cerrar los bloqueos.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Validar paquete de entrega, sin inventar URL externa.")
    p.add_argument("--manifest", type=Path, default=Path("config/entrega_despliegue.example.json"))
    p.add_argument("--output-dir", type=Path, default=Path("artifacts/paquete_entrega"))
    p.add_argument("--probe", action="store_true", help="Ejecuta smoke contra URLs del manifiesto, si son válidas.")
    p.add_argument("--strict", action="store_true", help="Falla si falta evidencia de entrega final.")
    args = p.parse_args(argv)
    try:
        manifest = read_manifest(args.manifest)
        probe = None
        if args.probe:
            api = validate_external_url(manifest.get("api_url"), "api_url")
            app = validate_external_url(manifest.get("application_url"), "application_url")
            from scripts.smoke_despliegue import smoke
            probe = smoke(api, app, timeout=30, check_ingress_limit=False)
        result = audit_manifest(manifest, external_probe=probe)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "auditoria.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (args.output_dir / "borrador_entrega.md").write_text(
            report_markdown(result), encoding="utf-8"
        )
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"Paquete inválido: {exc}", file=sys.stderr)
        return 2
    print(f"Estado: {result['status']} | Bloqueos: {len(result['blockers'])}")
    print(f"Reporte: {args.output_dir / 'borrador_entrega.md'}")
    if args.strict and result["blockers"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
