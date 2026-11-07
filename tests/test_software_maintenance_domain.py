"""Opt-in software-maintenance domain prompt contracts."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from core.config_loader import ConfigLoader  # noqa: E402
from core.hitl_manager_react import HitlManager  # noqa: E402
from core.hitl_runtime_state import HitlRuntimeState  # noqa: E402
from core.pipeline_orchestrator import ResearchPipelineOrchestrator  # noqa: E402
from templates.prompt_generator import PromptGenerator  # noqa: E402

HEADING = "DOMAIN-SPECIFIC GUIDELINES: SOFTWARE MAINTENANCE"
GUIDANCE = "Establishing that an existing behavior is mathematically valid"
REVIEW_GUIDANCE = "Approval of a working interpretation does not turn it into a user requirement."
IDEA = {
    "idea": {
        "title": "Repair the supplied software",
        "domain": "software_maintenance",
        "hypothesis": "The supplied defects can be repaired and independently validated.",
        "background": {"description": "Repair the broken implementation."},
    }
}


def _ordinary(work_dir: Path, *, focused: bool = True) -> ResearchPipelineOrchestrator:
    return ResearchPipelineOrchestrator(
        work_dir=work_dir,
        templates_dir=ROOT / "templates",
        managed_initial_run=True,
        focused_autoresearch=focused,
    )


def test_domain_is_explicit_and_not_keyword_inferred():
    loader = ConfigLoader()

    assert loader.is_domain_valid("software_maintenance")
    assert loader.domain_has_template("software_maintenance")
    assert loader.get_domain_keywords("software_maintenance") == []
    assert loader.get_all_domain_keywords()["software_maintenance"] == []


def test_managed_supplement_is_opt_in_and_does_not_fallback():
    generator = PromptGenerator(ROOT / "templates")

    supplement = generator.managed_role_domain_supplement("software_maintenance")
    assert supplement.count(HEADING) == 1
    assert GUIDANCE in supplement
    assert REVIEW_GUIDANCE in supplement
    assert generator.managed_role_domain_supplement("artificial_intelligence") == ""
    assert generator.managed_role_domain_supplement("unknown-domain") == ""


@pytest.mark.parametrize("phase", ["plan", "execution", "review"])
@pytest.mark.parametrize("invocation", ["bootstrap", "additive"])
def test_resource_finder_receives_domain_once(phase, invocation):
    generator = PromptGenerator(ROOT / "templates")
    prompt = generator.generate_resource_finder_prompt(
        IDEA,
        hitl_runtime_completion=True,
        hitl_phase=phase,
        invocation_mode=invocation,
        focused_managed_ordinary=True,
    )

    assert prompt.count(HEADING) == 1
    assert prompt.count(GUIDANCE) == 1
    assert prompt.count(REVIEW_GUIDANCE) == 1

    unrelated = deepcopy(IDEA)
    unrelated["idea"]["domain"] = "artificial_intelligence"
    unrelated_prompt = generator.generate_resource_finder_prompt(
        unrelated,
        hitl_runtime_completion=True,
        hitl_phase=phase,
        invocation_mode=invocation,
        focused_managed_ordinary=True,
    )
    assert HEADING not in unrelated_prompt
    assert GUIDANCE not in unrelated_prompt


@pytest.mark.parametrize("phase", ["plan", "execution", "review"])
def test_experiment_runner_receives_domain_once(tmp_path, phase):
    orchestrator = _ordinary(tmp_path)
    prompt = orchestrator._hitl_experiment_runner_source_prompt(
        idea=IDEA,
        provider="codex",
        use_scribe=False,
        scoring_enabled=False,
        hitl_phase=phase,
        benchmark_mode=True,
    )

    assert prompt.count(HEADING) == 1
    assert prompt.count(GUIDANCE) == 1


@pytest.mark.parametrize("mode", ["auto", "full"])
@pytest.mark.parametrize("stage", ["resource_finder", "experiment_runner"])
def test_manager_finish_review_receives_bound_domain_once(tmp_path, mode, stage):
    _ordinary(tmp_path)
    HitlRuntimeState(tmp_path).bind_task_context(IDEA)
    manager = HitlManager.__new__(HitlManager)
    manager.work_dir = tmp_path
    manager.request_worker_resolution = lambda **kwargs: kwargs["prompt"]

    prompt = manager.review_phase_finish(
        pipeline_stage=stage,
        hitl_stage="execution",
        plan_text="Plan",
        finish_summary="Ready",
        related_artifacts=[],
        request_key="request-key",
        requires_human_approval=mode == "full",
        hitl_mode=mode,
    )

    assert prompt.count(HEADING) == 1
    assert prompt.count(GUIDANCE) == 1


def test_manager_raised_idea_receives_bound_domain_once(tmp_path):
    _ordinary(tmp_path)
    HitlRuntimeState(tmp_path).bind_task_context(IDEA)
    manager = HitlManager.__new__(HitlManager)
    manager.work_dir = tmp_path
    manager.request_worker_resolution = lambda **kwargs: kwargs["prompt"]

    prompt = manager.review_raised_idea(
        pipeline_stage="experiment_runner",
        raised_idea={
            "idea_type": "evidence",
            "actor": "experiment_runner",
            "hitl_stage": "execution",
        },
        plan_text="Plan",
        hitl_mode="auto",
    )

    assert prompt.count(HEADING) == 1
    assert prompt.count(GUIDANCE) == 1
    assert prompt.count(REVIEW_GUIDANCE) == 1


def test_unfocused_manager_does_not_receive_domain_supplement(tmp_path):
    _ordinary(tmp_path, focused=False)
    HitlRuntimeState(tmp_path).bind_task_context(IDEA)
    manager = HitlManager.__new__(HitlManager)
    manager.work_dir = tmp_path
    manager.request_worker_resolution = lambda **kwargs: kwargs["prompt"]

    prompt = manager.review_phase_finish(
        pipeline_stage="experiment_runner",
        hitl_stage="execution",
        plan_text="Plan",
        finish_summary="Ready",
        related_artifacts=[],
        request_key="request-key",
        requires_human_approval=False,
        hitl_mode="auto",
    )

    assert HEADING not in prompt
    assert GUIDANCE not in prompt
