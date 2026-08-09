"""SessionSpawner tests: depth enforcement, tracker re-attachment,
cancellation linkage, approval/display inheritance, unwind-on-failure.

Fake sessions/coordinators throughout — no real amplifier-core session.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from amplifier_app_tui.kernel.spawner import (
    DEPTH_CAPABILITY,
    SPAWN_CAPABILITY,
    SessionSpawner,
    generate_sub_session_id,
)


class FakeHooks:
    def __init__(self) -> None:
        self.registered: list[str] = []
        self.unregistered: list[str] = []
        self.handlers: dict[str, list[Any]] = {}

    def register(self, event: str, handler: Any, *, priority: int = 0, name: str = "") -> Any:
        self.registered.append(event)
        self.handlers.setdefault(event, []).append(handler)

        def unregister() -> None:
            self.unregistered.append(event)
            self.handlers[event].remove(handler)

        return unregister

    async def emit(self, event: str, data: dict[str, Any]) -> None:
        for handler in list(self.handlers.get(event, ())):
            await handler(event, data)


class FakeCancellation:
    def __init__(self) -> None:
        self.children: list[Any] = []

    def register_child(self, child: Any) -> None:
        self.children.append(child)

    def unregister_child(self, child: Any) -> None:
        self.children.remove(child)


class FakeContext:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    async def add_message(self, message: dict[str, Any]) -> None:
        self.messages.append(dict(message))

    async def set_messages(self, messages: list[dict[str, Any]]) -> None:
        self.messages = [dict(m) for m in messages]


class FakeCoordinator:
    def __init__(self) -> None:
        self.hooks = FakeHooks()
        self.cancellation = FakeCancellation()
        self.capabilities: dict[str, Any] = {}
        self.approval_system = object()
        self.display_system: Any = None
        self.context = FakeContext()
        self.mounts: dict[str, Any] = {}

    def get(self, name: str) -> Any:
        if name == "hooks":
            return self.hooks
        if name == "context":
            return self.context
        return self.mounts.get(name)

    async def mount(self, mount_point: str, module: Any, name: str | None = None) -> None:
        del name
        self.mounts[mount_point] = module

    def get_capability(self, name: str) -> Any:
        return self.capabilities.get(name)

    def register_capability(self, name: str, value: Any) -> None:
        self.capabilities[name] = value


class FakeSession:
    def __init__(
        self,
        *,
        config: dict[str, Any],
        session_id: str,
        parent_id: str | None = None,
        approval_system: Any = None,
        display_system: Any = None,
        fail_execute: bool = False,
    ) -> None:
        self.config = config
        self.session_id = session_id
        self.parent_id = parent_id
        self.approval_system = approval_system
        self.display_system = display_system
        self.coordinator = FakeCoordinator()
        self.coordinator.approval_system = approval_system
        self.coordinator.display_system = display_system
        self.initialized = False
        self.executed: list[str] = []
        self.cleaned_up = False
        self._fail_execute = fail_execute

    async def initialize(self) -> None:
        self.initialized = True

    async def execute(self, instruction: str) -> str:
        self.executed.append(instruction)
        if self._fail_execute:
            raise RuntimeError("boom")
        return f"done: {instruction}"

    async def cleanup(self) -> None:
        self.cleaned_up = True


class RecordingTracker:
    def __init__(self) -> None:
        self.attached: list[Any] = []
        self.detached = 0

    def register_hooks(self, hooks: Any, *, priority: int = 50) -> Any:
        self.attached.append(hooks)

        def unregister() -> None:
            self.detached += 1

        return unregister


class FakeDisplay:
    def __init__(self) -> None:
        self.nesting = 0
        self.max_nesting = 0

    def push_nesting(self) -> None:
        self.nesting += 1
        self.max_nesting = max(self.max_nesting, self.nesting)

    def pop_nesting(self) -> None:
        self.nesting -= 1


def make_parent(session_id: str = "sess-root") -> FakeSession:
    return FakeSession(config={"providers": ["anthropic"]}, session_id=session_id)


def make_spawner(**kwargs: Any) -> tuple[SessionSpawner, list[FakeSession]]:
    created: list[FakeSession] = []
    fail_execute = kwargs.pop("fail_execute", False)

    def factory(**factory_kwargs: Any) -> FakeSession:
        session = FakeSession(**factory_kwargs, fail_execute=fail_execute)
        created.append(session)
        return session

    spawner = SessionSpawner(session_factory=factory, **kwargs)
    return spawner, created


def test_generate_sub_session_id_is_hierarchical() -> None:
    child_id = generate_sub_session_id("sess-root", "test writer")
    assert child_id.startswith("sess-root-")
    assert child_id.endswith("_test-writer")


@pytest.mark.asyncio
async def test_spawn_executes_and_returns_result_dict() -> None:
    spawner, created = make_spawner()
    parent = make_parent()
    result = await spawner.spawn("scout", "find the bug", parent)
    assert result["status"] == "success"
    assert result["output"] == "done: find the bug"
    assert result["session_id"] == created[0].session_id
    assert result["parent_id"] == "sess-root"
    child = created[0]
    assert child.initialized
    assert child.cleaned_up
    assert child.parent_id == "sess-root"


@pytest.mark.asyncio
async def test_spawn_inherits_parent_approval_and_display() -> None:
    display = FakeDisplay()
    parent = make_parent()
    parent.coordinator.display_system = display
    spawner, created = make_spawner()
    await spawner.spawn("scout", "go", parent)
    child = created[0]
    assert child.approval_system is parent.coordinator.approval_system
    assert child.display_system is display
    assert display.max_nesting == 1
    assert display.nesting == 0  # popped on unwind


@pytest.mark.asyncio
async def test_spawn_prefers_injected_approval_display() -> None:
    approval, display = object(), FakeDisplay()
    spawner, created = make_spawner(approval_system=approval, display_system=display)
    await spawner.spawn("scout", "go", make_parent())
    assert created[0].approval_system is approval
    assert created[0].display_system is display


@pytest.mark.asyncio
async def test_spawn_reattaches_trackers_and_unwinds_them() -> None:
    tracker_a, tracker_b = RecordingTracker(), RecordingTracker()
    spawner, created = make_spawner(trackers=[tracker_a, tracker_b])
    await spawner.spawn("scout", "go", make_parent())
    child_hooks = created[0].coordinator.hooks
    assert tracker_a.attached == [child_hooks]
    assert tracker_b.attached == [child_hooks]
    assert tracker_a.detached == 1
    assert tracker_b.detached == 1


@pytest.mark.asyncio
async def test_spawn_links_and_unlinks_child_cancellation() -> None:
    linked: list[Any] = []
    spawner, created = make_spawner()
    parent = make_parent()
    original_register = parent.coordinator.cancellation.register_child

    def recording_register(child: Any) -> None:
        linked.append(child)
        original_register(child)

    parent.coordinator.cancellation.register_child = recording_register  # type: ignore[method-assign]
    await spawner.spawn("scout", "go", parent)
    assert linked == [created[0].coordinator.cancellation]
    assert parent.coordinator.cancellation.children == []  # unlinked in finally


@pytest.mark.asyncio
async def test_recursion_depth_enforced_default_two() -> None:
    spawner, created = make_spawner()
    parent = make_parent()
    first = await spawner.spawn("a", "level 1", parent)
    assert first["status"] == "success"
    child = created[0]
    assert child.coordinator.capabilities[DEPTH_CAPABILITY] == 1
    assert child.coordinator.capabilities[SPAWN_CAPABILITY] == spawner.spawn

    second = await spawner.spawn("b", "level 2", child)
    assert second["status"] == "success"
    grandchild = created[1]
    assert grandchild.coordinator.capabilities[DEPTH_CAPABILITY] == 2

    third = await spawner.spawn("c", "level 3", grandchild)
    assert third["status"] == "error"
    assert "recursion depth" in third["error"]
    assert len(created) == 2  # nothing was created for the refused spawn


@pytest.mark.asyncio
async def test_execute_failure_returns_error_and_still_unwinds() -> None:
    tracker = RecordingTracker()
    display = FakeDisplay()
    spawner, created = make_spawner(trackers=[tracker], display_system=display, fail_execute=True)
    parent = make_parent()
    result = await spawner.spawn("scout", "explode", parent)
    assert result["status"] == "error"
    assert "boom" in result["output"]
    assert created[0].cleaned_up
    assert tracker.detached == 1
    assert display.nesting == 0
    assert parent.coordinator.cancellation.children == []


@pytest.mark.asyncio
async def test_agent_overlay_merges_over_parent_config() -> None:
    spawner, created = make_spawner()
    parent = make_parent()
    await spawner.spawn(
        "scout",
        "go",
        parent,
        agent_configs={"scout": {"model": "fast", "extra": True}},
    )
    config = created[0].config
    assert config["providers"] == ["anthropic"]  # inherited
    assert config["model"] == "fast"  # overlay wins


@pytest.mark.asyncio
async def test_spawn_honors_tool_delegate_contract_kwargs() -> None:
    """The exact kwargs foundation tool-delegate passes must all take
    effect: agent session overlay merges per-key (parent streaming
    orchestrator survives), orchestrator_config merges into
    session.orchestrator.config, tool/hook exclusions apply to
    inheritance only (agent declarations kept), session_metadata lands
    under session.metadata, self_delegation_depth becomes a capability.
    The parent's own config must stay untouched."""
    spawner, created = make_spawner()
    parent = FakeSession(
        config={
            "session": {
                "orchestrator": {"module": "loop-streaming", "config": {"a": 1}},
                "context": {"module": "context-parent"},
            },
            "tools": [{"module": "tool-a"}, {"module": "tool-delegate"}],
            "hooks": [{"module": "hook-a"}, {"module": "hook-b"}],
        },
        session_id="sess-root",
    )
    result = await spawner.spawn(
        agent_name="scout",
        instruction="go",
        parent_session=parent,
        agent_configs={
            "scout": {
                "session": {"context": {"module": "context-agent"}},
                "tools": [{"module": "tool-x"}],
            }
        },
        sub_session_id="sess-root-deadbeef_scout",
        tool_inheritance={"exclude_tools": ["tool-delegate"]},
        hook_inheritance={"exclude_hooks": ["hook-b"]},
        orchestrator_config={"b": 2},
        provider_preferences=None,
        self_delegation_depth=1,
        session_metadata={"agent_name": "scout", "tool_call_id": "call-1"},
    )
    assert result["status"] == "success"
    assert result["session_id"] == "sess-root-deadbeef_scout"
    config = created[0].config
    assert config["session"]["orchestrator"]["module"] == "loop-streaming"
    assert config["session"]["orchestrator"]["config"] == {"a": 1, "b": 2}
    assert config["session"]["context"] == {"module": "context-agent"}
    assert config["session"]["metadata"] == {"agent_name": "scout", "tool_call_id": "call-1"}
    assert [t["module"] for t in config["tools"]] == ["tool-a", "tool-x"]
    assert [h["module"] for h in config["hooks"]] == ["hook-a"]
    assert created[0].coordinator.capabilities["self_delegation_depth"] == 1
    # deny-and-continue semantics untouched; parent config not mutated
    assert parent.config["session"]["orchestrator"]["config"] == {"a": 1}
    assert [t["module"] for t in parent.config["tools"]] == ["tool-a", "tool-delegate"]


