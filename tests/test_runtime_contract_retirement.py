"""Exercise the active runtime boundary and a disposable no-copy package.

No source is deleted. The public TUI's locked runtime remains the baseline;
the neutral runtime owns normalization, durable replay and approval decisions.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

from amplifier_app_tui.kernel import events as client_events
from amplifier_app_tui.kernel.approval import ApprovalBroker, DENY
from amplifier_app_tui.kernel.jsonl import JsonlRecords
from amplifier_app_tui.kernel.persistence import SessionStore
from amplifier_app_tui.kernel.serve import _history_replay_records
from amplifier_app_tui.ui.runtime_adapter import RuntimeAdapter
from amplifier_runtime.kernel import events as owner_events


def test_normalized_owner_events_rehydrate_as_the_clients_existing_types() -> None:
    """No raw-hook renormalization or cross-namespace isinstance assumption."""
    factory = JsonlRecords()
    adapter = RuntimeAdapter()
    events = [
        owner_events.StreamBlockDelta(event_id="live", session_id="fictional", text="draft"),
        owner_events.ContentBlockEnd(
            event_id="durable", session_id="fictional", block={"text": "final"}
        ),
        owner_events.ToolPre(event_id="A", tool_name="same-tool", tool_call_id="call-A"),
        owner_events.ToolPre(event_id="B", tool_name="same-tool", tool_call_id="call-B"),
        owner_events.OrchestratorComplete(event_id="cancel", status="cancelled"),
    ]
    for event in events:
        wire = factory.runtime_event(event.model_dump(mode="json")).model_dump(mode="json")
        adapter.queue.put_nowait(client_events.parse_event(wire["event"]))
    actual = [adapter.queue.get_nowait() for _ in events]
    assert isinstance(actual[0], client_events.StreamBlockDelta)
    assert isinstance(actual[1], client_events.ContentBlockEnd)
    assert actual[2].tool_call_id != actual[3].tool_call_id
    assert actual[4].status == "cancelled"


@pytest.mark.asyncio
async def test_approval_ticket_survives_other_events_and_runtime_rejects_invalid_choice() -> None:
    broker = ApprovalBroker()
    task = asyncio.create_task(broker.request_approval("Fictional request"))
    await asyncio.sleep(0)
    ticket = broker.head
    assert ticket is not None
    parsed = client_events.parse_event(
        owner_events.StreamBlockDelta(text="later text").model_dump(mode="json")
    )
    assert parsed.kind == "stream_block_delta" and broker.head is ticket
    with pytest.raises(ValueError):
        broker.answer(ticket.ticket_id, "invented approval")
    assert not task.done()
    broker.answer(ticket.ticket_id, DENY)
    assert await task == DENY and broker.head is None
    with pytest.raises(KeyError):
        broker.answer(ticket.ticket_id, DENY)


def test_reconnect_uses_durable_cursor_and_keeps_the_real_store_unchanged(tmp_path: Path) -> None:
    store = SessionStore(base_dir=tmp_path / "sessions")
    sid = "fictional-contract"
    first = client_events.ContentBlockEnd(
        event_id="durable-1", session_id=sid, block={"text": "final"}
    )
    second = client_events.OrchestratorComplete(
        event_id="durable-2", session_id=sid, status="cancelled"
    )
    store.append_event(sid, first)
    store.append_event(sid, second)
    log = store.session_dir(sid) / "ui-events.jsonl"
    before = hashlib.sha256(log.read_bytes()).hexdigest()
    runtime = SimpleNamespace(store=store, session_id=sid, restored_history=())
    replay = _history_replay_records(runtime, {"since": 1})
    data = [r for r in replay if r["type"] == "runtime.event"]
    assert len(data) == 1 and data[0]["replay"] is True
    assert client_events.parse_event(data[0]["event"]).event_id == "durable-2"
    assert next(r for r in replay if r["type"] == "history.end")["cursor"] == 2
    # A live transport's sequence is not the durable replay cursor.
    stale = _history_replay_records(runtime, {"since": 900})
    assert next(r for r in stale if r["type"] == "history.end")["cursor"] == 2
    assert hashlib.sha256(log.read_bytes()).hexdigest() == before


@pytest.mark.parametrize("candidate", [False, True], ids=["locked-runtime", "candidate-runtime"])
def test_compatibility_imports_and_event_behavior_work_without_inert_copies(
    tmp_path: Path, candidate: bool
) -> None:
    """Kernel/model retain only their shims; actual client files stay intact."""
    root = Path(__file__).resolve().parents[1] / "src/amplifier_app_tui"
    package = tmp_path / "amplifier_app_tui"
    shutil.copytree(
        root,
        package,
        ignore=lambda path, names: [
            name
            for name in names
            if name == "__pycache__" or (Path(path) == root and name in {"kernel", "model"})
        ],
    )
    for layer in ["kernel", "model"]:
        (package / layer).mkdir()
        shutil.copy2(root / layer / "__init__.py", package / layer / "__init__.py")
    program = """
import json
from importlib.util import find_spec
from pathlib import Path
import amplifier_runtime, amplifier_app_tui
from amplifier_app_tui.kernel.events import StreamBlockDelta, ContentBlockEnd, parse_event
from amplifier_app_tui.kernel.jsonl import JsonlRecords
owner=Path(amplifier_runtime.__file__).resolve().parent
assert Path(amplifier_app_tui.__file__).resolve().parent==Path.cwd()/'amplifier_app_tui'
count=0
for layer in ('kernel','model'):
 for file in (owner/layer).rglob('*.py'):
  relative=file.relative_to(owner/layer)
  if relative==Path('__init__.py'):continue
  parts=relative.parent.parts if relative.name=='__init__.py'else relative.with_suffix('').parts
  spec=find_spec('.'.join(('amplifier_app_tui',layer,*parts)))
  assert spec and spec.origin and Path(spec.origin).resolve().is_relative_to(owner/layer)
  count+=1
factory=JsonlRecords()
for event in [StreamBlockDelta(text='draft'),ContentBlockEnd(block={'text':'final'})]:
 wire=factory.runtime_event(event).model_dump(mode='json')
 assert type(parse_event(wire['event']))is type(event)
print(json.dumps({'resolved_runtime_modules':count,'copied_module_bodies':0,'behavior':'stream and durable types retained'}))
"""
    paths = [str(tmp_path)]
    if candidate:
        source = Path(
            os.environ.get(
                "AMPLIFIER_RUNTIME_SOURCE", str(root.parents[2] / "amplifier-runtime/src")
            )
        )
        if not (source / "amplifier_runtime").is_dir():
            pytest.skip("Optional candidate runtime checkout not supplied")
        paths.append(str(source))
    result = subprocess.run(
        [sys.executable, "-c", program],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": os.pathsep.join(paths)},
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    assert observed["resolved_runtime_modules"] >= 86 and observed["copied_module_bodies"] == 0
