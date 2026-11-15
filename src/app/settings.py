"""Configuración del servicio vigente, sin secretos y sin dependencias externas.

La API actual sirve TF-IDF+reordenador y Top-3 BM25, NO SciBERT ni un LLM
integrado. Las opciones no implementadas fallan al iniciar, en vez de
aparentar que un cambio de variable activa modelos inexistentes.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import Mapping

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INSIGHTS = ROOT / "data" / "processed" / "dashboard_insights.json"
DEFAULT_TOP3_CORPUS = ROOT / "proyecto_de_grado" / "artifacts" / "top3_s2" / "casos_train.json"
_ALLOWED_ENV = {"development", "test", "production"}
_ALLOWED_LOG_LEVEL = {"critical", "error", "warning", "info", "debug"}
_HOSTNAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]*$")


def _value(env: Mapping[str, str], name: str, default: str) -> str:
    raw = env.get(name, default)
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"{name} no puede estar vacío")
    return raw.strip()


def _path(env: Mapping[str, str], name: str, default: Path) -> Path:
    raw = env.get(name)
    if raw is None:
        return default
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"{name} no puede estar vacío")
    candidate = Path(raw.strip()).expanduser()
    # Resolver respecto de la raíz del repo, nunca del cwd de uvicorn/Docker.
    return (candidate if candidate.is_absolute() else ROOT / candidate).resolve()


@dataclass(frozen=True)
class AppSettings:
    environment: str
    host: str
    port: int
    log_level: str
    recommender_backend: str
    top3_backend: str
    model_device: str
    insights_path: Path
    top3_corpus_path: Path
    scibert_enabled: bool = False
    scibert_manifest: Path | None = None
    scibert_device: str = "cpu"
    a4_enabled: bool = False
    a4_run: Path | None = None
    a4_evidence: Path | None = None
    a4_encoder_manifest: Path | None = None
    a4_device: str = "cpu"

    def public_info(self) -> dict[str, str]:
        """Solo nombres de backends y entorno, sin rutas ni credenciales."""
        return {
            "entorno": self.environment,
            "recomendador": self.recommender_backend,
            "top3": self.top3_backend,
            "dispositivo": self.model_device,
        }


def get_app_settings(environ: Mapping[str, str] | None = None) -> AppSettings:
    env = os.environ if environ is None else environ

    stage = _value(env, "APP_ENV", "development").lower()
    if stage not in _ALLOWED_ENV:
        raise ValueError("APP_ENV debe ser development, test o production")

    host = _value(env, "APP_HOST", "127.0.0.1")
    if not (_HOSTNAME.fullmatch(host) or host in {"::", "::1"}):
        raise ValueError("APP_HOST debe ser un host/IP, no una URL ni una ruta")

    raw_port = _value(env, "APP_PORT", "8000")
    if not raw_port.isdecimal() or not 1 <= int(raw_port) <= 65535:
        raise ValueError("APP_PORT debe ser un entero de 1 a 65535")
    port = int(raw_port)

    log_level = _value(env, "APP_LOG_LEVEL", "info").lower()
    if log_level not in _ALLOWED_LOG_LEVEL:
        raise ValueError("APP_LOG_LEVEL inválido")

    recommender = _value(
        env, "APP_RECOMMENDER_BACKEND", "packaged_tfidf_linear"
    ).lower()
    if recommender != "packaged_tfidf_linear":
        raise ValueError(
            "APP_RECOMMENDER_BACKEND no disponible: solo packaged_tfidf_linear está integrado"
        )

    top3 = _value(env, "APP_TOP3_BACKEND", "bm25_lexical").lower()
    if top3 != "bm25_lexical":
        raise ValueError(
            "APP_TOP3_BACKEND no disponible: solo bm25_lexical está integrado"
        )

    device = _value(env, "APP_MODEL_DEVICE", "cpu").lower()
    if device != "cpu":
        raise ValueError(
            "APP_MODEL_DEVICE no disponible: el modelo empaquetado actual sirve en CPU"
        )

    # Back-end denso INDEPENDIENTE de BM25: opt-in explícito. SciBERT está
    # offline por defecto; jamás insinuar que cambiar APP_TOP3_BACKEND lo activa.
    raw_dense = _value(env, "APP_SCIBERT_ENABLED", "false").lower()
    if raw_dense not in {"true", "false"}:
        raise ValueError("APP_SCIBERT_ENABLED debe ser true o false")
    dense_enabled = raw_dense == "true"
    dense_device = _value(env, "APP_SCIBERT_DEVICE", "cpu").lower()
    if dense_device not in {"cpu", "cuda", "auto"}:
        raise ValueError("APP_SCIBERT_DEVICE debe ser cpu, cuda o auto")
    raw_manifest = env.get("APP_SCIBERT_MANIFEST")
    if dense_enabled and (not isinstance(raw_manifest, str) or not raw_manifest.strip()):
        raise ValueError("APP_SCIBERT_MANIFEST es obligatorio al activar SciBERT")
    manifest = (_path(env, "APP_SCIBERT_MANIFEST", ROOT / "missing-manifest.json")
                if dense_enabled else None)

    # Clasificación provisional de nueve funciones: no se enciende sin pesos A4.
    raw_a4 = _value(env, "APP_A4_ENABLED", "false").lower()
    if raw_a4 not in {"true", "false"}:
        raise ValueError("APP_A4_ENABLED debe ser true o false")
    a4_enabled = raw_a4 == "true"
    a4_device = _value(env, "APP_A4_DEVICE", "cpu").lower()
    if a4_device not in {"cpu", "cuda", "auto"}:
        raise ValueError("APP_A4_DEVICE debe ser cpu, cuda o auto")
    if a4_enabled and (not isinstance(env.get("APP_A4_RUN"), str)
                       or not env.get("APP_A4_RUN", "").strip()):
        raise ValueError("APP_A4_RUN es obligatorio para servir un checkpoint real")
    a4_run = (_path(env, "APP_A4_RUN", ROOT / "missing-a4-run") if a4_enabled else None)
    a4_evidence = (_path(env, "APP_A4_EVIDENCE",
                 ROOT / "proyecto_de_grado/docs/evidencias_clasificacion_a4/scibert_A_42/manifiesto.json")
                 if a4_enabled else None)
    a4_encoder_manifest = (_path(env, "APP_A4_ENCODER_MANIFEST",
                 ROOT / "proyecto_de_grado/docs/evidencias_clasificacion_a4/manifiesto_modelo_scibert.json")
                 if a4_enabled else None)

    return AppSettings(
        environment=stage,
        host=host,
        port=port,
        log_level=log_level,
        recommender_backend=recommender,
        top3_backend=top3,
        model_device=device,
        insights_path=_path(env, "APP_INSIGHTS_PATH", DEFAULT_INSIGHTS),
        top3_corpus_path=_path(env, "TOP3_CORPUS_PATH", DEFAULT_TOP3_CORPUS),
        scibert_enabled=dense_enabled,
        scibert_manifest=manifest,
        scibert_device=dense_device,
        a4_enabled=a4_enabled,
        a4_run=a4_run,
        a4_evidence=a4_evidence,
        a4_encoder_manifest=a4_encoder_manifest,
        a4_device=a4_device,
    )
