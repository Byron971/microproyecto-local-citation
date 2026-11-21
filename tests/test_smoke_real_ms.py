"""Validacion del comparador de inferencia, sin descargar ni cargar pesos."""
from scripts.smoke_real_ms import comparar, resumen


def ejemplo(prob_m=0.458719, prob_s=0.866312, device="cpu"):
    return {
        "modelo_recuperacion": "scibert_base_mean_pooling_cosine",
        "revision_scibert": "24f92d32b1bfb0bcaf9ab193ff3ad01e87732fc1",
        "dispositivo": device, "tokens_ab": 512,
        "top3": [{"chunk_id": s} for s in ("p00011-p00012", "p00002-p00003", "p00065-p00065")],
        "clasificadores": {
            "M": {"clase": "Evidence", "probabilidad": prob_m},
            "S": {"clase": "Background", "probabilidad": prob_s},
        },
    }


def test_resumen_sin_texto_privado():
    e = ejemplo()
    e["top3"][0]["texto"] = "TEXTO NO PUBLICABLE"
    result = resumen(e)
    assert result["top3_ids"][0] == "p00011-p00012"
    assert "TEXTO NO PUBLICABLE" not in str(result)


def test_coincidencia_completa():
    assert comparar(resumen(ejemplo()), resumen(ejemplo()), 0.005) == []


def test_cambio_dispositivo_no_se_confunde_con_error():
    assert comparar(resumen(ejemplo(device="cpu")), resumen(ejemplo(device="cuda")), 0.005) == []


def test_tolerancia_probabilidad():
    assert comparar(resumen(ejemplo(prob_m=0.460)), resumen(ejemplo()), 0.005) == []
    assert any("M: softmax" in x for x in comparar(
        resumen(ejemplo(prob_m=0.480)), resumen(ejemplo()), 0.005))


def test_top3_diferente_falla():
    other = ejemplo()
    other["top3"][0]["chunk_id"] = "otro"
    assert "top3_ids no coincide" in comparar(resumen(other), resumen(ejemplo()), 0.005)


def test_clase_diferente_falla():
    other = ejemplo()
    other["clasificadores"]["S"]["clase"] = "Evidence"
    assert "S: clase no coincide" in comparar(resumen(other), resumen(ejemplo()), 0.005)
