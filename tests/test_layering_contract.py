"""Guard: the ADR-0007 layering contract is enforced by a stdlib-AST test.

ADR-0007 §Layering names import-linter as the enforcement mechanism, but no
``[tool.importlinter]`` contract or dependency ever shipped (see the ADR's
2026-08-09 status note). This test makes the contract real with zero new
dependencies, matching the precedent of ``test_no_floating_dependencies.py``:
a stdlib :mod:`ast` walk over every ``*.py`` under the layered packages.

Rules (verified against ``docs/ARCHITECTURE.md`` §1 and the current tree):

- ``kernel/**`` never imports ``textual`` / ``textual.*`` — at any depth,
  including function-level and ``try:``-guarded imports.
- ``model/**`` additionally never imports ``amplifier_*`` packages
  (``amplifier_core``, ``amplifier_foundation``, …). The app's own package
  ``amplifier_app_tui`` is exempt — it is the tree being layered.
- ``commands/**`` follows the same two bans and additionally never imports
  ``amplifier_app_tui.kernel*`` (directly or via relative ``..kernel`` /
  ``from .. import kernel``). Per ARCHITECTURE.md §6.2 command logic is pure;
  today's modules legitimately import stdlib, third-party (``pydantic``),
  ``model/``, and top-level package modules (``product``, ``install_contract``)
  — only Textual, amplifier platform packages, and ``kernel/`` are banned.

Every check resolves relative imports against the importing file's package so
``from .. import kernel`` is judged by its absolute target. One violation
names its file precisely: each source file is its own parametrized case, and
the violation text carries ``file:line``.

Also pinned here: ``ui/app.py``'s ratchet budget (ADR-0007 prescribes <500
lines; WS1 of ``docs/plans/2026-08-09-settings-ux-and-hygiene-campaign.md``
extracts controllers toward it). The budget may only move DOWN.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
APP_ROOT = SRC_ROOT / "amplifier_app_tui"

# ui/app.py ratchet: current size after WS1 step 1 (StripManager, 2026-08-09).
# WS1 (docs/plans/2026-08-09-settings-ux-and-hygiene-campaign.md) extracts
# controllers and ratchets this DOWN toward ADR-0007's <500-line budget.
# Never raise it — shrink the file or split it instead.
APP_PY_LINE_BUDGET = 2566

# The app's own package is layered, not banned: only EXTERNAL amplifier
# platform packages (amplifier_core, amplifier_foundation, amplifier_module_*)
# are forbidden outside kernel/.
_OWN_PACKAGE = "amplifier_app_tui"


def _module_parts(path: Path) -> tuple[str, ...]:
    """Dotted module path of *path* relative to ``src/``, as a tuple."""
    return path.relative_to(SRC_ROOT).with_suffix("").parts


def _resolve_from(from_package: tuple[str, ...], level: int, module: str | None) -> str:
    """Resolve an ``ImportFrom`` target to its absolute dotted module.

    ``from_package`` is the importing file's *package* (module parts minus the
    file itself); ``level`` counts the leading dots (1 = the package itself).
    """
    base = from_package[: len(from_package) - (level - 1)] if level else ()
    tail = tuple(module.split(".")) if module else ()
    return ".".join(base + tail)


def _iter_imports(source: str, module_parts: tuple[str, ...]):
    """Yield ``(lineno, absolute_dotted_name)`` for every import in *source*.

    ``ast.walk`` reaches nested scopes, so conditional/function-level imports
    are judged exactly like top-level ones. For ``from X import a, b`` both
    ``X`` and each ``X.a`` / ``X.b`` are yielded, so a banned *module* imported
    via ``from .. import kernel`` cannot slip through as an alias name.
    """
    from_package = module_parts[:-1]
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield (getattr(alias, "lineno", node.lineno), alias.name)
        elif isinstance(node, ast.ImportFrom):
            resolved = _resolve_from(from_package, node.level, node.module)
            yield (node.lineno, resolved)
            for alias in node.names:
                dotted = f"{resolved}.{alias.name}" if resolved else alias.name
                yield (getattr(alias, "lineno", node.lineno), dotted)


def _is_external_amplifier(dotted: str) -> bool:
    top = dotted.split(".")[0]
    return top.startswith("amplifier_") and top != _OWN_PACKAGE


def _is_kernel_import(dotted: str) -> bool:
    return dotted == f"{_OWN_PACKAGE}.kernel" or dotted.startswith(f"{_OWN_PACKAGE}.kernel.")


def layering_violations(source: str, module_parts: tuple[str, ...]) -> list[str]:
    """``["line N: ...", ...]`` for every import breaking *module_parts'* layer
    rules. The layer is the package directly under ``amplifier_app_tui``."""
    layer = module_parts[1] if len(module_parts) > 1 else ""
    if layer not in {"kernel", "model", "commands"}:
        return []
    violations: list[str] = []
    for lineno, dotted in _iter_imports(source, module_parts):
        top = dotted.split(".")[0]
        if top == "textual":
            violations.append(f"line {lineno}: {layer}/ must never import `textual` ({dotted})")
        if layer in {"model", "commands"} and _is_external_amplifier(dotted):
            violations.append(
                f"line {lineno}: {layer}/ must never import amplifier platform "
                f"packages ({dotted}) — only kernel/ may"
            )
        if layer == "commands" and _is_kernel_import(dotted):
            violations.append(
                f"line {lineno}: commands/ must not import kernel/ "
                f"({dotted}) — command logic stays pure (model/ + stdlib + "
                "third-party; ARCHITECTURE.md §6.2)"
            )
    return violations


def _layer_files(layer: str) -> list[Path]:
    layer_dir = APP_ROOT / layer
    return sorted(p for p in layer_dir.rglob("*.py") if "__pycache__" not in p.parts)


@pytest.mark.parametrize(
    "path",
    _layer_files("kernel"),
    ids=lambda p: str(p.relative_to(REPO_ROOT)),
)
def test_kernel_never_imports_textual(path: Path) -> None:
    violations = layering_violations(path.read_text(encoding="utf-8"), _module_parts(path))
    assert not violations, (
        f"{path.relative_to(REPO_ROOT)}: layering violation(s): {violations!r} — "
        "kernel/ is the amplifier adapter; nothing Textual-specific may leak into "
        "it (ADR-0007, ARCHITECTURE.md §1 invariant 2)"
    )


@pytest.mark.parametrize(
    "path",
    _layer_files("model"),
    ids=lambda p: str(p.relative_to(REPO_ROOT)),
)
def test_model_imports_neither_textual_nor_amplifier(path: Path) -> None:
    violations = layering_violations(path.read_text(encoding="utf-8"), _module_parts(path))
    assert not violations, (
        f"{path.relative_to(REPO_ROOT)}: layering violation(s): {violations!r} — "
        "model/ is the pure domain layer: no Textual, no amplifier-core/foundation "
        "(ADR-0007, ARCHITECTURE.md §1 invariant 2)"
    )


@pytest.mark.parametrize(
    "path",
    _layer_files("commands"),
    ids=lambda p: str(p.relative_to(REPO_ROOT)),
)
def test_commands_stay_pure_no_textual_amplifier_or_kernel(path: Path) -> None:
    violations = layering_violations(path.read_text(encoding="utf-8"), _module_parts(path))
    assert not violations, (
        f"{path.relative_to(REPO_ROOT)}: layering violation(s): {violations!r} — "
        "commands/ holds pure command logic: stdlib, third-party (e.g. pydantic), "
        "model/, and top-level package modules are fine; Textual, amplifier_*, and "
        "kernel/ are not (ARCHITECTURE.md §6.2: tests drive a FakeCommandContext, "
        "no Textual/kernel involved)"
    )


def test_app_py_within_line_budget() -> None:
    """Ratchet, not a target: WS1 ratchets APP_PY_LINE_BUDGET down per
    extraction PR; a file larger than the constant fails here."""
    app_py = APP_ROOT / "ui" / "app.py"
    lines = len(app_py.read_text(encoding="utf-8").splitlines())
    assert lines <= APP_PY_LINE_BUDGET, (
        f"ui/app.py grew to {lines} lines (budget {APP_PY_LINE_BUDGET}). "
        "ADR-0007 prescribes a <500-line composition root; new logic belongs in "
        "app_support.py / a widget / a WS1 controller — never in app.py. Lower the "
        "budget when extraction lands; do not raise it."
    )


# -- self-bite: the walker must catch violations, not just pass on clean code --

_KERNEL_PARTS = ("amplifier_app_tui", "kernel", "synthetic")
_MODEL_PARTS = ("amplifier_app_tui", "model", "synthetic")
_COMMANDS_PARTS = ("amplifier_app_tui", "commands", "synthetic")


def test_walker_detects_textual_in_kernel() -> None:
    source = "import textual\n\ndef f():\n    from textual.app import App\n"
    assert layering_violations(source, _KERNEL_PARTS)


def test_walker_detects_amplifier_and_textual_in_model() -> None:
    kernel_ok = layering_violations("from amplifier_core import HookResult\n", _KERNEL_PARTS)
    assert kernel_ok == []  # kernel legitimately imports amplifier-core
    assert layering_violations("from amplifier_core import HookResult\n", _MODEL_PARTS)
    assert layering_violations("import textual.widgets\n", _MODEL_PARTS)


def test_walker_detects_kernel_import_in_commands_even_when_relative() -> None:
    assert layering_violations("from ..kernel import demo\n", _COMMANDS_PARTS)
    assert layering_violations("from .. import kernel\n", _COMMANDS_PARTS)
    assert layering_violations("import amplifier_app_tui.kernel.demo\n", _COMMANDS_PARTS)
    assert layering_violations("import textual\n", _COMMANDS_PARTS)
    assert layering_violations("import amplifier_foundation\n", _COMMANDS_PARTS)
    # ...while today's real patterns stay clean:
    clean = (
        "import subprocess\n"
        "from pathlib import Path\n"
        "from pydantic import BaseModel\n"
        "from ..model.blocks import DoctorBlock\n"
        "from ..model.trust import (\n    DenialLog,\n)\n"
        "from ..product import DISPLAY_NAME\n"
        "from .registry import CommandContext\n"
    )
    assert layering_violations(clean, _COMMANDS_PARTS) == []
    # ...and non-layered packages (ui/, cli/, main.py) are out of the walker's scope:
    assert layering_violations("import textual\n", ("amplifier_app_tui", "ui", "app")) == []
