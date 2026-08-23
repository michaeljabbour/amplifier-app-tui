"""Read-only diagnostics for configured providers outside a live session."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ConfiguredProviderDiagnostic:
    """One configured provider's bounded model-catalog probe."""

    name: str
    module_id: str
    model: str
    ok: bool
    elapsed_s: float
    models: tuple[Any, ...] = ()
    error: str = ""


def _resolved_config(config: dict[str, Any], keys: dict[str, str]) -> dict[str, Any]:
    """Resolve exact ``${VAR}`` values without mutating settings or ``os.environ``."""

    def resolve(value: Any) -> Any:
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            name = value[2:-1]
            return os.environ.get(name, keys.get(name, value))
        if isinstance(value, dict):
            return {key: resolve(item) for key, item in value.items()}
        if isinstance(value, list):
            return [resolve(item) for item in value]
        return value

    return {key: resolve(value) for key, value in config.items()}


async def inspect_configured_provider(
    name: str = "",
    *,
    timeout: float = 15.0,
    project_dir: Path | None = None,
    amplifier_home: Path | None = None,
) -> ConfiguredProviderDiagnostic:
    """Probe one saved provider, defaulting to the current primary."""
    from ..kernel import setup
    from . import provider_repair

    repair = await provider_repair.repair_missing_configured_providers(project_dir, amplifier_home)
    if repair.failures:
        failed = ", ".join(module_id for module_id, _detail in repair.failures)
        return ConfiguredProviderDiagnostic(
            name=name,
            module_id="",
            model="",
            ok=False,
            elapsed_s=0.0,
            error=f"provider package repair failed for {failed}",
        )

    configured = setup.configured_providers(project_dir, amplifier_home)
    target = (
        setup.find_configured_provider(name, project_dir=project_dir, amplifier_home=amplifier_home)
        if name.strip()
        else next((entry for entry in configured if entry.primary), None)
    )
    if target is None:
        available = ", ".join(entry.name for entry in configured) if configured else "(none)"
        error = (
            f"provider {name!r} is not configured · available: {available}"
            if name.strip()
            else "no saved provider is configured"
        )
        return ConfiguredProviderDiagnostic(
            name=name,
            module_id="",
            model="",
            ok=False,
            elapsed_s=0.0,
            error=error,
        )

    keys = setup.read_keys(setup.keys_file(amplifier_home))
    config = _resolved_config(target.config, keys)
    started = time.monotonic()
    catalog = await setup.list_provider_models(target.module_id, config, timeout=timeout)
    elapsed = time.monotonic() - started
    return ConfiguredProviderDiagnostic(
        name=target.name,
        module_id=target.module_id,
        model=target.model or "",
        ok=not bool(catalog.error),
        elapsed_s=elapsed,
        models=tuple(catalog.models),
        error=catalog.error or "",
    )


__all__ = ["ConfiguredProviderDiagnostic", "inspect_configured_provider"]