@pytest.mark.asyncio
async def test_spawn_keeps_agent_declared_tool_despite_exclusion() -> None:
    """tool-delegate contract: exclusions apply to INHERITANCE only —
    an agent that explicitly declares an excluded module keeps it."""
    spawner, created = make_spawner()
    parent = FakeSession(
        config={
            "session": {"orchestrator": {"module": "loop"}, "context": {"module": "ctx"}},
            "tools": [{"module": "tool-delegate"}],
        },
        session_id="sess-root",
    )
    await spawner.spawn(
        "scout",
        "go",
        parent,
        agent_configs={"scout": {"tools": [{"module": "tool-delegate"}]}},
        tool_inheritance={"exclude_tools": ["tool-delegate"]},
    )
    assert [t["module"] for t in created[0].config["tools"]] == ["tool-delegate"]


@pytest.mark.asyncio
async def test_spawn_inherits_module_resolver_and_working_dir() -> None:
    """The child mounts the parent's module-source-resolver and inherits
    session.working_dir BEFORE initialize — without the resolver a real
    child (git+/file: module sources) cannot mount its orchestrator and
    no telemetry ever fires."""
    resolver = object()
    spawner, created = make_spawner()
    parent = make_parent()
    parent.coordinator.mounts["module-source-resolver"] = resolver
    parent.coordinator.capabilities["session.working_dir"] = "/proj"
    await spawner.spawn("scout", "go", parent)
    child = created[0]
    assert child.coordinator.mounts["module-source-resolver"] is resolver
    assert child.coordinator.capabilities["session.working_dir"] == "/proj"


