"""Protocol-level tests for the serve control plane (item B6).

Drives :func:`amplifier_app_tui.kernel.serve.serve_loop` with a minimal fake
runtime over a REAL :class:`SessionStore` in a tmp dir -- the same seam the
live CLI ``serve`` uses -- and proves the contract an out-of-process
controller (and item B8 on top of it) depends on:

* a legacy client that never opts in sees the byte-identical old protocol;
* exactly one holder may write; conflicting input is refused, never interleaved;
* takeover is deterministic and invalidates the loser's token;
* an ``idem`` retry after a dropped connection does not double-submit;
* a reattached client replays the same history without touching the ledger;
* an abandoned lease expires, so a session is never permanently locked;
* pause mints a durable handoff a human can claim, and it is all audited.

A "reconnect" here is a second ``serve_loop`` over the same session directory
-- exactly what a dropped stdio pipe means for a protocol client.
"""

from __future__ import annotations

import asyncio
import json
import queue
from pathlib import Path
from typing import IO, Any, cast

import pytest

from amplifier_app_tui.kernel.approval import ALLOW_ONCE, ApprovalBroker, ApprovalDetail
from amplifier_app_tui.kernel.events import Notification
from amplifier_app_tui.kernel.goal import GoalCommandResult
from amplifier_app_tui.kernel.persistence import SessionStore
from amplifier_app_tui.kernel.serve import serve_loop
from amplifier_app_tui.kernel.session_control import (
    AUDIT_FILENAME,
    CONTROL_FILENAME,
    REASON_LEASE_HELD,
    REASON_NOT_HOLDER,
    REASON_SESSION_PAUSED,
    Actor,
)
from amplifier_app_tui.model.queues import SteeringQueue

pytestmark = pytest.mark.asyncio

BOT = {"id": "bot-1", "kind": "automation"}
MJ = {"id": "mj", "kind": "human"}


class _PipeStdin:
    def __init__(self) -> None:
        self._q: queue.Queue[str | None] = queue.Queue()

    def feed(self, obj: dict[str, Any]) -> None:
        self._q.put(json.dumps(obj) + "\n")

    def close(self) -> None:
        self._q.put(None)

    def __iter__(self) -> _PipeStdin:
        return self

    def __next__(self) -> str:
        item = self._q.get()
        if item is None:
            raise StopIteration
        return item


class _Capture:
    def __init__(self) -> None:
        self.lines: list[dict[str, Any]] = []

    def write(self, s: str) -> int:
        for part in s.splitlines():
            text = part.strip()
            if text:
                self.lines.append(json.loads(text))
        return len(s)

    def flush(self) -> None:
        pass

    def types(self) -> list[str]:
        return [r.get("type", "") for r in self.lines]

    def find(self, type_: str) -> dict[str, Any] | None:
        return next((r for r in self.lines if r.get("type") == type_), None)

    def all(self, type_: str) -> list[dict[str, Any]]:
        return [r for r in self.lines if r.get("type") == type_]

    def conflicts(self) -> list[dict[str, Any]]:
        return self.all("control.conflict")

    def audits(self) -> list[dict[str, Any]]:
        return [r["entry"] for r in self.all("control.audit")]


class _NoBroker:
    head = None

    def add_listener(self, listener: Any) -> None:
        del listener


