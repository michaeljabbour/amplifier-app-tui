#!/usr/bin/env python3
"""Verify TUI version consistency and, on a PR, require a forward bump."""

from __future__ import annotations

import argparse
import re
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def _version_tuple(value: str) -> tuple[int, int, int]:
    match = SEMVER.fullmatch(value)
    if match is None:
        raise SystemExit(f"release version must be MAJOR.MINOR.PATCH, found {value!r}")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def _project_version(raw: str) -> str:
    project = tomllib.loads(raw).get("project", {})
    version = project.get("version") if isinstance(project, dict) else None
    if not isinstance(version, str):
        raise SystemExit("pyproject.toml is missing project.version")
    return version


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-ref", help="Git ref whose app version must be older")
    args = parser.parse_args()

    current = _project_version((ROOT / "pyproject.toml").read_text())
    init_text = (ROOT / "src/amplifier_app_tui/__init__.py").read_text()
    declared = re.search(r'^__version__\s*=\s*"([^"]+)"', init_text, re.MULTILINE)
    if declared is None or declared.group(1) != current:
        found = declared.group(1) if declared else "missing"
        raise SystemExit(f"__version__ is {found}; expected {current}")
    _version_tuple(current)

    if args.base_ref:
        raw = subprocess.run(
            ["git", "show", f"{args.base_ref}:pyproject.toml"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        base = _project_version(raw)
        if _version_tuple(current) <= _version_tuple(base):
            raise SystemExit(
                f"app release version must advance from {base}; current version is {current}"
            )
        print(f"Amplifier TUI release version advances {base} -> {current}.")
    else:
        print(f"Amplifier TUI release version {current} is consistent.")


if __name__ == "__main__":
    main()
