"""Compatibility import surface for runtime-owned semantic state.

The neutral runtime owns the protocol-safe model types shared by clients. This
package uses only that source directory so existing TUI imports keep their
module identity while loading the runtime implementation. The duplicate local
modules are intentionally disabled and cannot act as a silent fallback.
"""

from __future__ import annotations

from importlib.util import find_spec


def _use_runtime_model() -> None:
    spec = find_spec("amplifier_runtime.model")
    locations = list(spec.submodule_search_locations or ()) if spec is not None else []
    if not locations:
        raise ImportError("amplifier-runtime is required; run `uv sync` in amplifier-app-tui")
    # Do not append this package's original local path. That fallback would
    # reactivate the duplicate TUI implementation when a runtime file is absent.
    __path__[:] = locations


_use_runtime_model()

del _use_runtime_model
