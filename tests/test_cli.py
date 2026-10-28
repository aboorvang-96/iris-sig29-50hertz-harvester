"""CLI offline tests."""

from __future__ import annotations

import json

from iris_harvester.cli import main

from conftest import FIXTURES


def test_offline_cli_writes_jsonl(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("IRIS_DATABASE_URL", raising=False)
    output = tmp_path / "signals.jsonl"

    code = main(
        [
            "--offline",
            "--fixtures-dir",
            str(FIXTURES),
            "--gazetteer",
            str(FIXTURES / "gazetteer.csv"),
            "--output",
            str(output),
            "--no-db",
        ]
    )

    assert code == 0
    lines = output.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 4
    payloads = [json.loads(line) for line in lines]
    assert {p["source_id"] for p in payloads} == {
        "OST-6-1",
        "ostwind-2",
        "ostwind-3",
        "ostwind-4",
    }
    assert all(p["published_at"] is None for p in payloads)
    assert all(p["geom_status"] == "approximate" for p in payloads)
    captured = capsys.readouterr()
    assert "mode=offline sources=4" in captured.out
    assert "parsed=4 errors=0" in captured.out
    assert "database=skipped" in captured.out


def test_offline_cli_rerun_produces_identical_artifact(monkeypatch, tmp_path):
    monkeypatch.delenv("IRIS_DATABASE_URL", raising=False)
    output = tmp_path / "signals.jsonl"
    args = [
        "--offline",
        "--fixtures-dir",
        str(FIXTURES),
        "--gazetteer",
        str(FIXTURES / "gazetteer.csv"),
        "--output",
        str(output),
        "--no-db",
    ]
    assert main(args) == 0
    first = output.read_bytes()
    assert main(args) == 0
    assert output.read_bytes() == first


def test_missing_fixture_returns_error_code(monkeypatch, tmp_path):
    monkeypatch.delenv("IRIS_DATABASE_URL", raising=False)
    empty = tmp_path / "empty"
    empty.mkdir()
    output = tmp_path / "signals.jsonl"

    code = main(
        [
            "--offline",
            "--fixtures-dir",
            str(empty),
            "--gazetteer",
            str(FIXTURES / "gazetteer.csv"),
            "--output",
            str(output),
            "--no-db",
        ]
    )
    assert code == 2
    assert output.read_text(encoding="utf-8") == ""


def test_invalid_gazetteer_returns_configuration_error(monkeypatch, tmp_path):
    monkeypatch.delenv("IRIS_DATABASE_URL", raising=False)
    bad = tmp_path / "bad.csv"
    bad.write_text("name,lat,lon\nBad,nope,13.0\n", encoding="utf-8")

    code = main(
        [
            "--offline",
            "--fixtures-dir",
            str(FIXTURES),
            "--gazetteer",
            str(bad),
            "--output",
            str(tmp_path / "out.jsonl"),
            "--no-db",
        ]
    )
    assert code == 1
