"""Punto de entrada con modelo real: inyecta SciBERT (torch) a la CLI offline."""
from __future__ import annotations

from . import cli
from .codificador_torch import TorchSciBERTEncoder
from .revision import MODEL_ID


def fabrica(args) -> TorchSciBERTEncoder:
    return TorchSciBERTEncoder(args.revision, MODEL_ID, args.device, args.batch_size,
                               args.max_length)


def main(argv: list[str] | None = None) -> int:
    return cli.main(argv, fabrica_codificador=fabrica)


if __name__ == "__main__":
    raise SystemExit(main())