@pytest.mark.asyncio
async def test_spawn_seeds_agent_instruction_and_parent_messages() -> None:
    """The agent overlay's instruction (the agent .md body) becomes the
    child's system prompt; parent_messages, when a caller passes them,
    land in the child context first (reference in-process semantics)."""
    spawner, created = make_spawner()
    await spawner.spawn(
        "scout",
        "go",
        make_parent(),
        agent_configs={"scout": {"instruction": "You are scout."}},
        parent_messages=[{"role": "user", "content": "earlier context"}],
    )
    messages = created[0].coordinator.context.messages
    assert {"role": "user", "content": "earlier context"} in messages
    system = next(message["content"] for message in messages if message["role"] == "system")
    assert system == "You are scout."


@pytest.mark.asyncio
async def test_implementer_system_prompt_gets_execution_contract() -> None:
    spawner, created = make_spawner()
    await spawner.spawn(
        "superpowers:implementer",
        "go",
        make_parent(),
        agent_configs={"superpowers:implementer": {"instruction": "You implement."}},
    )
    system = next(
        message["content"]
        for message in created[0].coordinator.context.messages
        if message["role"] == "system"
    )
    assert system.startswith("You implement.")
    assert "A plan or a promise to execute is not completion" in system


@pytest.mark.asyncio
async def test_spawn_records_brief_and_result() -> None:
    """The spawner remembers the delegate brief (lane seed) and the child
    output keyed by sub-session id (AgentCompleted.result synthesis)."""
    spawner, _created = make_spawner()
    instruction = "[PARENT CONVERSATION CONTEXT]\nold\n[YOUR TASK]\nfind the bug in auth.py"
    result = await spawner.spawn("scout", instruction, make_parent())
    assert spawner.brief_for("scout") == "find the bug in auth.py"
    assert spawner.result_for(result["session_id"]).startswith("done: ")
    assert spawner.brief_for("unknown") == ""
    assert spawner.result_for("unknown") == ""


