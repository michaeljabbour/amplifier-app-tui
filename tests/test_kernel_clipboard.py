"""Clipboard image capture + multimodal injection (kernel/clipboard.py)."""

from __future__ import annotations

import base64

import pytest

from amplifier_app_tui.kernel.clipboard import (
    ClipboardImageInjector,
    ImageAttachment,
    build_image_message,
    pasted_image_attachments,
)

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40


def test_pasted_image_attachments_raw_path(tmp_path) -> None:
    png = tmp_path / "shot.png"
    png.write_bytes(_PNG)
    (attachments,) = pasted_image_attachments(str(png))
    assert attachments.data == _PNG


def test_pasted_image_attachments_backslash_escaped_space(tmp_path) -> None:
    # A drop whose path contains a space arrives backslash-escaped (`\ `).
    png = tmp_path / "shot one.png"
    png.write_bytes(_PNG)
    (attachments,) = pasted_image_attachments(str(png).replace(" ", "\\ "))
    assert attachments.data == _PNG


def test_pasted_image_attachments_file_uri(tmp_path) -> None:
    png = tmp_path / "shot.png"
    png.write_bytes(_PNG)
    (attachments,) = pasted_image_attachments(png.as_uri())
    assert attachments.data == _PNG


def test_pasted_image_attachments_percent_encoded_file_uri(tmp_path) -> None:
    png = tmp_path / "shot one.png"
    png.write_bytes(_PNG)
    uri = png.as_uri().replace(" ", "%20")
    (attachments,) = pasted_image_attachments(uri)
    assert attachments.data == _PNG


def test_pasted_image_attachments_trailing_newline(tmp_path) -> None:
    # Some terminals append a trailing CR/LF to a drop payload.
    png = tmp_path / "shot.png"
    png.write_bytes(_PNG)
    (attachments,) = pasted_image_attachments(str(png) + "\n")
    assert attachments.data == _PNG


def test_pasted_image_attachments_unescaped_apostrophe_falls_back(tmp_path) -> None:
    # An unescaped apostrophe in a path makes shlex.split raise ValueError;
    # the backslash-unescape fallback must still resolve the single candidate.
    png = tmp_path / "o'brien.png"
    png.write_bytes(_PNG)
    (attachments,) = pasted_image_attachments(str(png))
    assert attachments.data == _PNG


def test_image_attachment_validates_content_type() -> None:
    ImageAttachment(data=_PNG, media_type="image/png")  # ok
    with pytest.raises(ValueError):
        ImageAttachment(data=_PNG, media_type="image/jpeg")  # bytes ≠ declared
    with pytest.raises(ValueError):
        ImageAttachment(data=b"", media_type="image/png")  # empty


def test_build_image_message_shape() -> None:
    msg = build_image_message([ImageAttachment(_PNG, "image/png")], text="see this")
    assert msg["role"] == "user"
    assert msg["content"][0] == {"type": "text", "text": "see this"}
    src = msg["content"][1]["source"]
    assert src == {
        "type": "base64",
        "media_type": "image/png",
        "data": base64.b64encode(_PNG).decode("ascii"),
    }
    assert msg["metadata"]["attachment_count"] == 1


class _FakeContext:
    def __init__(self, messages: list[dict]) -> None:
        self._messages = messages

    async def get_messages(self) -> list[dict]:
        return list(self._messages)

    async def set_messages(self, messages: list[dict]) -> None:
        self._messages = messages


@pytest.mark.asyncio
async def test_injector_rewrites_matching_user_message_to_multimodal() -> None:
    ctx = _FakeContext([{"role": "user", "content": "look at this"}])
    injector = ClipboardImageInjector(ctx)
    injector.prepare("look at this", (ImageAttachment(_PNG, "image/png"),))
    result = await injector.handle_provider_request("provider:request", {})
    assert result.action == "continue"
    rewritten = ctx._messages[-1]
    assert isinstance(rewritten["content"], list)
    assert rewritten["content"][1]["type"] == "image"
    assert injector._pending is None  # cleared after inject


@pytest.mark.asyncio
async def test_injector_noop_without_pending() -> None:
    ctx = _FakeContext([{"role": "user", "content": "hi"}])
    result = await ClipboardImageInjector(ctx).handle_provider_request("provider:request", {})
    assert result.action == "continue"
    assert ctx._messages[-1]["content"] == "hi"  # untouched
