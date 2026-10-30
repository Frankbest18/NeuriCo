# Focused HITL AutoResearch Implementation Plan

## Purpose

Implement the focused workflow described in `FOCUSED_HITL_AUTORESEARCH_PROMPT_DESIGN.md` as an optional mode of HITL AutoResearch.

Focused mode changes prompt scope only:

- the initial resource finder recommends one direction;
- the rule maker creates an evaluation interface that remains valid when methods change;
- the initial experiment runner investigates the selected direction rather than implementing several directions for comparison;
- later proposals retain the existing exploitation and exploration behavior, with one modification per attempt.

The implementation must preserve all established NeuriCo workflow, authority, recovery, and scoring behavior.

## Required invariants

The following behavior must not change:

- Ordinary research;
- non-HITL AutoResearch;
- existing HITL AutoResearch when focused mode is off;
- HITL plan, execution, and review authority;
- manager approval and rerun behavior;
- idea logging and premise handling;
- proposal, verification, review, ranking, and selection;
- workspace write guards;
- checkpoint capture and restoration;
- pending-worker recovery;
- scorer and evaluator sealing;
- paper-writing availability;
- domain-specific scientific guidance.

Focused mode must not add:

- another workflow engine;
- another persistent state file;
- an idea-schema field;
- a second recovery record;
- focused copies of domain templates;
- a new proposal type;
- a new stage or worker role.

## Source of truth

Add one Boolean field to `.neurico/pipeline_state.json`:

```json
"focused_autoresearch": true
```

The rules are:

1. A new HITL AutoResearch workspace stores the requested value when its pipeline state is first created.
2. The default is `false`.
3. A missing field in an older workspace means `false`.
4. Once pipeline state exists, the value is immutable.
5. Ordinary and non-HITL workflows do not use this field.
6. Restart, continuation, retry, and rollback read the value from pipeline state.

The launch request may transport the value before pipeline creation. Launch status may display it. Neither becomes a durable authority.

Do not copy the value into `HitlRuntimeState`, `pending_worker_command`, `worker_continuation`, frontier state, checkpoint metadata, or the idea log.

## Runtime flow

The completed data flow is:

```text
CLI or browser selection
        ↓
HitlRunController launch request
        ↓
hitl_run_worker validation
        ↓
ResearchRunner.run_research
        ↓
prepare_initial_hitl_resume / run_fresh_hitl_autoresearch_initial_node
        ↓
PipelineState.focused_autoresearch
        ↓
ResearchPipelineOrchestrator prompt construction
```

After `pipeline_state.json` exists, every entry point reads the stored value. This includes an interrupted initial run that NeuriCo still labels `fresh` because no frontier has been published. The `fresh` or `continue` launch label must never determine whether focused mode may be changed.

## Implementation steps

Complete and locally verify each step before committing it. Do not begin the next step until the previous commit is complete.

### Step 1: Persist the mode and expose it through existing launch paths

#### `src/core/pipeline_orchestrator.py`

Extend `PipelineState` to accept an optional focused-mode request.

Required behavior:

- validate that the stored value is a Boolean;
- store the supplied Boolean only when creating a new HITL AutoResearch pipeline;
- interpret a missing stored value as `false`;
- reject a supplied value that conflicts with an established workspace;
- provide one read method for callers that only need the stored value;
- leave Ordinary pipeline records unchanged.

Extend `ResearchPipelineOrchestrator.__init__` with:

```python
focused_autoresearch: Optional[bool] = None
```

When `hitl_autoresearch` is true, resolve the value through `PipelineState` and retain it as `self.focused_autoresearch`. When `hitl_autoresearch` is false, focused mode must not be enabled.

#### `src/core/hitl_autoresearch.py`

Extend these functions with the optional value:

- `prepare_initial_hitl_resume`
- `run_fresh_hitl_autoresearch_initial_node`

Pass it into every `ResearchPipelineOrchestrator` construction that can create or resume the initial HITL AutoResearch pipeline.

The value must reach `prepare_initial_hitl_resume`. That function can create pipeline state before `run_fresh_hitl_autoresearch_initial_node` starts.

Later AutoResearch iterations do not need a new parameter. They read the established value when a focused prompt is needed.

#### `src/core/runner.py`

Add `focused_autoresearch: Optional[bool] = None` to `ResearchRunner.run_research`.

