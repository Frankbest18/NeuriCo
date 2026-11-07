# Focused managed ordinary research: requirements and assumptions

Status: implemented and locally validated on 2026-11-07.

Implementation commit: `93c25f0` on `codex/focused-ordinary-assumption-guidance`.
The user subsequently authorized a fresh Harbor run after local commits;
behavioral evaluation is pending and is not implied by the local checks.

Reviewed against `harbor-focused-managed-ordinary` at `1cd0562`.

## Objective and evidence

Prevent consequential assumptions from becoming apparent task requirements
merely through handoff, approval, and repeated use in evaluation.

In the embedding-drift-monitor run, the resource finder treated the existing
biased MMD estimator as a public contract. The manager accepted the handoff,
the experiment runner restricted estimator changes, and its independently
implemented tests verified the same chosen formula. The official verifier
required unbiased MMD, producing the sole failure among eleven checks.

The visible task did not explicitly specify unbiased MMD. This is evidence of
an unsupported promotion of a design interpretation into a requirement, not
proof that the hidden estimator requirement was uniquely inferable. The fix
must improve reasoning about requirements without teaching the task's answer
or promising that this run will pass on repetition.

## Scope and implementation location

Use the existing three focused managed ordinary prompt templates and their
current rendering paths. Apply under both Auto and Full HITL wherever focused
managed ordinary research is already supported.

No new workflow stage, configuration flag, assumption registry, artifact,
approval rule, or Harbor instruction is needed. Keep existing AutoResearch,
unfocused ordinary research, and the separate interactive manager unchanged.
Leave scoring, task-context delivery, and evidence retention outside this fix.

For implementation, create a separate branch
`codex/focused-ordinary-assumption-guidance` from the reviewed adapter branch,
using a clean worktree. Recheck the base and working-tree changes first; do not
modify the unrelated dirty main checkout. This document alone can be reviewed
before creating the implementation branch.

## Prompt changes

### 1. Resource finder: formation and handoff

File: `templates/hitl/focused_managed_ordinary_resource_finder.txt`.

Keep its bootstrap/additive distinction. Add the following common paragraph
after the existing conditional, so each rendered invocation receives it once:

> Distinguish explicit task requirements from assumptions inferred from the available materials and from your own recommendations. For consequential choices, explain what supports them and what remains uncertain. Preserve these distinctions in the handoff so the next worker can assess and revise the approach.

The current generator appends this template in
`PromptGenerator.generate_resource_finder_prompt` when
`focused_managed_ordinary` is true. Reuse that path. Cover the existing
invocation branches in rendering tests without adding an additional-resource
finder capability to ordinary research.

### 2. Experiment runner: adoption and evaluation

File: `templates/hitl/focused_managed_ordinary_experiment_runner.txt`.

In the planning branch, replace the complete paragraph beginning
“Treat the resource finder's findings as inputs to your reasoning” with:

> Treat the resource finder's findings as inputs to your reasoning, not as a prescribed solution. Assess the basis of consequential assumptions and constraints before adopting them. A recommendation or prior approval does not by itself establish a task requirement. Develop, combine, or replace approaches as warranted by the task and evidence, and explain consequential choices in the plan.

For execution and review/revision, add this paragraph once per rendered prompt,
using a small condition within the existing template:

> Evaluate whether the evidence supports both the solution and the consequential assumptions behind it. Checks derived from your chosen interpretation can verify its implementation without establishing that the interpretation is appropriate. Revisit those assumptions when warranted, updating the plan through the existing workflow.

Retain the existing task objective, deliverables, and manager-feedback guidance.
The orchestrator's `_hitl_experiment_runner_source_prompt` already selects this
template for all three phases; no routing change is expected.

### 3. Manager: approval and subsequent review

File: `templates/hitl/manager_focused_managed_ordinary.txt`.

Replace the existing sentence beginning “Examine whether the
proposed solution” and ending “assumptions have been checked.” with:

> Examine whether the proposed solution is supported by reasoning and evidence, including whether consequential assumptions have been checked. Check whether consequential constraints come from the supplied task, supporting evidence, or the workers' own choices. Approval authorizes proceeding with a plan; it does not by itself validate its assumptions. At subsequent reviews, assess the work against the supplied task as well as the approved plan, and request reconsideration when a consequential assumption lacks adequate support.

Keep the surrounding objective and guidance against unnecessary comparisons.
This template is already included by `manager_review_phase_finish.txt` and
`manager_review_raised_idea.txt`, gated on focused managed ordinary mode. Reuse
those includes for resource/experiment plan and completion reviews and raised
questions.

## Approval boundaries and surrounding instructions

