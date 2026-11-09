"""Mide HTTP público y recoge métricas de ECS sin modificar AWS.

Uso: python3 scripts/medir_despliegue.py --url URL --profile maia --output salida.json
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import statistics
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def aws(args, *command):
    result = subprocess.run(
        ["aws", "--profile", args.profile, "--region", args.region, *command, "--output", "json"],
        check=True, capture_output=True, text=True, timeout=60,
    )
    return json.loads(result.stdout)


def request(base, path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    started = time.perf_counter()
    try:
        req = Request(base + path, data=data, headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=30) as response:
            body = response.read()
            valid = response.status == 200
            if path == "/api/estado":
                valid = valid and json.loads(body).get("listo") is True
            elif path == "/api/recomendar":
                valid = valid and bool(json.loads(body).get("recomendaciones"))
            return {"status": response.status, "valid": valid,
                    "seconds": round(time.perf_counter() - started, 4)}
    except (HTTPError, URLError, TimeoutError, ValueError) as error:
        return {"status": getattr(error, "code", None), "valid": False,
                "seconds": round(time.perf_counter() - started, 4), "error": str(error)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--profile", default="maia")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--cluster", default="citas-api")
    parser.add_argument("--service", default="citas-api")
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.samples < 1:
        parser.error("--samples debe ser positivo")
    started = datetime.now(timezone.utc)
    url = args.url.rstrip("/")
    services = aws(args, "ecs", "describe-services", "--cluster", args.cluster, "--services", args.service)
    if services.get("failures") or not services.get("services"):
        raise SystemExit("No se pudo consultar el servicio ECS")
    service = services["services"][0]
    task = aws(args, "ecs", "describe-task-definition", "--task-definition", service["taskDefinition"])["taskDefinition"]
    payload = {"contexto": "Neural networks for natural language processing and machine translation", "top_k": 3}
    result = {
        "started_at_utc": started.isoformat(), "url": url,
        "region": args.region, "cluster": args.cluster, "service": args.service,
        "method": "External client; sequential requests; no concurrency; one fixed context; TLS connection per request; 3 warmups excluded",
        "ecs": {"status": service["status"], "desired": service["desiredCount"],
                "running": service["runningCount"], "pending": service["pendingCount"],
                "deployments": [{"status": d["status"], "rolloutState": d.get("rolloutState")} for d in service["deployments"]],
                "task_definition": service["taskDefinition"], "cpu_units": task["cpu"], "memory_mib": task["memory"]},
        "routes": {path: request(url, path) for path in ("/", "/static/top3.html", "/api/estado")},
        "warmups": [request(url, "/api/recomendar", payload) for _ in range(3)],
        "recommendation_payload": payload,
        "recommendations": [request(url, "/api/recomendar", payload) for _ in range(args.samples)],
    }
    durations = sorted(r["seconds"] for r in result["recommendations"] if r["valid"])
    if durations:
        result["latency_seconds"] = {"count": len(durations), "min": min(durations),
            "median": statistics.median(durations), "mean": statistics.mean(durations),
            "p95_nearest_rank": durations[math.ceil(.95 * len(durations)) - 1], "max": max(durations)}
    end = datetime.now(timezone.utc)
    window_start = started - timedelta(hours=1)
    result["cloudwatch"] = {"start_utc": window_start.isoformat(), "end_utc": end.isoformat(),
                            "period_seconds": 60, "metrics": {}}
    for metric in ("CPUUtilization", "MemoryUtilization"):
        points = aws(args, "cloudwatch", "get-metric-statistics", "--namespace", "AWS/ECS",
                     "--metric-name", metric, "--dimensions", f"Name=ClusterName,Value={args.cluster}",
                     f"Name=ServiceName,Value={args.service}", "--start-time", window_start.isoformat(),
                     "--end-time", end.isoformat(), "--period", "60", "--statistics", "Average", "Maximum")
        points["Datapoints"].sort(key=lambda p: p["Timestamp"])
        result["cloudwatch"]["metrics"][metric] = points
    result["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"ecs": result["ecs"], "routes": result["routes"],
                      "latency_seconds": result.get("latency_seconds"), "output": str(args.output)}, indent=2))
    if not all(r["valid"] for r in [*result["routes"].values(), *result["recommendations"]]):
        raise SystemExit("Se registraron respuestas fallidas; revisar la evidencia")


if __name__ == "__main__":
    main()
