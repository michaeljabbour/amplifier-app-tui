"""Compatibility import surface for the neutral Amplifier runtime.

Runtime behavior is owned by the sibling ``amplifier-runtime`` distribution.
Using only its kernel source directory for this package's search path preserves
the established ``amplifier_app_tui.kernel.*`` imports while ensuring they
execute runtime-owned files. The duplicate local modules are intentionally
disabled and cannot act as a silent fallback.
"""

from __future__ import annotations

from importlib.util import find_spec


def _use_runtime_kernel() -> None:
    spec = find_spec("amplifier_runtime.kernel")
    locations = list(spec.submodule_search_locations or ()) if spec is not None else []
    if not locations:
        raise ImportError("amplifier-runtime is required; run `uv sync` in amplifier-app-tui")
    # Do not append this package's original local path. That fallback would
    # reactivate the duplicate TUI implementation when a runtime file is absent.
    __path__[:] = locations


_use_runtime_kernel()

del _use_runtime_kernel