Read fully assembled prompts, including `worker_plan.txt`,
`worker_execution.txt`, `worker_review_revision.txt`,
`worker_escalation_policy.txt`, and `worker_terminal_contract.txt`.

Distinguish confidence in an assumption from authorization to act. The worker
may reconsider a design judgment, but must still use the existing workflow
when a revision exceeds its authority or changes approved scope, evaluation
meaning, or protected artifacts. The manager may authorize a revised approach.

Do not remove plan-completion requirements or weaken “apply only this feedback”
in revision sessions. Do not rewrite shared escalation policy as part of this
prompt correction. If rendered instructions create a concrete contradiction
that cannot be resolved within these three templates, report it before
expanding the implementation.

## Implementation sequence and commits

1. Revalidate the clean base and rendering paths. Capture representative
   pre-change rendered prompts for the affected phases and unaffected modes
   in temporary files for comparison; do not add a snapshot framework.
2. Edit the three templates above. Extend the existing focused-mode rendering
   tests and inspect full rendered prompts. Commit the prompt changes and
   their tests together as one coherent change.
3. Run the relevant existing regression suites, review the diff, and record
   commands, outcomes, and the rendering review in this document. Commit the
   completed validation record separately. Do not claim behavioral improvement
   from prompt-rendering tests.

## Verification

Extend `tests/test_focused_managed_ordinary.py` using its existing generator,
orchestrator, and manager fixtures:

- Resource finder: guidance reaches plan, execution, and review prompts;
  bootstrap and additive rendering preserve their distinct existing scope.
- Experiment runner: planning includes the requirement/assumption distinction;
  execution and review include interpretation-aware evaluation guidance.
- Manager: guidance reaches resource-finder and experiment-runner phase
  reviews and raised-idea reviews in Auto and Full HITL. Exercise the existing
  manager rendering entrypoints, not only raw template-file contents.
- Isolation: focused AutoResearch and unfocused ordinary prompts do not acquire
  the new guidance. Compare representative pre/post rendered prompts for exact
  equality in these unaffected branches.
- Retained contracts: full task context, original task objective, authority
  boundaries, mandatory artifacts, and phase-specific instructions remain
  present. Each new paragraph appears once per applicable rendered prompt.

Update existing assertions affected by deliberate wording changes. Avoid
whole-prompt golden files or tests for every sentence. Inspect the complete
rendered outputs for contradictory instructions and unnecessary repetition.

Using the existing project environment, run:

```sh
python -m pytest tests/test_focused_managed_ordinary.py tests/test_hitl_required_artifacts.py tests/test_hitl_autoresearch_review_fixes.py tests/test_scoring_conformance_report.py -q
git diff --check
```

If a test exposes a routing issue, investigate that specific path before
expanding tests or implementation. No live model call or Harbor run is required
for this implementation's local acceptance.

## Acceptance and later behavioral evaluation

Implementation is complete when all three roles receive their intended guidance
at the relevant phases, existing authority/scope boundaries remain intact,
unaffected prompt branches match the baseline, and local checks pass.

Report the changed files, validation results, and any unresolved contradiction.
Do not add task-specific estimator hints or mandate experiments for every
assumption. No benchmark rerun, push, or PR submission is part of this plan.

In a separately scheduled behavioral evaluation, inspect whether consequential
choices retain their evidential status through handoffs and manager decisions,
whether workers reconsider unsupported constraints, and whether evaluation
addresses the task interpretation. An informed decision to retain a method can
still be reasonable; selecting unbiased MMD is not itself the acceptance test
for this guidance. This inspected task can be a development diagnostic;
untouched tasks are needed to assess general benefit.

## Completed validation

- The three prompt templates were changed as specified; no runtime or shared
  escalation/approval code changed.
- Focused-mode tests: 45 passed. The full four-file suite above: 119 passed.
- Captured 54 representative prompts before and after the edit using the real
  resource generator, experiment orchestrator, and manager review entrypoints.
  All 36 unfocused ordinary/focused AutoResearch prompts were byte-identical;
  only the 18 intended focused ordinary prompts changed.
- Reviewed the rendered role guidance and surrounding planning, execution,
  revision, escalation, and terminal contracts. Reconsidering an assumption
  does not authorize bypassing manager feedback or modifying protected scope.
  No conflicting instruction requiring a shared-policy change was identified.
- Tests cover resource phases and invocation branches, runner phases, manager
  phase/raised-idea reviews under Auto and Full HITL, retained mandatory
  artifacts, and absence of duplicate guidance.
- `git diff --check` passed. Local tests establish delivery and isolation of
  the guidance; they do not establish a model-performance improvement.