class _ControlRuntime:
    """Minimal serve_loop surface + a real store.

    ``submit`` records the text and appends to the durable UIEvent ledger the
    way ``RealRuntime`` does, so ``history.replay`` has honest history to
    stream on a reattach.
    """

    def __init__(self, store: SessionStore, session_id: str) -> None:
        self.store = store
        self.session_id = session_id
        self.bundle_name = "tui"
        self.model_name = "test-model"
        self.queue: asyncio.Queue[Any] = asyncio.Queue()
        self.broker: Any = _NoBroker()
        self.steering = SteeringQueue()
        self.submits: list[str] = []
        self.interrupts = 0
        self.goal_calls: list[str] = []
        self.goal_started = asyncio.Event()
        self.goal_release = asyncio.Event()
        self.block_submit = False
        self.submit_started = asyncio.Event()
        self.submit_release = asyncio.Event()

    async def submit(self, text: str) -> str:
        self.submits.append(text)
        self.store.append_event(
            self.session_id,
            {"kind": "prompt_submit", "session_id": self.session_id, "ts": 1.0, "text": text},
        )
        if self.block_submit:
            self.submit_started.set()
            await self.submit_release.wait()
        return f"ok:{text}"

    async def interrupt(self) -> None:
        self.interrupts += 1

    async def configure_goal(self, args: str) -> GoalCommandResult:
        self.goal_calls.append(args)
        if not args:
            return GoalCommandResult(
                True,
                "status",
                "Goal: all checks pass",
                condition="all checks pass",
                cap=3,
            )
        if args == "clear":
            self.goal_release.set()
            return GoalCommandResult(True, "cleared", "Goal cleared: all checks pass")
        parts = args.split(maxsplit=2)
        cap = int(parts[1]) if parts[:1] == ["--max-turns"] else None
        condition = parts[2] if cap is not None and len(parts) == 3 else args
        return GoalCommandResult(
            True,
            "set",
            f"Goal set (max {cap} turns)." if cap else "Goal set (unlimited turns).",
            raw_condition=condition,
            condition=condition,
            cap=cap,
        )

    async def manage_goal(self, args: str, *, _on_configured: Any = None) -> GoalCommandResult:
        result = await self.configure_goal(args)
        if result.ok and result.action == "set":
            self.goal_started.set()
            if _on_configured is not None:
                _on_configured(result)
            await self.goal_release.wait()
        return result

    async def cleanup(self) -> None:
        pass


async def _wait_until(predicate, timeout: float = 5.0) -> None:
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("condition not met within timeout")


class _Connection:
    """One client connection to a session (a serve_loop over a pipe)."""

    def __init__(self, runtime: _ControlRuntime, **kwargs: Any) -> None:
        self.stdin = _PipeStdin()
        self.out = _Capture()
        self.task = asyncio.create_task(
            serve_loop(
                cast("Any", runtime),
                source=cast("IO[str]", self.stdin),
                out=cast("IO[str]", self.out),
                **kwargs,
            )
        )

    def send(self, **op: Any) -> None:
        self.stdin.feed(op)

    async def wait(self, predicate, timeout: float = 5.0) -> None:
        await _wait_until(predicate, timeout)

    async def drop(self) -> int:
        """Close the pipe -- what a dropped controller looks like to serve."""
        self.stdin.close()
        return await asyncio.wait_for(self.task, timeout=5.0)


@pytest.fixture
def store(tmp_path: Path) -> SessionStore:
    return SessionStore(base_dir=tmp_path / "sessions")


@pytest.fixture
def runtime(store: SessionStore) -> _ControlRuntime:
    session_id = "s" * 32
    store.save(session_id, [], {"session_id": session_id, "bundle": "tui"})
    return _ControlRuntime(store, session_id)


def _session_dir(runtime: _ControlRuntime) -> Path:
    return runtime.store.session_dir(runtime.session_id)


async def test_control_record_does_not_shadow_jsonl_event_encoder(
    runtime: _ControlRuntime,
) -> None:
    """A control reply must not replace the JsonlRecords captured by _pump.

    This is the exact regression: after the first control op, the next runtime
    event used to call ``runtime_event`` on the control handler's list and kill
    the pump task.
    """

    conn = _Connection(runtime)
    conn.send(op="lease.status")
    await conn.wait(lambda: conn.out.find("lease.state") is not None)

    runtime.queue.put_nowait(
        Notification(
            session_id=runtime.session_id,
            message="pump still alive",
            source="regression-test",
        )
    )
    await conn.wait(lambda: conn.out.find("runtime.event") is not None)

    record = conn.out.find("runtime.event")
    assert record is not None
    assert record["event"]["kind"] == "notification"
    assert record["event"]["message"] == "pump still alive"
    assert not conn.task.done()
    assert await conn.drop() == 0