@pytest.mark.asyncio
async def test_spawn_records_failure_output_as_result() -> None:
    spawner, _created = make_spawner(fail_execute=True)
    result = await spawner.spawn("scout", "explode", make_parent())
    assert "boom" in spawner.result_for(result["session_id"])


@pytest.mark.asyncio
async def test_builder_gets_one_execution_only_retry_when_it_only_plans() -> None:
    created: list[FakeSession] = []

    class RecoveringBuilder(FakeSession):
        async def execute(self, instruction: str) -> str:
            self.executed.append(instruction)
            if len(self.executed) == 1:
                return "I have a plan and will implement it next."
            await self.coordinator.hooks.emit(
                "tool:post",
                {"tool_name": "write_file", "result": {"ok": True}},
            )
            return "Implemented and verified."

    def factory(**kwargs: Any) -> FakeSession:
        child = RecoveringBuilder(**kwargs)
        created.append(child)
        return child

    spawner = SessionSpawner(session_factory=factory)
    result = await spawner.spawn("anchors:builder", "implement the spec", make_parent())

    assert result["status"] == "success"
    assert result["output"] == "Implemented and verified."
    assert len(created[0].executed) == 2
    assert "did not run an execution tool" in created[0].executed[1]


@pytest.mark.asyncio
async def test_builder_that_still_only_plans_fails_loudly() -> None:
    spawner, created = make_spawner()
    result = await spawner.spawn("builder", "implement the spec", make_parent())

    assert result["status"] == "incomplete"
    assert "no implementation was observed" in result["output"]
    assert len(created[0].executed) == 2


