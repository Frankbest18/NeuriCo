from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import yaml

from core.hitl_manager_context import HitlManagerTranscript
from core.hitl_manager_react import HitlManager
from core.hitl_mode import HitlMode
from core.hitl_paths import hitl_manager_dir
from core.hitl_runtime_state import HitlRuntimeState


def idea():
    return {"idea": {
        "title": "Task", "hypothesis": "A shortened task...",
        "background": {"description": "Investigate.\n" * 1000 + "Preserve the final required output."},
        "constraints": {"custom": "Keep this constraint"},
        "metadata": {"source_path": "/host/private/input.yaml"},
        "local_resources": {"datasets": [{"path": "datasets/local/data", "source_path": "/host/data"}]},
    }}


def manager(workspace, mode="full", tokens=300_000):
    value = HitlManager.__new__(HitlManager)
    value.runtime_state = HitlRuntimeState(workspace)
    value.work_dir = workspace
    value.world_model = SimpleNamespace(reconcile=lambda research: None)
    value.research = SimpleNamespace(digest_section=lambda: "Worker incorrectly says output is optional.")
    value.conversation = HitlManagerTranscript(hitl_manager_dir(workspace), context_tokens=tokens)
    value._current_hitl_mode = lambda: HitlMode(mode)
    value._runtime_tool_boundary_instruction = lambda tools: "Existing tool boundary"
    value._summarize = Mock(return_value="Earlier conversation summary")
    return value


def task_from(messages):
    message = next(m for m in messages if m["content"].startswith("User-provided research task"))
    assert message["role"] == "user"
    return yaml.safe_load(message["content"].split("\n\n", 1)[1])


def test_binding_preserves_full_task_and_caller(tmp_path):
    source = idea()
    original = deepcopy(source)
    state = HitlRuntimeState(tmp_path)
    bound = state.bind_task_context(source)
    assert source == original
    assert bound["idea"]["background"] == source["idea"]["background"]
    assert bound["idea"]["constraints"] == source["idea"]["constraints"]
    assert "source_path" not in bound["idea"]["metadata"]
    assert bound["idea"]["local_resources"]["datasets"] == [{"path": "datasets/local/data"}]
    bound["idea"]["title"] = "mutated returned copy"
    assert state.task_context()["idea"]["title"] == "Task"
    assert state.bind_task_context({"idea": {"title": "Candidate"}}) == state.task_context()
    assert HitlRuntimeState(tmp_path).task_context() == state.task_context()


@pytest.mark.parametrize("mode", ["full", "auto"])
def test_manager_receives_task_outside_history_after_compaction_and_restart(tmp_path, mode):
    value = manager(tmp_path, mode, tokens=4000)
    bound = value.runtime_state.bind_task_context(idea())
    for i in range(16):
        value.conversation.append("human", f"Discussion {i}: " + "history " * 400)
    prepare = value.conversation.prepare
    value.conversation.prepare = Mock(wraps=prepare)
    messages = value._messages(0, [])
    assert task_from(messages) == bound
    assert value._summarize.called
    assert value.conversation.prepare.call_args.kwargs["fixed_context_tokens"] > 3000
    assert "Preserve the final required output" not in messages[-1]["content"]
    assert task_from(manager(tmp_path, mode)._messages(0, [])) == bound


def test_preparation_refreshes_but_preserves_held_review(tmp_path):
    state = HitlRuntimeState(tmp_path)
    state.bind_task_context({"idea": {"title": "Pre-start"}})
    prepared = state.bind_task_context(idea(), prepare_run=True)
    with state._locked():
        state._state["pending_worker_command"] = {"status": "pending"}
        state._save_unlocked()
    assert state.bind_task_context({"idea": {"title": "Changed"}}, prepare_run=True) == prepared


def test_legacy_manager_can_open_without_task(tmp_path):
    messages = manager(tmp_path)._messages(0, [])
    assert any("no saved user-provided task context" in m["content"] for m in messages)
