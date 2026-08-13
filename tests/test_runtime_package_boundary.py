"""Regression gates for the neutral runtime extraction boundary."""

from __future__ import annotations

from importlib.util import find_spec
from pathlib import Path

import amplifier_runtime
import amplifier_app_tui.kernel as tui_kernel
import amplifier_app_tui.model as tui_model

TUI_PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "src" / "amplifier_app_tui"
RUNTIME_PACKAGE_ROOT = Path(amplifier_runtime.__file__).resolve().parent


def _module_name(layer: str, relative: Path) -> str:
    suffix = (
        relative.parent.parts if relative.name == "__init__.py" else relative.with_suffix("").parts
    )
    return ".".join(("amplifier_app_tui", layer, *suffix))


def test_tui_package_paths_exclude_local_runtime_fallbacks() -> None:
    """TUI kernel/model imports must have no local implementation fallback."""
    assert tuple(Path(item).resolve() for item in tui_kernel.__path__) == (
        RUNTIME_PACKAGE_ROOT / "kernel",
    )
    assert tuple(Path(item).resolve() for item in tui_model.__path__) == (
        RUNTIME_PACKAGE_ROOT / "model",
    )


def test_every_tui_runtime_module_resolves_to_amplifier_runtime() -> None:
    """Every formerly local kernel/model module must resolve to runtime source."""
    for layer in ("kernel", "model"):
        local_root = TUI_PACKAGE_ROOT / layer
        runtime_root = RUNTIME_PACKAGE_ROOT / layer
        local_files = {path.relative_to(local_root) for path in local_root.rglob("*.py")}
        runtime_files = {path.relative_to(runtime_root) for path in runtime_root.rglob("*.py")}

        assert local_files == runtime_files

        for relative in sorted(local_files - {Path("__init__.py")}):
            module_name = _module_name(layer, relative)
            spec = find_spec(module_name)
            assert spec is not None and spec.origin is not None, module_name
            module_path = Path(spec.origin).resolve()
            assert module_path.is_relative_to(runtime_root), (
                f"{module_name} resolves to {module_path}, not {runtime_root}"
            )
