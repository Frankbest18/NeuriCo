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
        assert "A source's reputation or familiarity" in prompt
        assert "establish that interpretation as fact" in prompt
        assert ("investigate their applicability before recommending one" in prompt) == (
            stage == "resource_finder" and phase in {"execution", "review"}
        )
        assert ("a successful computation under one" in prompt) == (
            stage == "experiment_runner" and phase in {"execution", "review"}
        )
        if phase in {"plan", "plan_revision"}:
            assert "The only permitted public workspace write" in prompt
            assert "Do not perform stage execution work" in prompt
        if phase == "review":
            assert "Apply only this feedback. Do not broaden" in prompt
    assert "focused checks for unresolved interpretations" in prompts["plan"]
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
    assert "a successful computation under one" in prompt
    assert "establish that interpretation as fact" in prompt
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
    assert "consider what further\ninvestigation could distinguish them" in prompt
    assert "Approval of a decision does not establish its" in prompt
    assert "CUSTOM" in prompt
    if mode == "auto":
        assert "`ask_human` is unavailable" in prompt
        assert "Do not add routing options" in prompt
    else:
        assert "preserve the worker's options exactly" in prompt
        assert "use `ask_human` inside this same request" in prompt
    system = render_hitl_template("interactive_manager_system.txt", hitl_mode=mode)
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
    assert ("do not require its\nexecution during planning" in prompt) == (phase == "plan")
    assert ("rather\n  than only by an earlier decision or approval" in prompt) == (
        phase in {"execution", "review"}
    )
    if phase != "plan":
        assert "do not require exhaustive comparisons or elimination of all uncertainty" in prompt


def test_proposal_receives_evidence_principle_without_execution_instructions():
    prompt = render_hitl_template(
        "worker_autonomous_idea_contract.txt",
        pipeline_stage="experiment_runner",
        hitl_stage="proposal",
        hitl_mode="auto",
    )
    assert "A source's reputation or familiarity" in prompt
    assert "a successful computation under one" not in prompt
    assert "hitl-submit-proposal" in prompt