async def test_approval_record_carries_structural_lane_identity(
    runtime: _ControlRuntime,
) -> None:
    runtime.broker = ApprovalBroker()
    conn = _Connection(runtime)
    await conn.wait(lambda: conn.out.find("session.started") is not None)
    runtime.broker.stage_detail(
        "Allow child write?",
        ApprovalDetail(
            tool_name="write_file",
            session_id="child-session",
            parent_id=runtime.session_id,
            tool_call_id="call-child-7",
        ),
    )
    request = asyncio.create_task(
        runtime.broker.request_approval("Allow child write?", [], timeout=3600)
    )

    await conn.wait(lambda: conn.out.find("approval.required") is not None)
    approval = conn.out.find("approval.required")
    assert approval is not None
    assert approval["session_id"] == "child-session"
    assert approval["parent_id"] == runtime.session_id
    assert approval["tool_call_id"] == "call-child-7"

    conn.send(op="approve", ticket_id=approval["ticket_id"], choice=ALLOW_ONCE)
    assert await asyncio.wait_for(request, timeout=1) == ALLOW_ONCE
    assert await conn.drop() == 0


async def test_goal_ops_use_native_runtime_and_share_the_turn_slot(
    runtime: _ControlRuntime,
) -> None:
    conn = _Connection(runtime)
    conn.send(op="goal.set", condition="all checks pass", max_turns=3)
    await asyncio.wait_for(runtime.goal_started.wait(), timeout=1)
    assert conn.out.find("goal.result") is None
    await conn.wait(lambda: len(conn.out.all("goal.state")) == 1)
    armed = conn.out.all("goal.state")[0]
    assert armed["action"] == "set"
    assert armed["active"] is True

    # A goal run owns the ordinary turn slot: a competing submit is not
    # admitted, while status and clear remain serviceable on the ops lane.
    conn.send(op="submit", text="must not interleave")
    conn.send(op="goal.status")
    await conn.wait(lambda: len(conn.out.all("goal.state")) == 2)
    status = conn.out.all("goal.state")[1]
    assert status["ok"] is True
    assert status["action"] == "status"
    assert status["condition"] == "all checks pass"
    assert status["max_turns"] == 3
    assert status["active"] is True

    conn.send(op="goal.clear")
    await conn.wait(lambda: len(conn.out.all("goal.state")) == 3)
    await conn.wait(lambda: conn.out.find("goal.result") is not None)
    cleared = conn.out.all("goal.state")[2]
    result = conn.out.find("goal.result")
    assert cleared["action"] == "cleared"
    assert cleared["active"] is False
    assert result is not None and result["action"] == "set"
    assert runtime.submits == []
    assert runtime.goal_calls == ["--max-turns 3 all checks pass", "", "clear"]

    # Once goal.result closes the native run, the slot is reusable.
    conn.send(op="submit", text="after goal")
    await conn.wait(lambda: conn.out.find("turn.completed") is not None)
    assert runtime.submits == ["after goal"]
    assert await conn.drop() == 0


async def test_goal_set_arms_the_native_loop_during_an_active_turn(
    runtime: _ControlRuntime,
) -> None:
    runtime.block_submit = True
    conn = _Connection(runtime)
    conn.send(op="submit", text="work already running")
    await asyncio.wait_for(runtime.submit_started.wait(), timeout=1)

    conn.send(op="goal.set", condition="finish every check", max_turns=4)
    await conn.wait(lambda: conn.out.find("goal.state") is not None)
    state = conn.out.find("goal.state")
    assert state is not None
    assert state["ok"] is True
    assert state["active"] is True
    assert state["condition"] == "finish every check"
    assert state["max_turns"] == 4
    assert runtime.goal_calls == ["--max-turns 4 finish every check"]
    assert not runtime.goal_started.is_set(), "configure-only must not launch a second goal turn"

    runtime.submit_release.set()
    await conn.wait(lambda: conn.out.find("turn.completed") is not None)
    assert runtime.submits == ["work already running"]
    assert await conn.drop() == 0


