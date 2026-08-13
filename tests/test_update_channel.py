from __future__ import annotations

from types import SimpleNamespace

import httpx

from amplifier_app_tui import update_channel


def test_target_release_version_reads_immutable_project_metadata(monkeypatch) -> None:
    commit = "a" * 40
    seen: list[tuple[str, float]] = []

    def fake_get(url: str, timeout: float):
        seen.append((url, timeout))
        return SimpleNamespace(
            text='[project]\nname = "amplifier-app-tui"\nversion = "0.1.2"\n',
            raise_for_status=lambda: None,
        )

    monkeypatch.setattr(httpx, "get", fake_get)

    assert update_channel.target_release_version(commit) == "0.1.2"
    assert seen == [
        (
            "https://raw.githubusercontent.com/michaeljabbour/amplifier-app-tui/"
            f"{commit}/pyproject.toml",
            5.0,
        )
    ]


def test_target_release_version_degrades_when_metadata_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: (_ for _ in ()).throw(OSError()))

    assert update_channel.target_release_version("b" * 40) is None
    assert update_channel.target_release_version("not-a-commit") is None
