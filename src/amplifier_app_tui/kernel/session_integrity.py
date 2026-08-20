"""Provider-valid transcript repair at the resume boundary.

A session can end after an assistant emitted tool calls but before their
results were durably recorded.  Anthropic rejects that transcript shape.  A
provider may patch one request in memory, but the repair disappears on the
next request unless the application owns and persists it.  Resume therefore
repairs the stored transcript before the restored context is mounted.

Three failure modes are handled, and they are detected by two different
mechanisms for a deliberate reason:

``missing_tool_results``
    A tool call with no result.  Detected and repaired **here**, because this
    module tolerates both persisted call shapes: a top-level ``tool_calls``
    list *and* ``content`` blocks of type ``tool_call``/``tool_use``.  Real
    transcripts in this project carry a majority of calls in the block shape.

``ordering_violation``
    Detected by ``amplifier_foundation.session.diagnosis``, so the analysis
    stays shared with the rest of the ecosystem rather than reimplemented, and
    repaired here.  Foundation's index only reads the top-level shape, so it is
    fed a *shadow* copy that projects block-shaped calls and results into the
    shapes it understands.  The shadow is index-aligned 1:1 with the input,
    which is what makes the returned entry indices safe to apply to the real
    list.

``incomplete_assistant_turn``
    Detected by foundation and deliberately **not** repaired.  Closing a turn
    means writing a sentence the model never said; the next request reads that
    back as its own last words.  The genuine fix is the next real response,
    which resume is about to request anyway.

Repair is a single index-keyed pass: misplaced results are dropped, and the
orphan pass then fills every remaining unmatched call — including the calls
whose misplaced results were just removed.

The synthetic result never claims whether execution happened.  It tells the
next model to inspect real state before retrying, which is the only safe answer
when interruption races an external side effect.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

_TOOL_CALL_BLOCK_TYPES = frozenset({"tool_call", "tool_use"})


@dataclass(frozen=True)
class ToolResultRepair:
    """One interrupted tool call completed with an uncertainty placeholder."""

    tool_call_id: str
    tool_name: str


@dataclass(frozen=True)
class TranscriptRepair:
    """What a resume boundary had to fix before the context could be mounted."""

    tool_results: tuple[ToolResultRepair, ...] = ()
    misplaced_tool_ids: tuple[str, ...] = ()
    incomplete_turns: int = 0
    entries_before: int = 0
    entries_after: int = 0

    def __bool__(self) -> bool:
        """True only when the transcript was actually modified.

        ``incomplete_turns`` is reported, never repaired, so it does not make a
        transcript dirty on its own -- see :func:`repair_resumed_transcript`.
        """
        return bool(self.tool_results or self.misplaced_tool_ids)

    @property
    def failure_modes(self) -> tuple[str, ...]:
        modes: list[str] = []
        if self.tool_results:
            modes.append("missing_tool_results")
        if self.misplaced_tool_ids:
            modes.append("ordering_violation")
        if self.incomplete_turns:
            modes.append("incomplete_assistant_turn")
        return tuple(modes)

    def describe(self) -> str:
        """A single operator-facing sentence naming what was repaired."""
        parts: list[str] = []
        if self.tool_results:
            parts.append(f"{len(self.tool_results)} interrupted tool result(s)")
        if self.misplaced_tool_ids:
            parts.append(f"{len(self.misplaced_tool_ids)} out-of-order tool result(s)")
        if self.incomplete_turns:
            parts.append(f"{self.incomplete_turns} unclosed turn(s) (reported, not rewritten)")
        return ", ".join(parts) if parts else "nothing"


def _tool_calls(message: dict[str, Any]) -> tuple[ToolResultRepair, ...]:
    """Every tool call on a message, in either persisted shape, deduped by id."""
    if message.get("role") != "assistant":
        return ()
    calls: list[ToolResultRepair] = []
    seen: set[str] = set()

    top_level = message.get("tool_calls")
    if isinstance(top_level, list):
        for raw in top_level:
            if not isinstance(raw, dict):
                continue
            call_id = str(raw.get("id") or "").strip()
            function = raw.get("function")
            function_name = function.get("name") if isinstance(function, dict) else ""
            name = str(
                raw.get("name") or raw.get("tool") or function_name or "unknown tool"
            ).strip()
            if call_id and call_id not in seen:
                seen.add(call_id)
                calls.append(ToolResultRepair(call_id, name))

    content = message.get("content")
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict) or block.get("type") not in _TOOL_CALL_BLOCK_TYPES:
                continue
            call_id = str(block.get("id") or "").strip()
            name = str(block.get("name") or "unknown tool").strip()
            if call_id and call_id not in seen:
                seen.add(call_id)
                calls.append(ToolResultRepair(call_id, name))
    return tuple(calls)


def _tool_result_ids(message: dict[str, Any]) -> set[str]:
    results: set[str] = set()
    if message.get("role") == "tool":
        call_id = str(message.get("tool_call_id") or "").strip()
        if call_id:
            results.add(call_id)
    content = message.get("content")
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_result":
                continue
            call_id = str(block.get("tool_use_id") or block.get("tool_call_id") or "").strip()
            if call_id:
                results.add(call_id)
    return results


def _synthetic_result(repair: ToolResultRepair) -> dict[str, Any]:
    return {
        "role": "tool",
        "content": (
            "[SYSTEM RECOVERY: This tool result was not durably recorded before "
            "the previous session ended. The tool may have executed. Inspect the "
            "actual external or disk state before retrying.]"
        ),
        "tool_call_id": repair.tool_call_id,
        "name": repair.tool_name,
    }


def _shadow_for_diagnosis(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """An index-aligned copy foundation's top-level-only index can read.

    Block-shaped tool calls are projected onto a top-level ``tool_calls`` key
    and block-shaped results onto ``tool_call_id``.  Entries are shallow copies
    and the input is never mutated.  The 1:1 index alignment is load-bearing:
    ``incomplete_turns`` reports ``after_index`` against this list, and those
    indices are applied to the real one.
    """
    shadow: list[dict[str, Any]] = []
    for idx, message in enumerate(messages):
        entry = {**message, "line_num": idx + 1}
        if message.get("role") == "assistant":
            calls = _tool_calls(message)
            if calls:
                entry["tool_calls"] = [
                    {"id": call.tool_call_id, "tool": call.tool_name} for call in calls
                ]
        elif not str(message.get("tool_call_id") or "").strip():
            # A result can ride on a non-tool role: Anthropic returns
            # ``tool_result`` blocks on a *user* message.  Left as-is, foundation
            # sees no result and reads that message as a user interruption --
            # which made repair non-idempotent, appending a fresh synthetic turn
            # on every resume.  Presenting it as the tool record it actually is
            # keeps foundation's view of results consistent with the orphan pass
            # below.  A single message can technically carry several results;
            # foundation indexes one id per entry, and the remainder stay visible
            # to the orphan pass, which reads every block.
            result_ids = sorted(_tool_result_ids(message))
            if result_ids:
                entry["role"] = "tool"
                entry["tool_call_id"] = result_ids[0]
        shadow.append(entry)
    return shadow


def _diagnose_extended(messages: list[dict[str, Any]]) -> tuple[set[int], set[int], set[str]]:
    """Foundation's view of the two failure modes this module does not detect.

    Returns ``(skip_indices, incomplete_after_indices, misplaced_tool_ids)``.
    Diagnosis is advisory: a failure here degrades to orphan-only repair rather
    than blocking a resume.
    """
    try:
        from amplifier_foundation.session.diagnosis import diagnose_transcript
    except ImportError:  # pragma: no cover - foundation is a hard dependency
        logger.debug("foundation transcript diagnosis unavailable", exc_info=True)
        return set(), set(), set()

    try:
        shadow = _shadow_for_diagnosis(messages)
        diagnosis = diagnose_transcript(shadow)
    except Exception:  # noqa: BLE001 - never let diagnosis break a resume
        logger.warning("transcript diagnosis failed; repairing orphans only", exc_info=True)
        return set(), set(), set()

    if diagnosis.get("status") == "healthy":
        return set(), set(), set()

    misplaced = {str(tid) for tid in diagnosis.get("misplaced_tool_ids") or ()}
    skip_indices = {
        idx
        for idx, message in enumerate(messages)
        if message.get("role") == "tool" and _tool_result_ids(message) & misplaced
    }

    incomplete_after: set[int] = set()
    for turn in diagnosis.get("incomplete_turns") or ():
        if not isinstance(turn, dict):
            continue
        after_index = turn.get("after_index")
        if after_index is None and turn.get("after_line") is not None:
            after_index = int(turn["after_line"]) - 1
        if isinstance(after_index, int) and 0 <= after_index < len(messages):
            incomplete_after.add(after_index)

    return skip_indices, incomplete_after, misplaced


def repair_resumed_transcript(
    messages: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], TranscriptRepair | None]:
    """Return a provider-valid transcript plus a record of what was repaired.

    A healthy transcript is returned unchanged (the same list object) with a
    ``None`` repair, so a clean resume copies nothing.  Existing tool results
    always win: this function never duplicates or replaces real output.  New
    placeholders are inserted immediately after the message that made the
    calls, satisfying provider ordering requirements for parallel calls.

    An unclosed assistant turn is **reported and not rewritten**.  Closing one
    means writing a sentence the model never said, and a fabricated assistant
    utterance is read back by the next request as the model's own last words --
    a strong pattern for it to continue.  The genuine fix is the next real
    response, which resume is about to request anyway.  Declining to fabricate
    is also what makes this function idempotent: repairing an orphan leaves a
    transcript ending on a tool result, so a rule that closed such turns would
    manufacture fresh work for itself on every resume and grow the stored
    conversation without bound.
    """
    if not messages:
        return messages, None

    skip_indices, incomplete_after, misplaced = _diagnose_extended(messages)

    # Results that were out of order are dropped here, which leaves their
    # calls unmatched — the orphan pass then re-inserts them in a valid
    # position.  One index-keyed pass keeps every decision aligned to the
    # input, so nothing shifts underneath a later step.
    staged: list[dict[str, Any]] = []
    for idx, message in enumerate(messages):
        if idx in skip_indices:
            continue
        staged.append(message)

    claimed: set[str] = set()
    for message in staged:
        claimed |= _tool_result_ids(message)

    repaired: list[dict[str, Any]] = []
    tool_results: list[ToolResultRepair] = []
    for message in staged:
        repaired.append(message)
        for call in _tool_calls(message):
            if call.tool_call_id in claimed:
                continue
            claimed.add(call.tool_call_id)
            tool_results.append(call)
            repaired.append(_synthetic_result(call))

    repair = TranscriptRepair(
        tool_results=tuple(tool_results),
        misplaced_tool_ids=tuple(sorted(misplaced)),
        incomplete_turns=len(incomplete_after),
        entries_before=len(messages),
        entries_after=len(repaired),
    )
    if not repair:
        # Nothing was rewritten. An unclosed turn alone is worth saying once,
        # but it must not mark the transcript dirty: persisting on detection
        # would rewrite a stored conversation that did not change.
        if repair.incomplete_turns:
            logger.info(
                "Resumed transcript has %d unclosed turn(s); the next response closes them.",
                repair.incomplete_turns,
            )
        return messages, None

    logger.warning(
        "Resumed transcript repaired: %s (entries %d -> %d, modes=%s)",
        repair.describe(),
        repair.entries_before,
        repair.entries_after,
        ",".join(repair.failure_modes),
    )
    return repaired, repair


__all__ = [
    "ToolResultRepair",
    "TranscriptRepair",
    "repair_resumed_transcript",
]
