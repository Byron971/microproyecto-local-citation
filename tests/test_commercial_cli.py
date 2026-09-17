import json

from src.evaluation.commercial.cli import main


def test_cli_check_only_validates_gold_and_prompts(tmp_path, capsys):
    gold = tmp_path / "gold.jsonl"
    prompts = tmp_path / "prompts.json"
    gold.write_text('{"id":"c1","input":"text","gold":"A"}\n', encoding="utf-8")
    prompts.write_text(json.dumps({"zero": "Classify {input}"}), encoding="utf-8")

    code = main(["--gold", str(gold), "--prompts", str(prompts), "--check-only"])

    assert code == 0
    out = capsys.readouterr().out
    assert "1 casos" in out
    assert "1 prompts" in out


def test_cli_requires_at_least_one_client_for_execution(tmp_path, capsys):
    gold = tmp_path / "gold.jsonl"
    prompts = tmp_path / "prompts.json"
    gold.write_text('{"id":"c1","input":"text","gold":"A"}\n', encoding="utf-8")
    prompts.write_text(json.dumps({"zero": "Classify {input}"}), encoding="utf-8")

    code = main(["--gold", str(gold), "--prompts", str(prompts)])

    assert code == 2
    assert "--client" in capsys.readouterr().err