`None` means that the caller did not supply new configuration. A new HITL AutoResearch pipeline resolves `None` to `false`; an established pipeline resolves it from `PipelineState`. This distinction is necessary because a focused continuation must not be mistaken for an explicit request to turn focused mode off.

Validation:

- allow a supplied value only for managed HITL AutoResearch, including the run worker transporting an established value during continuation;
- reject a supplied value with Ordinary research, baseline construction, or non-HITL AutoResearch;
- when pipeline state already exists, use the stored value rather than treating the argument as new configuration.

Forward the resolved value to:

- `prepare_initial_hitl_resume`;
- `run_fresh_hitl_autoresearch_initial_node`.

Add the CLI flag:

```text
--focused-autoresearch
```

The CLI flag is valid only with `--hitl-autoresearch` before pipeline state exists. It cannot be combined with `--hitl-continue-autoresearch`. A later CLI launch reads the workspace value without requiring the flag again. The parser passes `True` when the flag is present and `None` when it is absent.

#### `src/cli/hitl_launcher.py`

In `HitlRunController.launch`:

- accept `focused_autoresearch` only as a real Boolean;
- reject it for non-AutoResearch operations;
- before pipeline state exists, place the selected value in the launch request;
- after pipeline state exists, read the stored value and place that value in the request;
- do not use the launch request's `fresh` or `continue` classification to decide whether the setting is editable.

Keep launch request version 4. The new optional key defaults to `false`, so older requests remain valid.

Include the resolved value in launch status only for display and diagnosis.

#### `src/cli/hitl_run_worker.py`

In `_load_request`:

- default a missing `focused_autoresearch` key to `false`;
- reject non-Boolean values;
- reject `true` for Ordinary research or baseline construction.

Forward the value to `ResearchRunner.run_research` for HITL AutoResearch.

Include it in the active owner and launch-status projections so the interface can show the pre-persistence value while startup is in progress. Once pipeline state exists, the live view uses pipeline state.

#### `src/core/hitl_workspace_view.py`

Expose `focused_autoresearch` in the existing live status.

Resolution order:

1. stored pipeline-state value when pipeline state exists;
2. active owner or launch status while a new pipeline is starting;
3. `false` otherwise.

`workflow_locked` remains the lock condition. A workspace with pipeline state shows the stored focus value as non-editable.

#### `src/interactive/static/hitl/hitl.js`

Add `focusedAutoresearch: false` to `runDraft`.

In the run panel:

- show a `Focused mode` checkbox only when `workflow === "autoresearch"` and baseline construction is not selected;
- before pipeline state exists, allow editing;
- after pipeline state exists, set it from `live.focused_autoresearch` and disable it;
- include `focused_autoresearch` in the AutoResearch launch payload;
- do not send it for Ordinary research or baseline construction.

Do not change paper-writing controls. Focused mode and paper writing remain independent options.

#### Step 1 local verification

Use temporary workspaces to confirm:

- a new standard HITL AutoResearch pipeline stores `false`;
- a new focused pipeline stores `true`;
- an old pipeline record without the key reads as `false`;
- an incomplete initial pipeline retains its stored value on relaunch;
- a conflicting value is rejected;
- request validation rejects strings, numbers, and null in place of a Boolean;
- the browser payload and CLI reach the same runner argument;
- Ordinary and non-HITL calls do not acquire focused configuration.

Commit this step before continuing.

### Step 2: Add shared prompt contracts and pass the mode through generators

Add three templates:

- `templates/hitl/focused_autoresearch_resource_finder.txt`
- `templates/hitl/focused_autoresearch_rule_maker.txt`
- `templates/hitl/focused_autoresearch_experiment_runner.txt`

These files are the only sources for the new role-level policy. Python code loads and appends them; it does not repeat their prose.

The resource-finder template distinguishes bootstrap from additive invocation. The experiment-runner template distinguishes execution from plan or review. The rule-maker text is identical in all three phases.

Add `focused_autoresearch: bool = False` to these existing prompt APIs:

- `PromptGenerator.generate_resource_finder_prompt`;
- `agents.resource_finder.generate_resource_finder_prompt`;
- `run_resource_finder_hitl`;
- `generate_rule_maker_prompt`;
- `PromptGenerator.generate_research_prompt`;
- `PromptGenerator.generate_session_instructions`;
- `templates.research_agent_instructions.generate_instructions`.

