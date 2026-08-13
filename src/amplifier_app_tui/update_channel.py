"""TUI release-channel metadata.

The shared runtime owns sessions; this client module owns the TUI's product
version and GitHub source channel. Network failures are deliberately soft so a
verified commit-based update remains available when release metadata cannot be
read.
"""

from __future__ import annotations

import re
import tomllib

from .install_contract import APP_REPO_URL

_GITHUB_REPO_RE = re.compile(r"^https://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$")


def target_release_version(commit: str, timeout: float = 5.0) -> str | None:
    """Return the package version declared at an immutable source commit.

    Only the configured GitHub repository is consulted. Any network, parsing,
    or metadata error returns ``None`` so callers can retain the source-revision
    fallback without claiming a version they did not verify.
    """
    match = _GITHUB_REPO_RE.fullmatch(APP_REPO_URL)
    if match is None or not re.fullmatch(r"[0-9a-fA-F]{40}", commit):
        return None
    owner, repository = match.groups()
    url = f"https://raw.githubusercontent.com/{owner}/{repository}/{commit}/pyproject.toml"
    try:
        import httpx

        response = httpx.get(url, timeout=timeout)
        response.raise_for_status()
        project = tomllib.loads(response.text).get("project", {})
        version = project.get("version") if isinstance(project, dict) else None
        return str(version) if version else None
    except Exception:  # noqa: BLE001 - update checks degrade to the commit channel
        return None


__all__ = ["target_release_version"]
