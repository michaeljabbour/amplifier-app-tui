"""Full-app image attachment flows."""

from __future__ import annotations

import pytest
from textual import events

from amplifier_app_tui.ui.app import TuiApp
from amplifier_app_tui.ui.composer import Composer
from amplifier_app_tui.ui.demo_wiring import DemoRuntimeAdapter

from .test_flow_helpers import wait_for


@pytest.mark.asyncio
async def test_dropped_image_path_reaches_the_transcript(tmp_path) -> None:
    """A terminal file drop becomes an attachment and visible user turn.

    Terminal emulators deliver a dropped file as a bracketed paste of its
    path. Exercise that event through the full app, not only the isolated
    composer, so focus, submit routing, and the user-line echo stay covered.
    """

    png = tmp_path / "shot one.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 40)
    app = TuiApp(DemoRuntimeAdapter(instant=True))

    async with app.run_test(size=(110, 40)) as pilot:
        assert await wait_for(
            pilot,
            lambda: any(block.kind == "session_banner" for block in app.transcript.blocks),
        )
        composer = app.query_one("#composer", Composer)
        assert app.focused is composer._input

        composer._input.post_message(events.Paste(str(png)))
        await pilot.pause()
        assert composer.text == "[Image #1] "

        await pilot.press("enter")
        assert await wait_for(
            pilot,
            lambda: any(
                block.kind == "user_line" and getattr(block, "text", "") == "[Image #1]"
                for block in app.transcript.blocks
            ),
        )