# -- opt-in ------------------------------------------------------------------


async def test_a_legacy_client_sees_the_unchanged_protocol(runtime: _ControlRuntime) -> None:
    """No actor, no lease, no idem -> no control records and no control files.
    The plane is opt-in; an existing front-end notices nothing."""
    conn = _Connection(runtime)
    conn.send(op="submit", text="hello")
    await conn.wait(lambda: conn.out.find("turn.completed") is not None)
    assert await conn.drop() == 0

    assert runtime.submits == ["hello"]
    assert conn.out.types() == ["session.started", "turn.completed"]
    assert not (_session_dir(runtime) / CONTROL_FILENAME).exists()
    assert not (_session_dir(runtime) / AUDIT_FILENAME).exists()


async def test_session_handle_is_stable_across_connections(runtime: _ControlRuntime) -> None:
    """The durable handle a controller hands out survives a reconnect, so a
    reference minted in one process still names this session in the next."""
    first = _Connection(runtime)
    first.send(op="session.handle")
    await first.wait(lambda: first.out.find("session.handle") is not None)
    handle = first.out.find("session.handle")
    assert handle is not None
    await first.drop()

    second = _Connection(runtime)
    second.send(op="session.handle")
    await second.wait(lambda: second.out.find("session.handle") is not None)
    again = second.out.find("session.handle")
    assert again is not None
    await second.drop()

    assert again["handle"]["handle_id"] == handle["handle"]["handle_id"]
    assert again["handle"]["ref"] == f"amplifier-session:{runtime.session_id}"


# -- single writer -----------------------------------------------------------


async def test_a_second_writer_is_refused_not_interleaved(runtime: _ControlRuntime) -> None:
    """The AC3 guarantee: with a lease held, a competing submit is rejected
    deterministically -- it never reaches the runtime."""
    conn = _Connection(runtime)
    conn.send(op="lease.acquire", actor=BOT, ttl=60)
    await conn.wait(lambda: conn.out.find("lease.state") is not None)
    lease = conn.out.find("lease.state")["lease"]["lease_id"]  # type: ignore[index]

    conn.send(op="submit", text="from a stranger", actor=MJ)  # no lease presented
    conn.send(op="submit", text="from the holder", lease=lease)
    await conn.wait(lambda: conn.out.find("turn.completed") is not None)
    assert await conn.drop() == 0

    assert runtime.submits == ["from the holder"]
    conflict = conn.out.conflicts()[0]
    assert conflict["reason"] == REASON_LEASE_HELD
    assert conflict["op"] == "submit"
    assert conflict["holder"]["id"] == "bot-1"


async def test_takeover_invalidates_the_previous_holders_token(
    runtime: _ControlRuntime,
) -> None:
    """A human takes the pen from the bot; the bot's stale lease stops working
    immediately, and the human's writes go through."""
    conn = _Connection(runtime)
    conn.send(op="lease.acquire", actor=BOT)
    await conn.wait(lambda: conn.out.find("lease.state") is not None)
    stale = conn.out.find("lease.state")["lease"]["lease_id"]  # type: ignore[index]

    conn.send(op="lease.takeover", actor=MJ, reason="taking it from here")
    await conn.wait(lambda: len(conn.out.all("lease.state")) >= 2)
    human_lease = conn.out.all("lease.state")[-1]["lease"]
    assert human_lease["actor"]["id"] == "mj"

    conn.send(op="submit", text="bot still trying", lease=stale)
    conn.send(op="submit", text="human speaking", lease=human_lease["lease_id"])
    await conn.wait(lambda: conn.out.find("turn.completed") is not None)
    assert await conn.drop() == 0

    assert runtime.submits == ["human speaking"]
    assert conn.out.conflicts()[0]["reason"] == REASON_NOT_HOLDER
    assert "lease.revoked" in [entry["action"] for entry in conn.out.audits()]


