from pathlib import Path

import pytest
import yaml

from amplifier_app_tui.remote_hosts import (
    add_host,
    find_host,
    load_hosts,
    remove_host,
    resolve_token,
)


def test_registry_is_atomic_redacted_and_shared_yaml(tmp_path: Path) -> None:
    path = tmp_path / "hosts.yaml"
    host = add_host(
        host_id="sam-lab",
        name="SAM Lab",
        url="https://sam.example.test/",
        token_ref="env:SAM_HOST_TOKEN",
        path=path,
    )

    assert host.url == "https://sam.example.test"
    assert find_host("sam-lab", path) == host
    document = yaml.safe_load(path.read_text())
    assert document["version"] == 1
    assert document["hosts"][0]["token_ref"] == "env:SAM_HOST_TOKEN"
    assert "secret-value" not in path.read_text()
    assert path.stat().st_mode & 0o777 == 0o600

    assert remove_host("sam-lab", path) is True
    assert remove_host("sam-lab", path) is False
    assert load_hosts(path) == ()


def test_registry_requires_https_off_loopback(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="require HTTPS"):
        add_host(host_id="bad", name="Bad", url="http://sam.example.test", path=tmp_path / "h")
    assert (
        add_host(
            host_id="local",
            name="Local",
            url="http://127.0.0.1:4317",
            path=tmp_path / "local.yaml",
        ).url
        == "http://127.0.0.1:4317"
    )


def test_token_is_resolved_from_reference_not_registry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    host = add_host(
        host_id="forge",
        name="Forge",
        url="https://forge.example.test",
        token_ref="env:FORGE_HOST_TOKEN",
        path=tmp_path / "hosts.yaml",
    )
    monkeypatch.setenv("FORGE_HOST_TOKEN", "a" * 32)
    assert resolve_token(host) == "a" * 32
