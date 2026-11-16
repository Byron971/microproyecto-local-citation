"""Auditoría READ-ONLY del despliegue HTTPS y Cost Explorer.

Sin acceso AWS no hay factura verificable. Consultar Cost Explorer solo tras
--aws-cost y usar una etiqueta de costo habilitada por la cuenta.
No ejecuta terraform, despliega, modifica permisos ni publica imágenes.
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import subprocess
from datetime import date
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def https_url(raw: str) -> str:
    u = urlsplit(raw)
    if (u.scheme != "https" or not u.hostname or u.username or u.password
            or u.query or u.fragment or u.path not in ("", "/") or u.port not in (None, 443)):
        raise ValueError("Solo se permite URL HTTPS de origen público, sin ruta ni credenciales.")
    hostname = u.hostname.lower()
    if hostname in ("localhost", "host.docker.internal") or hostname.endswith(".local"):
        raise ValueError("No se permite destino local.")
    try:
        ip = ipaddress.ip_address(hostname)
        if not ip.is_global:
            raise ValueError("No se permite IP privada o reservada.")
    except ValueError as exc:
        if "No se permite IP" in str(exc):
            raise
    return raw.rstrip("/")


def get_json(url: str, timeout: int = 15) -> dict:
    with urlopen(Request(url, headers={"Accept": "application/json"}), timeout=timeout) as res:
        if res.status != 200:
            raise RuntimeError(f"HTTPS respondió {res.status}.")
        return json.load(res)


def check_https(api: str, frontend: str, *, request=get_json) -> dict:
    api, frontend = https_url(api), https_url(frontend)
    state = request(api + "/api/estado")
    caps = request(api + "/api/capacidades")
    if state.get("listo") is not True:
        raise RuntimeError("API HTTPS no declara su baseline como listo.")
    if caps.get("servicio", {}).get("listo") is not True:
        raise RuntimeError("Capacidades HTTPS no confirman backend listo.")
    with urlopen(Request(frontend + "/", headers={"Accept": "text/html"}), timeout=15) as resp:
        if resp.status != 200 or "text/html" not in resp.headers.get("Content-Type", ""):
            raise RuntimeError("CloudFront no respondió HTML correcto.")
        content = resp.read(128 * 1024)
        if b"<html" not in content.lower():
            raise RuntimeError("La URL frontend no presenta una aplicación HTML.")
    return {
        "api_https": "verificado",
        "frontend_https": "verificado",
        "api_host": urlsplit(api).hostname,
        "frontend_host": urlsplit(frontend).hostname,
        "scibert_disponible": bool(caps.get("tareas", {}).get("top3_scibert", {}).get("disponible")),
        "a4_a_disponible": bool(caps.get("tareas", {}).get("clasificacion_nueve_funciones", {}).get("disponible")),
        "a4_b_disponible": bool(caps.get("tareas", {}).get("clasificacion_nueve_funciones_b", {}).get("disponible")),
        "limite": "HTTPS y health check no prueban inferencia Torch. Ejecutar smoke --cientifico.",
    }


def _aws(args: list[str], runner=subprocess.run) -> dict:
    result = runner(["aws", *args, "--output", "json"], check=True,
                    capture_output=True, text=True, timeout=35)
    return json.loads(result.stdout)


def actual_tagged_cost(project_tag: str, start: str, end: str,
                       *, caller=_aws) -> dict:
    if not project_tag or len(project_tag) > 90 or "\n" in project_tag:
        raise ValueError("Etiqueta Project inválida.")
    a, b = date.fromisoformat(start), date.fromisoformat(end)
    if not a < b or (b - a).days > 32:
        raise ValueError("Rango Cost Explorer: máximo 32 días, inicio < fin.")
    identity = caller(["sts", "get-caller-identity"])
    query = {
        "TimePeriod": {"Start": start, "End": end},
        "Granularity": "DAILY", "Metrics": ["UnblendedCost"],
        "Filter": {"Tags": {"Key": "Project", "Values": [project_tag],
                            "MatchOptions": ["EQUALS"]}},
        "GroupBy": [{"Type": "DIMENSION", "Key": "SERVICE"}],
    }
    response = caller(["ce", "get-cost-and-usage",
                       "--time-period", json.dumps(query["TimePeriod"]),
                       "--granularity", query["Granularity"],
                       "--metrics", "UnblendedCost",
                       "--filter", json.dumps(query["Filter"]),
                       "--group-by", json.dumps(query["GroupBy"])])
    groups = {}
    for day in response.get("ResultsByTime", []):
        for service in day.get("Groups", []):
            name = service["Keys"][0]
            metric = service["Metrics"]["UnblendedCost"]
            if metric["Unit"] != "USD":
                raise RuntimeError("Cost Explorer entregó unidad distinta a USD.")
            groups[name] = groups.get(name, Decimal("0")) + Decimal(metric["Amount"])
    return {
        "estado": "costo_atribuido_por_etiqueta" if groups else "sin_datos_atribuibles_no_es_cero_verificado",
        "tag": {"Project": project_tag},
        "periodo_utc": {"inicio": start, "fin_exclusivo": end},
        "account_sha8": hashlib.sha256(identity["Account"].encode()).hexdigest()[:8],
        "servicios_usd": {k: str(v) for k, v in sorted(groups.items())},
        "subtotal_usd": str(sum(groups.values(), Decimal("0"))) if groups else None,
        "advertencia": (
            "Cost Explorer puede tener rezagos y requiere Project como cost allocation tag activa. "
            "No incluye consumo sin etiqueta y no sustituye la factura de AWS."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--api-url", help="HTTPS real de API Gateway")
    p.add_argument("--frontend-url", help="HTTPS real de CloudFront")
    p.add_argument("--aws-cost", action="store_true", help="Autoriza consulta AWS read-only")
    p.add_argument("--project-tag", default="citas-api")
    p.add_argument("--start", help="YYYY-MM-DD inicial del costo")
    p.add_argument("--end", help="YYYY-MM-DD final exclusivo del costo")
    p.add_argument("--output", required=True, type=Path,
                   help="Reporte JSON nuevo; no sobrescribe evidencia.")
    a = p.parse_args(argv)
    out = {
        "estado": "auditoria_parcial_sin_gold",
        "https": {"estado": "no_verificado_no_se_proporcionaron_urls"},
        "costos": {"estado": "no_consultado_sin_autorizacion_o_credenciales"},
    }
    try:
        if bool(a.api_url) != bool(a.frontend_url):
            raise ValueError("Proporciona juntas las URL API y frontend.")
        if a.api_url:
            out["https"] = check_https(a.api_url, a.frontend_url)
        if a.aws_cost:
            if not a.start or not a.end:
                raise ValueError("--aws-cost exige --start y --end.")
            out["costos"] = actual_tagged_cost(a.project_tag, a.start, a.end)
        a.output.parent.mkdir(parents=True, exist_ok=True)
        with a.output.open("x", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
            f.write("\n")
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        p.exit(2, f"Auditoría incompleta: {exc}\n")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