async def test_an_automated_client_cannot_take_the_lease_from_a_human(
    runtime: _ControlRuntime,
) -> None:
    conn = _Connection(runtime)
    conn.send(op="lease.acquire", actor=MJ)
    await conn.wait(lambda: conn.out.find("lease.state") is not None)
    conn.send(op="lease.takeover", actor=BOT, force=True)
    await conn.wait(lambda: conn.out.find("control.conflict") is not None)
    assert await conn.drop() == 0

    assert conn.out.conflicts()[0]["reason"] == "takeover_denied"
    assert conn.out.all("lease.state")[-1]["lease"]["actor"]["id"] == "mj"


# -- idempotency + reconnect -------------------------------------------------


async def test_idempotent_submit_survives_a_dropped_connection(
    runtime: _ControlRuntime,
) -> None:
    """The retry a reconnecting controller sends must NOT run the turn twice.
    The key is durable, so the replay works from a brand-new connection."""
    first = _Connection(runtime)
    first.send(op="submit", text="deploy", actor=BOT, idem="req-42")
    await first.wait(lambda: first.out.find("turn.completed") is not None)
    await first.drop()
    assert first.out.find("control.ack")["op"] == "submit"  # type: ignore[index]

    second = _Connection(runtime)
    second.send(op="submit", text="deploy", actor=BOT, idem="req-42")
    await second.wait(lambda: second.out.find("control.ack") is not None)
    assert await second.drop() == 0

    assert runtime.submits == ["deploy"], "the retry must not double-submit"
    ack = second.out.find("control.ack")
    assert ack is not None and ack["replay"] is True
    assert second.out.find("turn.completed") is None


async def test_reattach_replays_the_same_history_without_touching_it(
    runtime: _ControlRuntime,
) -> None:
    """AC5: a reconnecting participant observes the same event history, and
    replay is read-only -- the durable ledger is byte-identical afterwards."""
    first = _Connection(runtime)
    first.send(op="submit", text="one")
    await first.wait(lambda: first.out.find("turn.completed") is not None)
    first.send(op="submit", text="two")
    await first.wait(lambda: len(first.out.all("turn.completed")) == 2)
    await first.drop()

    ledger = _session_dir(runtime) / "ui-events.jsonl"
    before = ledger.read_bytes()

    second = _Connection(runtime)
    second.send(op="history.replay")
    await second.wait(lambda: second.out.find("history.end") is not None)
    second.send(op="history.replay", since=1)
    await second.wait(lambda: len(second.out.all("history.end")) == 2)
    assert await second.drop() == 0

    replayed = [r for r in second.out.all("runtime.event") if r.get("replay")]
    assert [r["event"]["text"] for r in replayed[:2]] == ["one", "two"]
    # Assert the fields this client consumes, not the whole envelope. Runtime
    # owns this contract and pins it exactly in its own suite; a CONSUMER that
    # demands exact equality turns every backward-compatible addition into a
    # break. That is not hypothetical: runtime added `source` (which ledger the
    # history came from -- "ui-events" or a legacy "transcript") to both
    # history.begin and history.end, and this assertion failed on a change that
    # took nothing away.
    end = second.out.all("history.end")[0]
    assert (
        end.items()
        >= {
            "schema_version": 1,
            "type": "history.end",
            "session_id": runtime.session_id,
            "count": 2,
            "cursor": 2,
            "source": "ui-events",
        }.items()
    )
    # The cursor lets a client resume where it stopped.
    assert second.out.all("history.begin")[1]["since"] == 1
    assert second.out.all("history.end")[1]["count"] == 1
    assert ledger.read_bytes() == before, "replay must never write the transcript"


