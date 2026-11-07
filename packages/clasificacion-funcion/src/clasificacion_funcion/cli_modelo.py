"""Punto de entrada con modelo real: inyecta SciBERT (torch) a la CLI offline.

  PYTHONPATH=. uv run --project packages/clasificacion-funcion --group modelo \\
      python -m clasificacion_funcion.cli_modelo recuperar --limite 20
Subcomandos con torch: `recuperar` (paso 6); `entrenar` y `predecir` se agregan en el paso 8."""
from recuperacion_densa.codificador_torch import TorchSciBERTEncoder

from . import cli, revision


def fabrica_recuperador(args) -> TorchSciBERTEncoder:
    """Recuperador unico para ambos encoders: SciBERT base en la revision de A1."""
    model_id, rev = revision.modelo("scibert")
    return TorchSciBERTEncoder(rev, model_id, args.device, args.batch_size, args.max_length,
                               manifiesto=args.manifiesto_modelo)


def main(argv: list[str] | None = None) -> int:
    return cli.main(argv, fabrica_codificador=fabrica_recuperador)


if __name__ == "__main__":
    raise SystemExit(main())
