"""Offline contract for the recursive Anchors source lock."""

from __future__ import annotations

from amplifier_app_tui.kernel.source_lock import (
    LOCKED_GIT_REFS,
    is_floating_git_uri,
    pin_git_uri,
    pin_mount_plan_sources,
    unlocked_floating_git_uris,
)


CONTEXT_SIMPLE_REPOSITORY = "git+https://github.com/microsoft/amplifier-module-context-simple"
STICKY_COMPACTION_FIX = "a2a098bd21dc4c11e177bb66d3c86f380f77457a"


def test_context_simple_lock_contains_sticky_total_token_compaction_fix() -> None:
    """Do not regress to the pre-fix compactor that repeatedly stalled at L1."""
    assert LOCKED_GIT_REFS[CONTEXT_SIMPLE_REPOSITORY] == STICKY_COMPACTION_FIX
    assert pin_git_uri(f"{CONTEXT_SIMPLE_REPOSITORY}@main") == (
        f"{CONTEXT_SIMPLE_REPOSITORY}@{STICKY_COMPACTION_FIX}"
    )


def test_pin_git_uri_preserves_fragment_and_leaves_unrelated_sources_alone() -> None:
    repository = "git+https://github.com/microsoft/amplifier-module-tool-bash"
    expected = LOCKED_GIT_REFS[repository]
    assert (
        pin_git_uri(f"{repository}@main#subdirectory=modules/tool-bash")
        == f"{repository}@{expected}#subdirectory=modules/tool-bash"
    )
    unknown = "git+https://github.com/example/user-bundle@main"
    assert pin_git_uri(unknown) == unknown
    assert is_floating_git_uri(unknown)


def test_mount_plan_policy_pins_module_and_nested_config_sources() -> None:
    module_repo = "git+https://github.com/microsoft/amplifier-module-tool-bash"
    skill_repo = "git+https://github.com/microsoft/amplifier-bundle-skills"
    plan = {
        "tools": [
            {
                "module": "tool-bash",
                "source": f"{module_repo}@main",
                "config": {"skills": [f"{skill_repo}@main#subdirectory=skills"]},
            }
        ]
    }

    pin_mount_plan_sources(plan, lambda _module, source: pin_git_uri(source))

    assert plan["tools"][0]["source"] == f"{module_repo}@{LOCKED_GIT_REFS[module_repo]}"
    assert plan["tools"][0]["config"]["skills"] == [
        f"{skill_repo}@{LOCKED_GIT_REFS[skill_repo]}#subdirectory=skills"
    ]
    assert unlocked_floating_git_uris(plan) == ()


def test_explicit_module_override_wins_over_the_builtin_lock() -> None:
    source = "git+https://github.com/microsoft/amplifier-module-tool-bash@main"
    plan = {"tools": [{"module": "tool-bash", "source": source}]}
    override = "file:///tmp/my-tool-bash"

    pin_mount_plan_sources(
        plan, lambda module, original: override if module == "tool-bash" else original
    )

    assert plan["tools"][0]["source"] == override


def test_unknown_float_is_reported_instead_of_misrepresented_as_locked() -> None:
    unknown = "git+https://github.com/example/new-transitive-source@dev"
    assert unlocked_floating_git_uris({"source": unknown}) == (unknown,)