Pass the flag from `ResearchPipelineOrchestrator` into its existing resource-finder, rule-maker, and experiment-runner prompt call sites.

Every new parameter defaults to `false`. No existing caller is required to change unless it must produce a focused prompt.

#### Additional resource finders

In `src/core/manager_additional_agents.py`, read the stored value through `PipelineState` immediately before launching the established resource-finder lifecycle. Pass it to `run_resource_finder_hitl`.

Do not infer the value from the manager objective, proposal, idea log, launch status, or current worker.

#### Step 2 local verification

Before changing prompt text, render representative standard prompts and save their hashes locally. After flag plumbing:

- standard prompt hashes must be unchanged;
- all old calls must work without passing the new argument;
- the initial orchestrator must resolve the same value after reconstruction;
- an additional resource finder must receive the stored value;
- no focused text should appear yet.

Commit this step before continuing.

### Step 3: Apply the focused resource-finder contract

#### `templates/agents/state_contract.txt`

Add a Jinja condition around only the `DIRECTION BUDGET` section.

- standard mode renders the current section unchanged;
- focused mode omits the section wherever the shared state contract is rendered;
- the `STATE.md` handoff contract remains unchanged.

Pass `focused_autoresearch` into this rendering from both `generate_resource_finder_prompt` and `generate_session_instructions`. A focused experiment runner already receives one selected direction and must not also be told to enumerate several directions for implementation.

#### Bootstrap invocation

Append the agreed resource-finder contract after the complete resource-finder context for plan, execution, and review.

It must:

- compare plausible directions;
- recommend one direction for implementation;
- record other promising directions as deferred;
- gather resources needed for the selected direction;
- avoid treating alternative directions as required implementations or experiments.

#### Additive invocation

Retain the existing manager-supplied objective and additive-workspace restrictions.

The focused contract for an additive invocation says to support the supplied objective without reopening global direction selection. It does not select a new workspace-wide direction independently.

Do not change `max_directions` in the idea schema. It continues to govern standard mode.

#### Step 3 local verification

Render plan, execution, and review prompts for both bootstrap and additive invocations:

- standard prompts retain the current direction budget;
- focused bootstrap prompts contain the focused contract once and no direction budget;
- focused additive prompts contain the manager objective, additive restrictions, and focused additive scope once;
- user constraints and required repositories remain present;
- domain resource-finder templates remain unchanged.

Commit this step before continuing.

### Step 4: Apply the focused rule-maker contract

In `src/agents/rule_maker.py`, append the shared focused rule-maker template after the existing prompt composition when `focused_autoresearch` is true.

Apply it to plan, execution, and review.

Do not change:

- rule-maker output files;
- scoring schemas;
- evaluator ABI;
- evaluator sealing;
- conformance verification;
- domain supplements;
- artifact validation;
- manager approval.

The contract changes only the evaluation scope. It requires one stable task interface and prevents the evaluator from requiring separate implementations of every method found during resource discovery.

#### Step 4 local verification

- plan, execution, and review contain the same focused contract exactly once;
- execution still contains its domain supplement;
- plan and review remain context-only outside their established phase permissions;
- standard rule-maker prompts are byte-for-byte unchanged;
- scoring output validation remains unchanged.

Commit this step before continuing.

### Step 5: Apply the agreed experiment-runner changes

#### `templates/base/researcher.txt`

Implement only the conditional replacements recorded in the design document.

Use `focused_autoresearch` Jinja branches. The false branch must reproduce the current text and spacing.

Do not rewrite surrounding phases or restructure the template.

#### `templates/agents/session_instructions.txt`

Implement only the agreed conditional replacements recorded in the design document.

The standard branch remains the current text. Do not modify generic workflow instructions that were not reviewed.

#### Shared final scope

In `ResearchPipelineOrchestrator._hitl_experiment_runner_source_prompt`:

- execution continues to use `generate_research_prompt` followed by `generate_instructions`;
- append the focused execution contract after the complete rendered session instructions;
- plan and review continue to use `hitl/experiment_runner_context.txt`;
- append the focused plan/review scope after that existing context.

The final execution contract includes the agreed objective and this domain-compatibility sentence:

