"""Shared Amplifier Host registry and read-only discovery client.

The registry intentionally contains endpoint metadata and secret references,
never bearer tokens. Studio and TUI use the same ``~/.amplifier/hosts.yaml``
shape so selecting a machine does not become an app-specific decision.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import yaml

REGISTRY_VERSION = 1
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,62}$")


@dataclass(frozen=True)
class HostRecord:
    id: str
    name: str
    url: str
    token_ref: str
    default_project_root: str | None = None


def registry_path() -> Path:
    root = Path(os.environ.get("AMPLIFIER_HOME", Path.home() / ".amplifier")).expanduser()
    return root / "hosts.yaml"


def load_hosts(path: Path | None = None) -> tuple[HostRecord, ...]:
    target = path or registry_path()
    if not target.exists():
        return ()
    raw = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict) or raw.get("version") != REGISTRY_VERSION:
        raise ValueError(f"{target} must use Amplifier host registry version {REGISTRY_VERSION}")
    entries = raw.get("hosts", [])
    if not isinstance(entries, list):
        raise ValueError(f"{target} hosts must be a list")
    hosts = tuple(_parse_host(entry) for entry in entries)
    ids = [host.id for host in hosts]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{target} contains duplicate host ids")
    return hosts


def save_hosts(hosts: tuple[HostRecord, ...], path: Path | None = None) -> None:
    target = path or registry_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    document = {"version": REGISTRY_VERSION, "hosts": [asdict(host) for host in hosts]}
    # JSON is valid YAML and gives both Rust and Python clients one deterministic
    # representation without either app owning a YAML formatting dependency.
    encoded = json.dumps(document, indent=2, sort_keys=True) + "\n"
    descriptor, temporary = tempfile.mkstemp(prefix=".hosts-", suffix=".yaml", dir=target.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)


def add_host(
    *,
    host_id: str,
    name: str,
    url: str,
    token_ref: str | None = None,
    default_project_root: str | None = None,
    path: Path | None = None,
) -> HostRecord:
    record = _parse_host(
        {
            "id": host_id,
            "name": name,
            "url": url,
            "token_ref": token_ref or f"env:AMPLIFIER_HOST_TOKEN_{_env_suffix(host_id)}",
            "default_project_root": default_project_root,
        }
    )
    hosts = list(load_hosts(path))
    if any(host.id == record.id for host in hosts):
        raise ValueError(f"Amplifier host '{record.id}' already exists")
    hosts.append(record)
    hosts.sort(key=lambda host: (host.name.casefold(), host.id))
    save_hosts(tuple(hosts), path)
    return record


def remove_host(host_id: str, path: Path | None = None) -> bool:
    hosts = load_hosts(path)
    remaining = tuple(host for host in hosts if host.id != host_id)
    if len(remaining) == len(hosts):
        return False
    save_hosts(remaining, path)
    return True


def store_keychain_token(host_id: str, token: str, path: Path | None = None) -> HostRecord:
    if sys.platform != "darwin":
        raise ValueError("Keychain host tokens currently require macOS")
    token = token.strip()
    if not 32 <= len(token.encode()) <= 4096:
        raise ValueError("Host bearer tokens must contain 32 to 4096 bytes")
    host = find_host(host_id, path)
    result = subprocess.run(  # noqa: S603 - fixed executable and argument vector
        [
            "/usr/bin/security",
            "add-generic-password",
            "-U",
            "-s",
            "amplifier-host",
            "-a",
            host.id,
            "-w",
            token,
        ],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "macOS Keychain rejected the host token")
    updated = HostRecord(
        id=host.id,
        name=host.name,
        url=host.url,
        token_ref=f"keychain:{host.id}",
        default_project_root=host.default_project_root,
    )
    hosts = tuple(updated if item.id == host.id else item for item in load_hosts(path))
    save_hosts(hosts, path)
    return updated


def find_host(host_id: str, path: Path | None = None) -> HostRecord:
    for host in load_hosts(path):
        if host.id == host_id:
            return host
    raise ValueError(f"Unknown Amplifier host '{host_id}'")


def host_get(host: HostRecord, route: str, *, params: dict[str, str] | None = None) -> Any:
    token = resolve_token(host)
    response = httpx.get(
        f"{host.url}/v1/api/{route.lstrip('/')}",
        params=params,
        headers={"authorization": f"Bearer {token}"},
        timeout=10.0,
        follow_redirects=False,
    )
    try:
        value = response.json()
    except ValueError as error:
        raise RuntimeError(
            f"Amplifier host returned invalid JSON ({response.status_code})"
        ) from error
    if response.is_error:
        message = value.get("error") if isinstance(value, dict) else None
        raise RuntimeError(message or f"Amplifier host request failed ({response.status_code})")
    return value


def resolve_token(host: HostRecord) -> str:
    secret_label = host.token_ref
    if host.token_ref.startswith("env:"):
        variable = host.token_ref.removeprefix("env:")
        secret_label = variable
        token = os.environ.get(variable, "").strip()
        if not token:
            raise ValueError(f"Set {variable} to the bearer token for Amplifier host '{host.id}'")
    elif host.token_ref.startswith("keychain:") and sys.platform == "darwin":
        account = host.token_ref.removeprefix("keychain:")
        result = subprocess.run(  # noqa: S603 - fixed executable and argument vector
            [
                "/usr/bin/security",
                "find-generic-password",
                "-s",
                "amplifier-host",
                "-a",
                account,
                "-w",
            ],
            capture_output=True,
            check=False,
            text=True,
        )
        token = result.stdout.strip() if result.returncode == 0 else ""
        if not token:
            raise ValueError(f"No macOS Keychain token exists for Amplifier host '{host.id}'")
    else:
        raise ValueError(f"Token reference '{host.token_ref}' is not supported on this platform")
    if not token:
        raise ValueError(f"No bearer token is available for Amplifier host '{host.id}'")
    if not 32 <= len(token.encode()) <= 4096:
        raise ValueError(f"{secret_label} must contain 32 to 4096 bytes")
    return token


def _parse_host(raw: object) -> HostRecord:
    if not isinstance(raw, dict):
        raise ValueError("Every Amplifier host entry must be an object")
    host_id = str(raw.get("id", "")).strip().lower()
    name = str(raw.get("name", "")).strip()
    url = _normalize_url(str(raw.get("url", "")))
    token_ref = str(raw.get("token_ref", raw.get("tokenRef", ""))).strip()
    default_project_root = str(
        raw.get("default_project_root", raw.get("defaultProjectRoot", "")) or ""
    ).strip()
    if not _ID_RE.fullmatch(host_id):
        raise ValueError("Host ids use lowercase letters, numbers, dots, dashes, and underscores")
    if not name or len(name) > 80:
        raise ValueError("Host names must contain 1 to 80 characters")
    if not token_ref or len(token_ref) > 256:
        raise ValueError("Host token_ref must name a secret reference")
    return HostRecord(
        id=host_id,
        name=name,
        url=url,
        token_ref=token_ref,
        default_project_root=default_project_root or None,
    )


def _normalize_url(value: str) -> str:
    parsed = urlparse(value.strip())
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Host URL must be an http(s) origin without query or fragment")
    loopback = parsed.hostname.lower() in {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme != "https" and not loopback:
        raise ValueError("Remote Amplifier hosts require HTTPS; HTTP is allowed only on loopback")
    if parsed.username or parsed.password:
        raise ValueError("Host URL must not contain credentials")
    return value.strip().rstrip("/")


def _env_suffix(host_id: str) -> str:
    return re.sub(r"[^A-Z0-9]", "_", host_id.upper())
