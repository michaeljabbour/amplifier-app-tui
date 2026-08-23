#!/usr/bin/env python3
"""Fail visibly when app-cli main moves beyond the last reviewed baseline.

This is a read-only drift alarm, not a claim that matching commits imply
capability parity. The scheduled workflow opens/refreshes the normal upstream
drift issue when the donor SHA changes; a human or agent must then perform and
record the actual capability review before updating the baseline.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "docs" / "audits" / "app-cli-baseline.json"


def _sha(value: Any, label: str) -> str:
    text = str(value or "")
    if len(text) != 40 or any(character not in "0123456789abcdef" for character in text):
        raise ValueError(f"{label} must be a full lowercase commit SHA")
    return text


def load_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("unsupported app-cli parity baseline schema")
    repository = str(payload.get("donor_repository") or "")
    if not repository.startswith("https://github.com/") or "@" in repository:
        raise ValueError("donor_repository must be a credential-free GitHub HTTPS URL")
    _sha(payload.get("audited_commit"), "audited_commit")
    return payload


def remote_main(repository: str, *, timeout: float = 20.0) -> str:
    result = subprocess.run(
        ["git", "ls-remote", repository, "refs/heads/main"],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    fields = result.stdout.split()
    if result.returncode != 0 or len(fields) != 2 or fields[1] != "refs/heads/main":
        detail = result.stderr.strip() or "main ref not returned"
        raise RuntimeError(f"could not resolve donor main: {detail}")
    return _sha(fields[0], "remote main")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--head",
        default=None,
        help="compare an explicit full SHA instead of contacting GitHub (tests/offline review)",
    )
    args = parser.parse_args(argv)
    try:
        manifest = load_manifest(args.manifest)
        audited = _sha(manifest["audited_commit"], "audited_commit")
        current = (
            _sha(args.head, "head") if args.head else remote_main(manifest["donor_repository"])
        )
    except (
        OSError,
        ValueError,
        RuntimeError,
        subprocess.SubprocessError,
        json.JSONDecodeError,
    ) as error:
        print(f"ERROR: {error}")
        return 1

    print(f"app-cli audited {audited[:8]} · current {current[:8]}")
    if current == audited:
        print("app-cli parity baseline is current")
        return 0
    print(
        "APP-CLI PARITY REVIEW REQUIRED: donor main changed; review the commit range, "
        "record a new audit pass, then update the baseline"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