```text
When general or domain-specific instructions use novelty-oriented language,
treat them as a request to explain why the selected direction is worth
investigating, not as a requirement to invent a novel method.
```

This sentence resolves later novelty wording in domain session overrides without copying focused policy into five domain files.

Do not edit files under `templates/domains/*`.

#### Step 5 local verification

Render focused and standard execution prompts for:

- a domain that uses the generic session template;
- battery;
- finance;
- mathematics;
- mathematics with Lean;
- particle physics.

Confirm:

- standard output is unchanged;
- focused output contains each agreed replacement where the shared templates apply;
- every focused domain receives one final focused scope;
- the final scope occurs after domain guidance;
- user requirements and scoring interface remain binding;
- no focused text appears in non-HITL, Ordinary, proposer, candidate, scorer, manager, frontier, or paper-writer prompts.

Commit this step before continuing.

### Step 6: Recovery and integration verification

No recovery code should be changed in this step. Verify the new setting against the existing mechanisms.

#### Pending worker

Start a focused initial HITL phase, allow the runtime to register its worker prompt, then interrupt the process.

On restart:

- the existing worker-continuation record supplies the exact saved prompt;
- no prompt is regenerated for the pending worker;
- no focus value is added to the continuation record.

#### Stage rollback and retry

Trigger an established stage failure that causes rollback and relaunch.

Confirm:

- pipeline state retains `focused_autoresearch`;
- the stage regenerates a focused prompt from pipeline state;
- rollback does not reconstruct configuration from logs;
- no public experiment artifact becomes a configuration source.

#### Incomplete initial pipeline

Stop after pipeline state exists but before the frontier root is published. Relaunch through both browser and CLI paths.

Confirm that NeuriCo may still classify the launch as `fresh`, while focused mode remains locked to the pipeline-state value.

Commit only if production changes were required to correct a defect found here. Do not add speculative recovery code.

### Step 7: End-to-end smoke test

Run one fresh focused HITL AutoResearch workspace.

Observe the generated prompts and completed artifacts. Confirm:

1. The resource finder considers alternatives but recommends one direction.
2. Deferred directions are recorded rather than implemented.
3. The rule maker creates one method-neutral evaluation interface.
4. The experiment runner follows the selected direction.
5. Baselines, controls, and comparisons appear only when required for evaluation, improvement, or an explicit user requirement.
6. The manager can approve the completed initial node normally.
7. A later proposal may exploit the current direction or explore a different direction.
8. Candidate execution, scoring, manager selection, and frontier publication remain unchanged.
9. Paper writing remains available when selected.
10. Stop and restart retain focused mode.

Afterward, run one standard HITL AutoResearch prompt-rendering comparison to confirm that focused mode did not alter the default workflow.

## Local verification policy

Use temporary workspaces and local checks while implementing each step. Do not add permanent test files to the branch unless the user requests them. Keep temporary outputs, prompt snapshots, and smoke-test workspaces outside the commit.

Run at minimum:

- syntax and import checks for changed Python modules;
- existing focused unit subsets covering launcher, runner, prompt generation, pipeline state, workspace view, additional agents, and recovery;
- JavaScript syntax validation for the browser change;
- standard-versus-focused prompt snapshots;
- one end-to-end focused smoke test.

## Commit sequence

Use one local commit for each completed production step:

1. `Add focused AutoResearch workspace configuration`
2. `Thread focused AutoResearch through prompt generation`
3. `Focus initial AutoResearch resource selection`
4. `Keep focused AutoResearch evaluation method-neutral`
5. `Focus initial AutoResearch experiment prompts`
6. A recovery correction commit only if verification exposes a real defect

Do not combine unfinished steps in one commit. Do not proceed after a failed local check.

## Completion criteria

The implementation is complete when all of the following are true:

- focused mode is selectable from both CLI and browser for a new HITL AutoResearch workspace;
- pipeline state is the only durable configuration source;
- established workspaces cannot be reconfigured accidentally;
- every initial focused worker receives the correct phase-specific scope;
- additional resource finders honor the stored mode;
- pending-worker recovery and stage rollback behave through existing mechanisms;
- standard HITL AutoResearch prompt output is unchanged;
- Ordinary and non-HITL workflows are unchanged;
- later proposal generation and candidate execution remain unchanged;
- the focused smoke test completes through manager selection and frontier continuation.

No runtime implementation has been made as part of this plan.