@pytest.mark.asyncio
async def test_read_only_bash_does_not_count_as_builder_execution() -> None:
    created: list[FakeSession] = []

    class ReadOnlyShellBuilder(FakeSession):
        async def execute(self, instruction: str) -> str:
            self.executed.append(instruction)
            await self.coordinator.hooks.emit(
                "tool:post", {"tool_name": "bash", "result": {"output": "inspected"}}
            )
            return "I inspected it."

    def factory(**kwargs: Any) -> FakeSession:
        child = ReadOnlyShellBuilder(**kwargs)
        created.append(child)
        return child

    result = await SessionSpawner(session_factory=factory).spawn(
        "builder", "implement", make_parent()
    )
    assert result["status"] == "incomplete"
    assert len(created[0].executed) == 2


@pytest.mark.asyncio
async def test_failed_write_does_not_count_as_builder_execution() -> None:
    created: list[FakeSession] = []

    class FailedWriteBuilder(FakeSession):
        async def execute(self, instruction: str) -> str:
            self.executed.append(instruction)
            await self.coordinator.hooks.emit(
                "tool:error", {"tool_name": "write_file", "error": "denied"}
            )
            return "The write failed."

    def factory(**kwargs: Any) -> FakeSession:
        child = FailedWriteBuilder(**kwargs)
        created.append(child)
        return child

    result = await SessionSpawner(session_factory=factory).spawn(
        "builder", "implement", make_parent()
    )
    assert result["status"] == "incomplete"
    assert len(created[0].executed) == 2


@pytest.mark.asyncio
async def test_shell_created_git_diff_counts_as_builder_execution(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "test@example.invalid"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.name", "Amplifier test"], check=True
    )
    (tmp_path / "seed.txt").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "seed.txt"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-q", "-m", "seed"], check=True)
    created: list[FakeSession] = []

    class ShellEditingBuilder(FakeSession):
        async def execute(self, instruction: str) -> str:
            self.executed.append(instruction)
            (tmp_path / "generated.txt").write_text("implemented\n", encoding="utf-8")
            await self.coordinator.hooks.emit(
                "tool:post", {"tool_name": "bash", "result": {"output": "wrote file"}}
            )
            return "Implemented."

    def factory(**kwargs: Any) -> FakeSession:
        child = ShellEditingBuilder(**kwargs)
        created.append(child)
        return child

    parent = make_parent()
    parent.coordinator.capabilities["session.working_dir"] = str(tmp_path)
    result = await SessionSpawner(session_factory=factory).spawn("builder", "implement", parent)
    assert result["status"] == "success"
    assert len(created[0].executed) == 1


def test_register_installs_spawn_capability() -> None:
    spawner, _ = make_spawner()
    coordinator = FakeCoordinator()
    spawner.register(coordinator)
    assert coordinator.capabilities[SPAWN_CAPABILITY] == spawner.spawn


def test_max_depth_must_be_positive() -> None:
    with pytest.raises(ValueError):
        SessionSpawner(session_factory=lambda **kwargs: None, max_depth=0)