async def test_replay_clamps_a_cursor_beyond_the_durable_tail(
    runtime: _ControlRuntime,
) -> None:
    runtime.store.append_event(
        runtime.session_id,
        Notification(
            event_id="durable-one",
            session_id=runtime.session_id,
            message="one",
            source="cursor-test",
        ),
    )
    conn = _Connection(runtime)
    conn.send(op="history.replay", since=99_999)
    await conn.wait(lambda: conn.out.find("history.end") is not None)

    assert conn.out.find("history.begin")["since"] == 1  # type: ignore[index]
    assert conn.out.find("history.end")["cursor"] == 1  # type: ignore[index]
    assert await conn.drop() == 0


async def test_replay_does_not_repeat_an_event_still_waiting_in_the_live_queue(
    runtime: _ControlRuntime,
) -> None:
    class _GatedQueue(asyncio.Queue[Any]):
        def __init__(self) -> None:
            super().__init__()
            self.release = asyncio.Event()

        async def get(self) -> Any:
            await self.release.wait()
            return await super().get()

    pending = Notification(
        event_id="pending-at-replay",
        session_id=runtime.session_id,
        message="exactly once",
        source="replay-race-test",
    )
    runtime.store.append_event(runtime.session_id, pending)
    gated = _GatedQueue()
    gated.put_nowait(pending)
    runtime.queue = gated

    conn = _Connection(runtime)
    conn.send(op="history.replay", since=0)
    await conn.wait(lambda: conn.out.find("history.end") is not None)
    gated.release.set()
    await asyncio.sleep(0)

    matching = [
        record
        for record in conn.out.all("runtime.event")
        if record.get("event", {}).get("event_id") == pending.event_id
    ]
    assert len(matching) == 1
    assert matching[0]["replay"] is True
    assert await conn.drop() == 0


async def test_an_abandoned_lease_expires_so_the_session_is_never_locked(
    runtime: _ControlRuntime,
) -> None:
    """AC5's hard edge: the controller vanishes mid-session holding the lease.
    Writes are refused while it is live, and freed the moment it expires --
    no unlock request, no operator intervention."""
    controller = _Connection(runtime)
    controller.send(op="lease.acquire", actor=BOT, ttl=0.2)
    await controller.wait(lambda: controller.out.find("lease.state") is not None)
    await controller.drop()  # dropped without releasing

    human = _Connection(runtime)
    human.send(op="submit", text="too early", actor=MJ)
    await human.wait(lambda: human.out.find("control.conflict") is not None)
    assert human.out.conflicts()[0]["reason"] == REASON_LEASE_HELD
    assert runtime.submits == []

    await asyncio.sleep(0.25)  # the lease TTL elapses with nobody heartbeating
    human.send(op="submit", text="now mine", actor=MJ)
    await human.wait(lambda: human.out.find("turn.completed") is not None)
    assert await human.drop() == 0

    assert runtime.submits == ["now mine"]
    assert "lease.expired" in [entry["action"] for entry in human.out.audits()]


# -- pause / handoff / audit -------------------------------------------------


async def test_pause_escalates_with_a_durable_handoff_a_human_claims(
    runtime: _ControlRuntime,
) -> None:
    """AC2 end to end: the controller pauses, gets a durable reference, and a
    human uses it to attach to the SAME session and take the write lease."""
    bot = _Connection(runtime)
    bot.send(op="lease.acquire", actor=BOT)
    await bot.wait(lambda: bot.out.find("lease.state") is not None)
    lease = bot.out.find("lease.state")["lease"]["lease_id"]  # type: ignore[index]
    bot.send(
        op="session.pause",
        actor=BOT,
        lease=lease,
        reason="needs human judgment",
        note="approve the prod deploy?",
        interrupt=True,
    )
    await bot.wait(lambda: bot.out.find("handoff.created") is not None)
    handoff = bot.out.find("handoff.created")["handoff"]  # type: ignore[index]
    assert handoff["ref"] == f"amplifier-session:{runtime.session_id}#{handoff['handoff_id']}"
    assert handoff["attach_command"] == f"amplifier-tui serve --attach {handoff['ref']}"

    # Paused: even the pauser cannot write until a human takes it.
    bot.send(op="submit", text="carry on anyway", actor=BOT)
    await bot.wait(lambda: bot.out.find("control.conflict") is not None)
    assert bot.out.conflicts()[0]["reason"] == REASON_SESSION_PAUSED
    await bot.wait(lambda: runtime.interrupts == 1)  # "interrupt": true honored
    await bot.drop()
    assert runtime.submits == []

    # The human arrives on a NEW connection with only the durable ref.
    human = _Connection(runtime)
    human.send(op="handoff.claim", handoff=handoff["handoff_id"], actor=MJ)
    await human.wait(lambda: human.out.find("handoff.claimed") is not None)
    granted = human.out.all("lease.state")[-1]["lease"]
    assert granted["actor"]["id"] == "mj"
    human.send(op="submit", text="I'll take it from here", lease=granted["lease_id"])
    await human.wait(lambda: human.out.find("turn.completed") is not None)
    assert await human.drop() == 0

    assert runtime.submits == ["I'll take it from here"]


