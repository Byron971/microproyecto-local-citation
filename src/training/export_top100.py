from pathlib import Path

from src.data.load_data import load_json
from src.training.run_tfidf_baseline import export_top100


def export_split_top100(
    raw_dir: str | Path,
    output_dir: str | Path,
    split_name: str,
) -> Path:
    """Genera y guarda el Top-100 TF-IDF para un split."""
    raw_path = Path(raw_dir)
    output_path = Path(output_dir) / f"{split_name}_tfidf_top100.json"

    papers = load_json(raw_path / "papers.json")
    contexts = load_json(raw_path / "contexts.json")
    split = load_json(raw_path / f"{split_name}.json")

    export_top100(
        papers=papers,
        contexts=contexts,
        split=split,
        output_path=output_path,
    )

    return output_path

    