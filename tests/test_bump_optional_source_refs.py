"""Offline contract for the optional-source pin maintenance helper."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_script() -> ModuleType:
    path = REPO_ROOT / "scripts" / "bump_optional_source_refs.py"
    spec = importlib.util.spec_from_file_location("bump_optional_source_refs", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


script = _load_script()


def test_source_url_and_ref_requires_a_full_sha() -> None:
    sha = "a" * 40
    assert script.source_url_and_ref(f"git+https://example.invalid/repo@{sha}#subdirectory=x") == (
        "https://example.invalid/repo",
        sha,
    )
    with pytest.raises(ValueError, match="not pinned"):
        script.source_url_and_ref("git+https://example.invalid/repo@main")


def test_rewritten_files_replaces_each_pin_once_without_writing(tmp_path: Path) -> None:
    source = tmp_path / "pins.py"
    old_a, old_b = "a" * 40, "b" * 40
    source.write_text(f'A = "repo@{old_a}"\nB = "repo@{old_b}"\n', encoding="utf-8")
    pins = (
        script.SourcePin("a", f"git+https://example.invalid/a@{old_a}", source),
        script.SourcePin("b", f"git+https://example.invalid/b@{old_b}", source),
    )

    result = script.rewritten_files(pins, {"a": "c" * 40, "b": "d" * 40})

    assert result[source] == f'A = "repo@{"c" * 40}"\nB = "repo@{"d" * 40}"\n'
    assert old_a in source.read_text(encoding="utf-8")  # pure until caller commits the rewrite


def test_rewritten_files_fails_closed_when_a_pin_is_ambiguous(tmp_path: Path) -> None:
    source = tmp_path / "pins.py"
    old = "a" * 40
    source.write_text(f'ONE = "{old}"\nTWO = "{old}"\n', encoding="utf-8")
    pin = script.SourcePin("one", f"git+https://example.invalid/one@{old}", source)

    with pytest.raises(RuntimeError, match="exactly one"):
        script.rewritten_files((pin,), {"one": "b" * 40})


def test_pins_are_read_from_the_file_they_would_be_written_to() -> None:
    """The pin's file must be the one the value was actually READ from.

    ``amplifier_app_tui.kernel`` is a ``__path__`` shim that rewrites its search
    path to the installed ``amplifier-runtime`` distribution.  This script used
    to read a pin through that shim -- resolving to site-packages -- and then
    write ``src/amplifier_app_tui/kernel/config.py``, a file nothing loads.
    ``--write`` therefore rewrote a corpse and the next ``--check`` re-read the
    runtime, saw the old value, and reported drift again.  Forever.
    """
    for pin in script.current_pins():
        assert pin.source_file == script._declaring_file(
            script._config_module if pin.name == "routing-matrix" else script._setup_module
        )


def test_guard_refuses_to_rewrite_a_pin_this_repo_no_longer_declares() -> None:
    foreign = script.SourcePin(
        "routing-matrix",
        f"git+https://example.invalid/repo@{'a' * 40}",
        Path("/somewhere/site-packages/amplifier_runtime/kernel/config.py"),
    )

    with pytest.raises(RuntimeError, match="no longer declared by this repo"):
        script._assert_app_owned((foreign,))


def test_guard_accepts_a_pin_declared_under_this_repos_src() -> None:
    owned = script.SourcePin(
        "routing-matrix",
        f"git+https://example.invalid/repo@{'a' * 40}",
        script.APP_SOURCE_ROOT / "amplifier_app_tui" / "kernel" / "config.py",
    )

    script._assert_app_owned((owned,))  # must not raise


def test_the_ownership_test_is_src_not_repo_root() -> None:
    """The virtualenv lives INSIDE the checkout, so ``REPO_ROOT`` cannot decide this.

    A site-packages path is happily ``relative_to`` the repo root, which would
    pass exactly the files the guard exists to reject.  This pins the boundary
    at ``src/`` so a future simplification cannot quietly reintroduce the bug.
    """
    venv_file = REPO_ROOT / ".venv" / "lib" / "site-packages" / "amplifier_runtime" / "x.py"

    assert venv_file.is_relative_to(REPO_ROOT), "precondition: .venv is inside the checkout"
    assert not venv_file.is_relative_to(script.APP_SOURCE_ROOT)
