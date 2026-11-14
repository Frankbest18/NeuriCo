"""Evidence guidance follows existing managed phases and authority boundaries."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.hitl import HitlRuntime, render_hitl_template  # noqa: E402
from core.hitl_manager_react import HitlManager  # noqa: E402


@pytest.mark.parametrize("mode", ["auto", "full"])
@pytest.mark.parametrize("stage", ["resource_finder", "experiment_runner", "rule_maker"])
def test_worker_guidance_respects_phase_and_agent_scope(tmp_path, mode, stage):
    runtime = HitlRuntime(
        tmp_path, stage, channel=object(), manager=object(), hitl_mode=mode
    )
    prompts = {
        "plan": runtime.plan_prompt_block(),
        "plan_revision": runtime.plan_revision_prompt_block("Revise the assumptions."),
        "execution": runtime.execution_prompt_block(),
        "review": runtime.review_prompt_block("Check the conflicting reference."),
    }
    for phase, prompt in prompts.items():
        assert prompt.count("Treat supplied resources as evidence") == 1
        assert "supplied claim must be preserved" in prompt
        assert prompt.count("For example, algorithm A takes 10 seconds") == 1
        assert "current interpretation or an approved" in prompt
        assert "Distinguish explicit task requirements" in prompt
        assert "supports excluding the alternatives" in prompt
        assert ("Investigate resource relevance and reliability" in prompt) == (
            stage == "resource_finder" and phase in {"execution", "review"}
        )
        assert ("Run the planned investigations" in prompt) == (
            stage == "experiment_runner" and phase in {"execution", "review"}
        )
        if phase in {"plan", "plan_revision"}:
            assert "The only permitted public workspace write" in prompt
            assert "Do not perform stage execution work" in prompt
        if phase == "review":
            assert "Apply only this feedback. Do not broaden" in prompt
    assert "Planned investigations: the relevant alternatives" in prompts["plan"]
    if stage == "experiment_runner":
        assert "illegal to look for, depend on, or raise concerns" in prompts["execution"]
    if stage == "rule_maker":
        assert "It is illegal for you to read the contents" in prompts["review"]


@pytest.mark.parametrize("phase", ["execution", "review"])
def test_raised_idea_continuation_retains_guidance_and_feedback(tmp_path, phase):
    runtime = HitlRuntime(
        tmp_path, "experiment_runner", channel=object(), manager=object(), hitl_mode="auto"
    )
    runtime.current_hitl_stage = phase
    runtime._tool_context["worker_prompt_contexts"] = {phase: "Original task context"}
    runtime.register_worker_prompt("Initial prompt")
    result = runtime._normalize_raised_resolution(
        {
            "idea_id": "I1",
            "decision": "CUSTOM",
            "manager_feedback": "Compare the two reference interpretations.",
        }
    )
    prompt = result["prompt_block"]
    assert "Original task context" in prompt
    assert "Compare the two reference interpretations." in prompt
    assert "Run the planned investigations" in prompt
    assert "supports excluding the alternatives" in prompt
    assert runtime.worker_continuation()["prompt_block"] == prompt


@pytest.mark.parametrize("mode", ["auto", "full"])
@pytest.mark.parametrize("stage", ["resource_finder", "experiment_runner", "rule_maker"])
def test_manager_decision_guidance_preserves_existing_authority(tmp_path, mode, stage):
    manager = HitlManager.__new__(HitlManager)
    manager.work_dir = tmp_path
    manager.request_worker_resolution = lambda **kwargs: kwargs["prompt"]
    prompt = manager.review_raised_idea(
        pipeline_stage=stage,
        raised_idea={"actor": stage, "hitl_stage": "execution"},
        plan_text="Existing approved scope",
        hitl_mode=mode,
    )
    assert "Check whether the worker's options include the consequential alternatives" in prompt
    assert "task requirement or an approved choice as established fact" in prompt
    assert "use CUSTOM feedback to direct a comparison" in prompt
    assert "CUSTOM" in prompt
    if mode == "auto":
        assert "`ask_human` is unavailable" in prompt
        assert "Do not add routing options" in prompt
        assert "assumption within that scope is permitted" in prompt
    else:
        assert "preserve the worker's options exactly" in prompt
        assert "use `ask_human` inside this same request" in prompt
    system = render_hitl_template("interactive_manager_system.txt", hitl_mode=mode)
    assert system.count("Treat supplied resources as evidence") == 1
    assert "supplied claim must be preserved" in system
    assert "resolve blocking worker requests only when the issue is actually resolved" in system


@pytest.mark.parametrize("phase", ["plan", "execution", "review"])
@pytest.mark.parametrize("stage", ["resource_finder", "experiment_runner", "rule_maker"])
def test_manager_reviews_investigations_at_the_correct_phase(tmp_path, phase, stage):
    manager = HitlManager.__new__(HitlManager)
    manager.work_dir = tmp_path
    manager.request_worker_resolution = lambda **kwargs: kwargs["prompt"]
    prompt = manager.review_phase_finish(
        pipeline_stage=stage,
        hitl_stage=phase,
        plan_text="Plan",
        finish_summary="Ready",
        related_artifacts=[],
        request_key="review",
        requires_human_approval=False,
        hitl_mode="auto",
    )
    assert ("Assess the plan without requiring execution during planning" in prompt) == (phase == "plan")
    assert ("Check whether the evidence supports the delivered work" in prompt) == (
        phase in {"execution", "review"}
    )
    if phase != "plan":
        assert "A manager-approved deviation does not make an unmet requirement" in prompt
    assert "do not require exhaustive comparisons" not in prompt


def test_proposal_receives_evidence_principle_without_execution_instructions():
    prompt = render_hitl_template(
        "worker_autonomous_idea_contract.txt",
        pipeline_stage="experiment_runner",
        hitl_stage="proposal",
        hitl_mode="auto",
    )
    assert "Distinguish explicit task requirements" in prompt
    assert "Run the planned investigations" not in prompt
    assert "hitl-submit-proposal" in prompt
