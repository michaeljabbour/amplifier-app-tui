"""Repair configured provider packages after the app tool environment is replaced.

The verified-source updater creates a fresh isolated uv tool environment. User
settings, keys, and Amplifier source caches correctly survive that replacement,
but provider packages installed during onboarding do not. This app-owned seam
restores only configured provider module types (plus declared dependencies)
before a real session starts. It never changes settings or credentials.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path


PROVIDER_RUNTIME_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    # AzureOpenAIProvider extends OpenAIProvider, but the provider packages do
    # not declare that module relationship as an install dependency.
    "provider-azure-openai": ("provider-openai",),
}


@dataclass(frozen=True)
class ProviderRepairResult:
    """Outcome of one configured-provider environment repair."""

    missing: tuple[str, ...] = ()
    repaired: tuple[str, ...] = ()
    failures: tuple[tuple[str, str], ...] = ()

    @property
    def ok(self) -> bool:
        return not self.failures


class ProviderRepairError(RuntimeError):
    """A configured provider could not be restored into the app environment."""


def _provider_package_name(module_id: str) -> str:
    name = module_id
    for lead in ("amplifier-module-", "provider-", "amplifier-provider-"):
        if name.startswith(lead):
            name = name[len(lead) :]
    return f"amplifier_module_provider_{name.replace('-', '_')}"


def provider_module_available(module_id: str) -> bool:
    """Whether the provider's own top-level package is importable.

    A spec check keeps a missing third-party SDK distinct from a provider
    package removed with the old tool environment. Foundation's normal prepare
    pass owns the former; this repair owns the latter.
    """
    try:
        return importlib.util.find_spec(_provider_package_name(module_id)) is not None
    except (ImportError, AttributeError, ValueError):
        return False


def missing_configured_provider_modules(
    project_dir: Path | None = None,
    amplifier_home: Path | None = None,
) -> tuple[str, ...]:
    """Configured provider module types absent from this Python environment."""
    from ..kernel import setup

    seen: set[str] = set()
    missing: list[str] = []
    for provider in setup.configured_providers(project_dir, amplifier_home):
        module_id = provider.module_id
        if not module_id or module_id in seen:
            continue
        seen.add(module_id)
        if not provider_module_available(module_id):
            missing.append(module_id)
    return tuple(missing)


async def repair_missing_configured_providers(
    project_dir: Path | None = None,
    amplifier_home: Path | None = None,
) -> ProviderRepairResult:
    """Restore configured providers without rewriting settings or working installs."""
    from ..kernel import setup

    missing = missing_configured_provider_modules(project_dir, amplifier_home)
    if not missing:
        return ProviderRepairResult()

    sources = setup.effective_provider_sources(project_dir, amplifier_home)
    ordered: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(module_id: str) -> None:
        if module_id in visited or provider_module_available(module_id):
            return
        if module_id in visiting:
            return
        visiting.add(module_id)
        for dependency in PROVIDER_RUNTIME_DEPENDENCIES.get(module_id, ()):
            visit(dependency)
        visiting.remove(module_id)
        visited.add(module_id)
        ordered.append(module_id)

    for module_id in missing:
        visit(module_id)

    repaired: list[str] = []
    failures: list[tuple[str, str]] = []
    failed_ids: set[str] = set()
    for module_id in ordered:
        failed_dependency = next(
            (
                dependency
                for dependency in PROVIDER_RUNTIME_DEPENDENCIES.get(module_id, ())
                if dependency in failed_ids
            ),
            None,
        )
        if failed_dependency is not None:
            failures.append((module_id, f"dependency {failed_dependency} could not be restored"))
            failed_ids.add(module_id)
            continue

        source_uri = sources.get(module_id)
        if not source_uri:
            failures.append((module_id, "no provider source is configured"))
            failed_ids.add(module_id)
            continue

        ok, detail = await setup.install_provider_module(
            module_id,
            source_uri,
            amplifier_home=amplifier_home,
        )
        if ok:
            # This package was absent when find_spec first populated the
            # FileFinder cache. A freshly installed distribution is visible
            # to a new process but can remain falsely missing in this one
            # unless import caches are invalidated before verification.
            importlib.invalidate_caches()
        if ok and provider_module_available(module_id):
            repaired.append(module_id)
            continue
        failures.append((module_id, detail or "installed package is not importable"))
        failed_ids.add(module_id)

    return ProviderRepairResult(
        missing=missing,
        repaired=tuple(repaired),
        failures=tuple(failures),
    )


def repair_error(result: ProviderRepairResult) -> ProviderRepairError:
    """Build a secret-safe actionable error for a failed repair."""
    failed = ", ".join(module_id for module_id, _detail in result.failures)
    return ProviderRepairError(
        f"provider repair failed for {failed}; retry amplifier-tui, then inspect "
        "the configured provider source"
    )


__all__ = [
    "PROVIDER_RUNTIME_DEPENDENCIES",
    "ProviderRepairError",
    "ProviderRepairResult",
    "missing_configured_provider_modules",
    "provider_module_available",
    "repair_error",
    "repair_missing_configured_providers",
]