async def test_attach_boot_claims_the_handoff_and_hands_over_the_lease(
    runtime: _ControlRuntime,
) -> None:
    """The CLI ``--attach <ref>`` adapter: the arriving human holds the write
    lease before their first keystroke."""
    bot = _Connection(runtime)
    bot.send(op="session.pause", actor=BOT, reason="escalate")
    await bot.wait(lambda: bot.out.find("handoff.created") is not None)
    handoff_id = bot.out.find("handoff.created")["handoff"]["handoff_id"]  # type: ignore[index]
    await bot.drop()

    human = _Connection(
        runtime,
        default_actor=Actor(id="mj", kind="human"),
        attach_handoff=handoff_id,
    )
    await human.wait(lambda: human.out.find("handoff.claimed") is not None)
    lease = human.out.all("lease.state")[-1]["lease"]
    assert lease["actor"] == {"id": "mj", "kind": "human"}
    human.send(op="submit", text="hello", lease=lease["lease_id"])
    await human.wait(lambda: human.out.find("turn.completed") is not None)
    assert await human.drop() == 0
    assert runtime.submits == ["hello"]


async def test_every_automated_action_and_handoff_is_attributable(
    runtime: _ControlRuntime,
) -> None:
    """AC4: the durable trail names an actor for each action, and any client
    can read it back over the protocol with ``audit.query``."""
    conn = _Connection(runtime)
    conn.send(op="lease.acquire", actor=BOT)
    await conn.wait(lambda: conn.out.find("lease.state") is not None)
    lease = conn.out.find("lease.state")["lease"]["lease_id"]  # type: ignore[index]
    conn.send(op="submit", text="ship it", lease=lease)
    await conn.wait(lambda: conn.out.find("turn.completed") is not None)
    conn.send(op="session.pause", actor=BOT, lease=lease, reason="escalate")
    await conn.wait(lambda: conn.out.find("handoff.created") is not None)
    handoff_id = conn.out.find("handoff.created")["handoff"]["handoff_id"]  # type: ignore[index]
    conn.send(op="handoff.claim", handoff=handoff_id, actor=MJ)
    await conn.wait(lambda: conn.out.find("handoff.claimed") is not None)
    conn.send(op="audit.query", limit=50)
    await conn.wait(lambda: conn.out.find("audit.list") is not None)
    assert await conn.drop() == 0

    entries = conn.out.find("audit.list")["entries"]  # type: ignore[index]
    pairs = [(e["action"], e["actor"]["id"]) for e in entries]
    assert pairs == [
        ("lease.granted", "bot-1"),
        ("write.accepted", "bot-1"),
        ("lease.released", "bot-1"),
        ("session.paused", "bot-1"),
        ("handoff.created", "bot-1"),
        ("handoff.claimed", "mj"),
    ]
    # The same trail is durable on disk, not just on the wire.
    lines = (_session_dir(runtime) / AUDIT_FILENAME).read_text().splitlines()
    assert [json.loads(line)["action"] for line in lines if line.strip()] == [
        action for action, _ in pairs
    ]
