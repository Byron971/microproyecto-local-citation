"""Auditoría HTTPS/costos: tests aislados sin red ni permisos AWS."""
import json

import pytest

from scripts.ci.audit_https_aws import actual_tagged_cost, https_url, main


@pytest.mark.parametrize("url", [
    "http://api.example.org", "https://localhost",
    "https://127.0.0.1", "https://192.168.0.10",
    "https://user:pass@api.example.org", "https://api.example.org/admin",
    "https://api.example.org?key=secret", "file:///etc/passwd",
])
def test_audit_rejects_unsafe_or_non_https_destinations(url):
    with pytest.raises(ValueError):
        https_url(url)


def test_audit_accepts_public_https_only():
    assert https_url("https://abc.execute-api.us-east-1.amazonaws.com") == (
        "https://abc.execute-api.us-east-1.amazonaws.com"
    )


def test_real_costs_are_read_from_ce_and_summed_by_service():
    events = []

    def fake_aws(args):
        events.append(args)
        if args[0] == "sts":
            return {"Account": "111111111111"}
        assert args[0:2] == ["ce", "get-cost-and-usage"]
        tag_filter = json.loads(args[args.index("--filter") + 1])
        assert tag_filter["Tags"]["Key"] == "Project"
        assert tag_filter["Tags"]["Values"] == ["citas-api"]
        return {"ResultsByTime": [
            {"Groups": [
                {"Keys": ["Amazon Elastic Container Service"], "Metrics": {
                    "UnblendedCost": {"Amount": "1.25", "Unit": "USD"}}},
                {"Keys": ["Amazon CloudFront"], "Metrics": {
                    "UnblendedCost": {"Amount": "0.15", "Unit": "USD"}}},
            ]},
            {"Groups": [
                {"Keys": ["Amazon Elastic Container Service"], "Metrics": {
                    "UnblendedCost": {"Amount": "2.50", "Unit": "USD"}}},
            ]},
        ]}
    report = actual_tagged_cost("citas-api", "2026-11-01", "2026-11-15",
                                caller=fake_aws)
    assert report["estado"] == "costo_atribuido_por_etiqueta"
    assert report["subtotal_usd"] == "3.90"
    assert report["servicios_usd"]["Amazon Elastic Container Service"] == "3.75"
    assert len(events) == 2
    assert len(report["account_sha8"]) == 8


def test_no_cost_data_is_not_falsely_reported_as_zero():
    def fake(args):
        if args[0] == "sts":
            return {"Account": "111111111111"}
        return {"ResultsByTime": []}
    report = actual_tagged_cost("citas-api", "2026-11-01", "2026-11-14",
                                caller=fake)
    assert report["subtotal_usd"] is None
    assert report["estado"] == "sin_datos_atribuibles_no_es_cero_verificado"


@pytest.mark.parametrize("a,b", [
    ("2026-11-15", "2026-11-14"),
    ("2026-10-01", "2026-11-15"),
    ("garbage", "2026-11-15"),
])
def test_cost_audit_rejects_invalid_period(a,b):
    with pytest.raises(ValueError):
        actual_tagged_cost("citas-api", a, b, caller=lambda _: {})


def test_no_remote_inputs_generates_honest_not_verified_report(tmp_path):
    output = tmp_path / "audit.json"
    assert main(["--output", str(output)]) == 0
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["https"]["estado"] == "no_verificado_no_se_proporcionaron_urls"
    assert result["costos"]["estado"] == "no_consultado_sin_autorizacion_o_credenciales"
    with pytest.raises(SystemExit) as err:
        main(["--output", str(output)])
    assert err.value.code == 2
