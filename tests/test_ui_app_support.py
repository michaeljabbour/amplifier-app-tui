"""Pure interaction-state helpers kept outside the composition root."""

from __future__ import annotations

from amplifier_app_tui.ui.app_support import (
    ATTENTION_MIN_TURN_SECONDS,
    EscSequence,
    attention_bell_needed,
    native_modes_segments,
)
from amplifier_app_tui.ui.keymap import ESC_BACKTRACK_WINDOW_SECONDS


def test_native_modes_use_full_terminal_width() -> None:
    long_desc = "Amplifier-way conformance audit of the working repo across every module today"
    catalog = {"modes": [{"name": "audit", "description": long_desc, "source": "conformance"}]}
    text = "".join(s.text for s in native_modes_segments(catalog, term_width=200))
    wide = next(line for line in text.splitlines() if "Amplifier-way" in line)
    narrow_text = "".join(s.text for s in native_modes_segments(catalog, term_width=60))
    narrow = next(line for line in narrow_text.splitlines() if "Amplifier-way" in line)
    # Wider terminal → longer description line (no fixed 90-col cap), and the
    # narrow render truncates with an ellipsis to fit.
    assert len(wide) > len(narrow)
    assert "…" in narrow and "…" not in wide


def test_native_modes_mark_the_active_set() -> None:
    catalog = {
        "modes": [
            {"name": "audit", "description": "conformance audit", "source": "conformance"},
            {"name": "careful", "description": "extra caution", "source": "modes"},
        ]
    }
    text = "".join(s.text for s in native_modes_segments(catalog, active=("audit",)))
    audit_line = next(line for line in text.splitlines() if "audit" in line)
    careful_line = next(line for line in text.splitlines() if "careful" in line)
    assert "◆" in audit_line  # active mode is marked
    assert "◆" not in careful_line  # inactive mode is not


def test_native_modes_mark_hidden_entries_and_add_the_footnote() -> None:
    """CLI parity (``amplifier_app_cli.main._list_modes``): a hidden mode
    is still listed, marked ``(hidden)``, with a footnote explaining it."""
    catalog = {
        "modes": [
            {
                "name": "evaluation",
                "description": "score a design",
                "source": "modes",
                "advertised": True,
            },
            {
                "name": "mode-design",
                "description": "author a new mode",
                "source": "modes",
                "advertised": False,
            },
        ]
    }
    text = "".join(s.text for s in native_modes_segments(catalog))
    lines = text.splitlines()
    hidden_line = next(line for line in lines if "mode-design" in line)
    visible_line = next(line for line in lines if "evaluation" in line)
    assert "(hidden)" in hidden_line
    assert "(hidden)" not in visible_line
    assert any(
        "(hidden) = available only via slash command, not advertised to agents." in line
        for line in lines
    )


def test_native_modes_no_footnote_when_nothing_is_hidden() -> None:
    catalog = {
        "modes": [{"name": "plan", "description": "d", "source": "modes", "advertised": True}]
    }
    text = "".join(s.text for s in native_modes_segments(catalog))
    assert "(hidden)" not in text


def test_native_modes_missing_advertised_key_renders_unchanged() -> None:
    """Pre-existing tool-shaped payloads (no ``advertised`` key at all)
    default to advertised=True and render exactly as before."""
    catalog = {"modes": [{"name": "plan", "description": "read-only planning", "source": "modes"}]}
    text = "".join(s.text for s in native_modes_segments(catalog))
    assert "(hidden)" not in text
    assert "plan" in text


def test_native_modes_hidden_marker_widens_the_name_column() -> None:
    """The ``(hidden)`` suffix must not clip the description column for
    the SHORTER, non-hidden row sharing the same source group."""
    catalog = {
        "modes": [
            {"name": "a", "description": "short one", "source": "modes", "advertised": True},
            {
                "name": "much-longer-name",
                "description": "the hidden one",
                "source": "modes",
                "advertised": False,
            },
        ]
    }
    text = "".join(s.text for s in native_modes_segments(catalog, term_width=200))
    short_line = next(line for line in text.splitlines() if "short one" in line)
    assert "short one" in short_line  # not truncated/misaligned by the wider hidden row


def test_esc_sequence_accepts_the_boundary_once() -> None:
    sequence = EscSequence()
    sequence.arm_interrupt(10.0)
    assert sequence.consume_backtrack(10.0 + ESC_BACKTRACK_WINDOW_SECONDS)
    assert not sequence.consume_backtrack(10.1)


def test_esc_sequence_expires_and_clears() -> None:
    sequence = EscSequence()
    sequence.arm_interrupt(10.0)
    assert not sequence.consume_backtrack(10.0 + ESC_BACKTRACK_WINDOW_SECONDS + 0.001)
    assert sequence.interrupted_at is None


# -- attention bell (hook-output adapter for the suppressed hooks-notify) -----


def test_attention_bell_rings_when_a_decision_is_deferred() -> None:
    """A deferred decision always needs the human — elapsed is irrelevant."""
    assert attention_bell_needed("awaiting_approval", 0.0, environ={})
    assert attention_bell_needed("awaiting_clarification", 0.0, environ={})
    assert attention_bell_needed("error", 0.0, environ={})


def test_attention_bell_rings_only_after_long_turns() -> None:
    """Turn end rings only when the turn ran long enough that the user has
    plausibly looked away; quick exchanges stay silent."""
    assert not attention_bell_needed("completion", 0.0, environ={})
    assert not attention_bell_needed("completion", ATTENTION_MIN_TURN_SECONDS - 0.1, environ={})
    assert attention_bell_needed("completion", ATTENTION_MIN_TURN_SECONDS, environ={})


def test_attention_bell_honors_amplifier_notify_env() -> None:
    """AMPLIFIER_NOTIFY=false/0/no/off disables the bell — same kill switch
    the suppressed hooks-notify module honored."""
    for value in ("false", "0", "no", "off", "FALSE", "Off"):
        assert not attention_bell_needed(
            "awaiting_approval", 0.0, environ={"AMPLIFIER_NOTIFY": value}
        )
        assert not attention_bell_needed("completion", 999.0, environ={"AMPLIFIER_NOTIFY": value})
    assert attention_bell_needed("awaiting_approval", 0.0, environ={"AMPLIFIER_NOTIFY": "true"})
