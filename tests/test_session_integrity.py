"""Resume-time repair for interrupted tool sequences.

These import through ``amplifier_app_tui.kernel``, whose ``__path__`` shim
resolves to the runtime-owned module -- so this file is a client-side contract
test over ``amplifier-runtime``, not coverage of anything this repo ships. The
local duplicate was deleted; the shim refuses a local fallback by design.

What is pinned here is the shape tolerance the TUI depends on: calls persisted
as ``content`` blocks AND as a top-level ``tool_calls`` list, and results that
arrive as ``role: tool`` records or as ``tool_result`` blocks on another role.
Real transcripts carry a majority of calls in the block shape, so a repair path
that only understood the top-level shape would silently miss most interrupted
work.
"""

from __future__ import annotations

from amplifier_app_tui.kernel.session_integrity import repair_resumed_transcript


def test_completes_content_and_top_level_orphans_immediately_after_assistant() -> None:
    messages = [
        {"role": "user", "content": "work in parallel"},
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Starting."},
                {"type": "tool_call", "id": "call-a", "name": "bash", "input": {}},
                {"type": "tool_use", "id": "call-b", "name": "delegate", "input": {}},
            ],
            "tool_calls": [
                {
                    "id": "call-c",
                    "type": "function",
                    "function": {"name": "read_file", "arguments": "{}"},
                },
                {"id": "call-d", "tool": "todo", "arguments": {}},
            ],
        },
        {"role": "user", "content": "resume"},
    ]

    repaired, repair = repair_resumed_transcript(messages)

    assert repair is not None
    assert repair.failure_modes == ("missing_tool_results",)
    assert [(row.tool_call_id, row.tool_name) for row in repair.tool_results] == [
        ("call-c", "read_file"),
        ("call-d", "todo"),
        ("call-a", "bash"),
        ("call-b", "delegate"),
    ]
    assert [message["role"] for message in repaired] == [
        "user",
        "assistant",
        "tool",
        "tool",
        "tool",
        "tool",
        "user",
    ]
    assert {message.get("tool_call_id") for message in repaired} >= {
        "call-a",
        "call-b",
        "call-c",
        "call-d",
    }
    assert all(
        "may have executed" in str(message.get("content"))
        for message in repaired
        if message.get("role") == "tool"
    )


def test_preserves_real_results_and_repairs_only_the_missing_parallel_call() -> None:
    """A real result is never duplicated; only the unmatched sibling is filled.

    The placeholder lands immediately after the message that made the call --
    the ordering providers require for parallel calls -- so the real result
    keeps its own later position.

    This transcript also ends without a closing assistant message, which is
    reported as an unclosed turn but deliberately not written: fabricating an
    assistant utterance would be read back by the next request as the model's
    own last words.
    """
    messages = [
        {
            "role": "assistant",
            "content": [
                {"type": "tool_call", "id": "done", "name": "bash", "input": {}},
                {"type": "tool_call", "id": "missing", "name": "delegate", "input": {}},
            ],
        },
        {"role": "tool", "tool_call_id": "done", "name": "bash", "content": "ok"},
    ]

    repaired, repair = repair_resumed_transcript(messages)

    assert repair is not None
    assert [row.tool_call_id for row in repair.tool_results] == ["missing"]
    assert sum(message.get("tool_call_id") == "done" for message in repaired) == 1
    assert sum(message.get("tool_call_id") == "missing" for message in repaired) == 1
    # The real result survives verbatim, after the placeholder.
    assert repaired[-1] == {"role": "tool", "tool_call_id": "done", "name": "bash", "content": "ok"}

    assert "incomplete_assistant_turn" in repair.failure_modes
    assert repair.incomplete_turns == 1
    assert not any(message.get("role") == "assistant" for message in repaired[1:])


def test_tool_result_content_block_counts_as_real_and_repair_is_idempotent() -> None:
    """A ``tool_result`` block on a non-tool role still counts as a real result.

    Re-running over an already-repaired transcript must be a no-op that copies
    nothing -- a clean resume should not rewrite the stored conversation, and a
    repair that found fresh work on its own output would grow the transcript
    once per resume.
    """
    messages = [
        {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": "existing", "name": "bash", "input": {}},
                {"type": "tool_use", "id": "orphan", "name": "delegate", "input": {}},
            ],
        },
        {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "existing", "content": "ok"}],
        },
    ]

    first, repair = repair_resumed_transcript(messages)
    second, repeated = repair_resumed_transcript(first)

    assert repair is not None
    assert [row.tool_call_id for row in repair.tool_results] == ["orphan"]
    assert repeated is None
    assert second is first
