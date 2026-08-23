"""Offline contract tests for the app-cli parity drift alarm."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType


def _load() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts" / "check_app_cli_parity.py"
    spec = importlib.util.spec_from_file_location("check_app_cli_parity", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _manifest(path: Path, sha: str) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "donor_repository": "https://github.com/microsoft/amplifier-app-cli.git",
                "audited_commit": sha,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_current_donor_passes(tmp_path: Path, capsys) -> None:
    module = _load()
    sha = "a" * 40
    manifest = _manifest(tmp_path / "baseline.json", sha)

    assert module.main(["--manifest", str(manifest), "--head", sha]) == 0
    assert "baseline is current" in capsys.readouterr().out


def test_changed_donor_requires_a_real_review(tmp_path: Path, capsys) -> None:
    module = _load()
    manifest = _manifest(tmp_path / "baseline.json", "a" * 40)

    assert module.main(["--manifest", str(manifest), "--head", "b" * 40]) == 2
    output = capsys.readouterr().out
    assert "PARITY REVIEW REQUIRED" in output
    assert "record a new audit pass" in output


def test_invalid_baseline_fails_closed(tmp_path: Path, capsys) -> None:
    module = _load()
    manifest = _manifest(tmp_path / "baseline.json", "main")

    assert module.main(["--manifest", str(manifest), "--head", "b" * 40]) == 1
    assert "full lowercase commit SHA" in capsys.readouterr().out
