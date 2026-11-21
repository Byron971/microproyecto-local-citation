"""Endpoints opt-in de la demostración científica M/S (sin modificar A4)."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

router = APIRouter(tags=["Ciencia M/S"])


class FragmentoMS(BaseModel):
    chunk_id: str = Field(min_length=1, max_length=120)
    texto: str = Field(min_length=1, max_length=5000)
    seccion: str | None = Field(default=None, max_length=200)


class ConsultaMS(BaseModel):
    contexto: str = Field(min_length=1, max_length=4000)
    titulo: str = Field(min_length=1, max_length=600)
    abstract: str = Field(min_length=1, max_length=12000)
    candidatos: list[FragmentoMS] = Field(min_length=3, max_length=100)

    @model_validator(mode="after")
    def validar(self):
        if self.contexto.count("TARGETCIT") != 1:
            raise ValueError("El contexto debe contener TARGETCIT exactamente una vez")
        if not self.titulo.strip() or not self.abstract.strip():
            raise ValueError("Titulo y abstract no pueden estar vacios")
        ids = [c.chunk_id.strip() for c in self.candidatos]
        if not all(ids) or len(ids) != len(set(ids)) or any(not c.texto.strip() for c in self.candidatos):
            raise ValueError("IDs duplicados/vacios o fragmentos sin texto")
        total = len(self.contexto) + len(self.titulo) + len(self.abstract) + sum(len(c.texto) for c in self.candidatos)
        if total > 60000:
            raise ValueError("El texto de la solicitud supera 60000 caracteres")
        return self


@router.get("/api/analisis-cita-ms/estado")
def estado_ms():
    root = Path(__file__).resolve().parents[2]
    ARTIFACTS = root / "proyecto_de_grado/artifacts/experimentos_10"
    MANIFEST_SCIBERT = root / "proyecto_de_grado/docs/evidencias_recuperacion_densa_a1/manifiesto_modelo.json"
    manifest_scibert_existe = MANIFEST_SCIBERT.is_file()
    checkpoint_m_existe = (ARTIFACTS / "M/model.safetensors").is_file()
    checkpoint_s_existe = (ARTIFACTS / "S/model.safetensors").is_file()
    manifiesto_m_existe = (ARTIFACTS / "M/manifiesto_entrenamiento.json").is_file()
    manifiesto_s_existe = (ARTIFACTS / "S/manifiesto_entrenamiento.json").is_file()
    artefactos_presentes = all((
        manifest_scibert_existe, checkpoint_m_existe, checkpoint_s_existe,
        manifiesto_m_existe, manifiesto_s_existe,
    ))
    return {
        "habilitado": True,  # La ruta HTTP esta publicada, no es un chequeo de inferencia.
        "artefactos_locales_presentes": artefactos_presentes,
        "inferencia_verificada_por_estado": False,  # Este GET no ejecuta modelos.
        "manifest_scibert_existe": manifest_scibert_existe,
        "checkpoint_m_existe": checkpoint_m_existe,
        "checkpoint_s_existe": checkpoint_s_existe,
        "manifiesto_m_existe": manifiesto_m_existe,
        "manifiesto_s_existe": manifiesto_s_existe,
        "nota": (
            "La ruta esta habilitada, pero no se ha verificado carga ni inferencia en "
            "esta consulta. Compruebe la carga real con POST; los archivos por si "
            "solos no garantizan que los modelos funcionen."
        ),
    }


@router.post("/api/analisis-cita-ms")
def analisis_cita_ms(consulta: ConsultaMS):
    from src.app.ms_runtime import analizar_seguro
    try:
        return analizar_seguro(
            consulta.contexto, consulta.titulo, consulta.abstract,
            [c.model_dump() for c in consulta.candidatos],
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (OSError, RuntimeError) as exc:
        # Evitar exponer rutas internas y trazas en HTTP; ver error en log del servidor.
        import logging
        logging.getLogger(__name__).exception("Error al cargar o ejecutar M/S")
        raise HTTPException(status_code=503, detail="Modelos científicos no disponibles; revisar registro del servidor") from exc
