# Focused HITL AutoResearch Prompt Design

## Status

This is the living design record for the focused HITL AutoResearch prompt update. It records decisions that have been agreed upon and questions that still require discussion. Update this document as those questions are resolved.

No implementation has been approved or made yet.

## Scope

Focused AutoResearch is an optional mode of HITL AutoResearch. It uses NeuriCo's existing stages, HITL plan-execution-review workflow, scoring system, checkpoints, proposals, and paper-writing option.

The mode changes the research scope expressed in prompts. It does not replace NeuriCo's workflow.

Standard research, existing HITL AutoResearch when focused mode is disabled, and non-HITL AutoResearch retain their current behavior.

## Goal

Focused mode should pursue the best solution while investigating one research direction at a time.

Resource finding may compare several possible directions before recommending one. The initial experiment implements and investigates the selected direction. Later proposals may either improve the current direction or test a different direction, but each attempt implements only one direction.

A baseline, comparison, control, or ablation is allowed when it is needed to evaluate the selected direction or is explicitly required by the user. It should not become mandatory merely because it appeared in the literature review or resource-finder shortlist.

## Agreed design

### Optional mode

Focused mode is optional. Existing AutoResearch behavior remains available when the mode is disabled.

Paper writing remains available in focused mode. The first version will use the existing paper writer. Focused paper-writing improvements may be added later after focused-mode runs provide evidence about what is missing.

### Resource-finder direction selection

For the initial focused HITL AutoResearch resource finder, replace the existing direction-budget paragraph with:

```text
Compare plausible research directions using the available evidence,
relevance to the research objective, potential for improvement, and
implementation feasibility. Select one direction to recommend for
implementation and experimentation. Explain the choice and record other
promising directions as deferred possibilities in the existing planning
and handoff documents.

Gather the resources needed to pursue the selected direction. Considering
other directions does not require implementing or experimentally comparing
them.
```

The resource finder recommends one direction. It does not implement or experimentally compare the alternatives.

### Initial experiment-runner direction scope

For the initial focused HITL AutoResearch experiment runner, use this direction instruction:

```text
Pursue the strongest valid solution within the direction selected in the
approved plan and the available resources. Implement and investigate that
direction only. Run supporting comparisons or controls when needed to
evaluate or improve it; do not develop deferred alternatives in this
invocation.
```

The experiment runner follows the approved direction rather than reopening direction selection.

### Rule-maker contract

The focused-mode rule maker receives this instruction during plan, execution, and review:

```text
The research objective is to find the best solution to the task. Each
experiment investigates one direction, which may use a different method
from previous experiments. The evaluation must remain applicable when
the method changes.

Define the required outputs and evaluate how well they satisfy the task.
Do not require outputs from several competing methods in each experiment.
The methods identified during resource finding are possible approaches,
not a list of implementations the experiment runner must produce.

Preserve the user's explicit requirements, including any required method,
comparison, or output.
```

The scoring schemas and established rule-maker responsibilities remain unchanged.

### Initial experiment-runner objective

The focused-mode initial experiment runner receives this research objective:

```text
Your objective is to produce the best solution you can within the selected
research direction, the task constraints, and the available resources.

Read the approved plan, the gathered resources, and scoring/interface.md.
Use the available code and data to implement the selected direction.
Improve the implementation and investigate problems that limit its quality.

Each experiment should help develop or evaluate this direction. Run
comparisons, controls, or ablations when they answer a concrete question
about its correctness, effectiveness, or limitations. Do not implement
other research directions merely to complete a comparison of methods.

Produce the artifacts required by scoring/interface.md. Preserve the
user's explicit requirements and the approved scope of work.
```

The existing six-phase experiment structure remains. Environment setup, implementation, testing, analysis, documentation, and HITL plan-execution-review controls are retained. Focused mode makes small conditional changes to instructions that conflict with investigating one direction at a time.

### Baseline implementation

In focused mode, replace the unconditional instruction to implement baselines first with:

```text
✓ Implement a baseline only when needed to evaluate the selected direction
  or when explicitly required by the user. Reuse an existing baseline
  where available.
```

### Baseline planning

In focused mode, replace the instruction to choose baselines and metrics from the literature review with:

```text
✓ Use the evaluation requirements in scoring/interface.md. Include
  baseline work in the plan only when needed to evaluate the selected direction
  or when explicitly required by the user. Reuse an existing baseline
  where available.
```

The rule maker has already defined the evaluation contract, so the experiment runner uses that contract rather than selecting new metrics.

### Baseline experiments

In focused mode, replace the unconditional instruction to run baseline experiments with:

```text
✓ Run baseline experiments only when needed to evaluate the selected
  direction or when explicitly required by the user. Reuse existing
  results when they remain valid for the comparison.
```

### Use of existing results and literature during analysis

Only in focused HITL AutoResearch, replace `✓ Compare against baselines and literature` in `templates/agents/session_instructions.txt` with:

```text
✓ Consult existing results or literature when they help identify
  weaknesses or guide improvements to the selected direction.
```

This does not require a routine comparison with baselines or literature. Evaluation against the task requirements is already covered by the existing evaluation instructions.

### Visualizations during analysis

Only in focused HITL AutoResearch, replace `✓ Create comprehensive visualizations` in `templates/agents/session_instructions.txt` with:

```text
✓ Create visualizations when they help interpret results or diagnose problems.
```

Useful visual analysis remains available without requiring a comprehensive set of figures.

### Figures and tables in REPORT.md

Only in focused HITL AutoResearch, replace `Include key visualizations/tables inline (as markdown).` in `templates/agents/session_instructions.txt` with:

```text
Include figures or tables inline (as markdown) when they help explain
the findings.
```

This keeps report presentation consistent with the agreed visualization instruction.

### REPORT.md scope

Only in focused HITL AutoResearch, replace `1. REPORT.md - Comprehensive research report containing:` in `templates/agents/session_instructions.txt` with:

```text
1. REPORT.md - Comprehensive technical record of the selected directions, containing:
```

Focused scope does not require less thorough documentation. This replacement does not change the existing section structure.

### Literature summary in REPORT.md

Only in focused HITL AutoResearch, replace `- Literature Review Summary (key papers and insights from Phase 0)` in `templates/agents/session_instructions.txt` with:

```text
- Literature Review Summary (key papers and insights that informed the
  selected directions)
```

### Datasets and baselines in the researcher prompt

Only in focused HITL AutoResearch, replace `- Use datasets and baselines identified in resources.md` in `templates/base/researcher.txt` with:

```text
- Use relevant datasets identified in resources.md. Include baseline work
  only when needed to evaluate the selected direction or when explicitly
  required by the user. Reuse existing baselines where available.
```

This applies the agreed baseline policy consistently across the researcher prompt and session instructions.

### Baselines in the planning outline

Only in focused HITL AutoResearch, replace the baseline section in the planning outline in `templates/base/researcher.txt`:

```text
### Baselines
[What will you compare against and why?]
```

with:

```text
### Baselines
[Which baselines, if any, are needed to evaluate or support the selected direction
or explicitly required by the user? Explain why.]
```

### Comparison tables in the researcher prompt

Only in focused HITL AutoResearch, replace `- Tables comparing methods, conditions, or systems` in `templates/base/researcher.txt` with:

```text
- Tables comparing methods, conditions, or systems when they help explain the findings
```

### Evaluation metrics in the researcher planning outline

Only in focused HITL AutoResearch, replace `[How will you measure success? Why these metrics?]` in `templates/base/researcher.txt` with:

```text
[Use the evaluation requirements in scoring/interface.md.
Explain how the planned experiments address them.]
```

### Baseline implementation in the researcher prompt

Only in focused HITL AutoResearch, replace `✓ Implement reference methods or baselines first (if applicable)` in `templates/base/researcher.txt` with:

```text
✓ Implement reference methods or baselines only when needed to evaluate
  or support the selected direction or when explicitly required by the
  user. Reuse existing implementations where available.
```

### Baseline comparisons in the researcher prompt

Only in focused HITL AutoResearch, replace `- Compare against all baselines` in `templates/base/researcher.txt` with:

```text
- Compare against baselines only when needed to evaluate or improve
  the selected direction or when explicitly required by the user.
```

### Report introduction in the researcher prompt

Only in focused HITL AutoResearch, replace `This is the primary research report. Include these sections:` in `templates/base/researcher.txt` with:

```text
This is a comprehensive technical record of the selected directions.
Include these sections:
```

### Supporting evidence in the researcher report

Keep the existing instruction in `templates/base/researcher.txt` unchanged, including in focused HITL AutoResearch:

```text
- Key findings with supporting data and figures
```

The proposed replacement making figures explicitly conditional in this sentence was not adopted.

### Visualization generation during experiments

Only in focused HITL AutoResearch, replace `✓ Generate visualizations` in `templates/agents/session_instructions.txt` with:

```text
✓ Generate visualizations when they help interpret results or diagnose problems.
```

### Analysis completion in the researcher prompt

Only in focused HITL AutoResearch, replace `✓ Verify your analysis is complete with statistical tests and visualizations` in `templates/base/researcher.txt` with:

```text
✓ Verify your analysis is complete, using statistical tests where appropriate
  and visualizations when they help interpret results or diagnose problems.
```

### Figure presentation in the researcher report

Only in focused HITL AutoResearch, replace `- Visualizations with clear labels, units, and legends` in `templates/base/researcher.txt` with:

```text
- When including visualizations, use clear labels, units, and legends
```

### Comparisons in the researcher report discussion

Only in focused HITL AutoResearch, replace `- Comparison to baselines, prior work, or literature values` in `templates/base/researcher.txt` with:

```text
- Comparisons to baselines, prior work, or literature values when they
  help explain the findings or guide improvements
```

### Initial assessment heading

Only in focused HITL AutoResearch, replace `PHASE 0: MOTIVATION & NOVELTY ASSESSMENT (CRITICAL - DO NOT SKIP)` in `templates/base/researcher.txt` with:

```text
PHASE 0: MOTIVATION & APPROACH RATIONALE (CRITICAL - DO NOT SKIP)
```

### Initial assessment questions

Only in focused HITL AutoResearch, replace this part of `templates/base/researcher.txt`:

```text
2. WHAT Makes It Novel
   - How does this differ from existing work?
   - What gap in the literature does it fill?
   - What new insight or method does it contribute?
```

with:

```text
2. WHY Pursue the Selected Direction
   - How could it improve the solution to the task?
   - What evidence supports this approach?
   - What assumptions or limitations need investigation?
```

### Initial assessment record

Only in focused HITL AutoResearch, replace this part of `templates/base/researcher.txt`:

```text
DELIVERABLE: Add a "Motivation & Novelty" section to planning.md:

## Motivation & Novelty Assessment

### Why This Research Matters
[2-3 sentences on importance and impact]

### Gap in Existing Work
[Based on literature_review.md, what's missing?]

### Our Novel Contribution
[What new thing are we testing/proposing?]
```

with:

```text
DELIVERABLE: Add a "Motivation & Approach Rationale" section to planning.md:

## Motivation & Approach Rationale

### Why This Research Matters
[2-3 sentences on importance and impact]

### Evidence for the Selected Direction
[What evidence supports pursuing this approach?]

### Assumptions and Limitations
[What needs investigation to determine whether this approach works?]
```

The following experiment-justification instructions remain unchanged.

### Initial assessment completion reminder

Only in focused HITL AutoResearch, replace `✓ You have identified WHAT makes it novel` in `templates/base/researcher.txt` with:

```text
✓ You have explained WHY the selected direction is worth investigating
```

### Initial assessment in the session instructions

Only in focused HITL AutoResearch, replace this part of `templates/agents/session_instructions.txt`:

```text
✓ FIRST: Write "Motivation & Novelty Assessment" section in planning.md
  - Why this research matters (problem and impact)
  - What gap it fills (based on literature review)
  - Why each experiment is necessary
```

with:

```text
✓ FIRST: Write "Motivation & Approach Rationale" section in planning.md
  - Why this research matters (problem and impact)
  - What evidence supports the selected direction and what assumptions
    or limitations need investigation
  - Why each experiment is necessary
```

These changes retain the assessment and its place in the existing structure. The selected direction must have a reason to be investigated, but need not introduce a novel method.

### Later proposals

Each later proposal contains one focused experiment-stage modification. It may be:

- exploitation that improves the current direction; or
- exploration that tests a different direction.

Only one direction is implemented in an attempt. Reuse NeuriCo's existing exploration/exploitation proposal mechanism rather than adding another proposal type or field.

### Paper writing in the first version

Focused mode allows the existing optional paper-writing stage. The first version does not change the paper writer.

The experiment runner should not broaden an experiment solely to fill out a conventional paper. The existing paper writer will write from the evidence that focused AutoResearch produced. Its current requirement that claims be supported by experimental evidence remains the basic protection against unsupported claims.

Improving the paper writer for focused evidence is deferred. Likely future work includes framing narrower contributions, handling evidence accumulated across accepted rounds, and avoiding assumptions that every paper has a broad baseline or ablation suite.

## Changes intentionally outside this work

- The generic non-HITL `comment_handler` prompt is outside this work.
- Standard NeuriCo research prompts are not being redesigned.
- Existing non-focused HITL AutoResearch behavior is preserved.
- Verifier, reviewer, manager-selection, frontier-decision, scoring-result, and paper-writer behavior are not being redesigned in the first version.
- NeuriCo's runtime stages, HITL authority model, checkpoints, rollback, scoring schemas, and proposal lifecycle remain in place.

## Remaining design and implementation scope

### Minimal remaining implementation design

The prompt audit found no need for further sentence-by-sentence changes. The remaining work is to place the agreed contracts consistently and expose the optional mode through NeuriCo's established run configuration.

The initial resource finder must receive the agreed resource-finder direction contract in plan, execution, and review. For a bootstrap invocation, it compares possible directions and selects one. An additive resource-finder invocation has an existing manager-supplied objective and must support that objective without reopening direction selection. The existing `max_directions` field remains unchanged for standard research and non-focused AutoResearch. Focused mode does not use it to carry several directions into implementation.

The rule maker must receive the agreed focused rule-maker contract in plan, execution, and review. The same text is reused in all three phases; no second rule-maker policy is introduced.

The initial experiment runner receives the agreed detailed objective in execution and the agreed concise direction scope in plan and review. In execution, the detailed objective must be composed after the base and domain research guidance so it remains the controlling scope when a domain template contains broader baseline, comparison, robustness, or publication guidance. The reviewed conditional sentence replacements remain part of the focused rendering.

Domain templates are not edited individually. Their scientific requirements remain useful. The shared focused experiment-runner objective limits how those requirements are applied: additional methods, baselines, comparisons, or presentation work are performed only when they support evaluation or improvement of the selected direction or are explicitly required by the user.

The AutoResearch proposer does not require a focused-mode change. Its existing output contract already requires one concrete modification for one targeted pass, and its existing HITL submission contract already distinguishes exploitation from exploration. `Expected artifacts to update` also remains unchanged; it asks the proposer to name affected artifacts without requiring manuscript work.

The candidate worker, scorer, manager, frontier decision, verifier and reviewer mechanisms do not require prompt or runtime changes for focused mode. Candidate execution already follows the admitted proposal and the existing experiment boundary.

The remaining `REPORT.md` structure stays unchanged beyond the wording already agreed above. The existing paper writer also remains unchanged in the first version.

### Focused-mode configuration and persistence

Focused mode is a launch-level option for HITL AutoResearch, not a property of the submitted research idea. It should therefore not be added to `ideas/schema.yaml` or copied into the idea record.

The existing behavior is the default. A fresh HITL AutoResearch run may select focused mode through both the CLI and browser setup. Once the initial workspace pipeline is created, that selection is stored with the workspace's existing pipeline workflow state and becomes the single source of truth for every later launch, including restart and continuation. The interface reads the stored value rather than asking the user to choose again.

The launch request carries the selection only until the run process adopts it into workspace state. The browser reads the stored value through the existing live workspace view and treats it as locked for an established workspace. This follows the current Ordinary-versus-AutoResearch workflow policy and avoids a second configuration store.

### Conditional prompt composition

The implementation should pass one focused-mode flag through the existing prompt generators. Existing templates render exactly as they do now when the flag is false.

The agreed resource-finder, rule-maker, and experiment-runner contracts are the role-level sources of truth. They are reused at the existing plan, execution, and review composition points. Domain prompt files are not forked or copied for focused mode.

## Implementation design based on the current code

### What the current implementation already provides

Focused mode does not need a new workflow, stage, agent type, checkpoint, or recovery system.

NeuriCo already provides the required structure:

- `PipelineState` owns durable workspace workflow state in `.neurico/pipeline_state.json`.
- `HitlRunController` and `hitl_run_worker.py` carry fresh launch settings from both browser and CLI entry points into `ResearchRunner`.
- `ResearchPipelineOrchestrator` constructs the resource-finder, rule-maker, and experiment-runner prompts for the existing plan, execution, and review lifecycle.
- `run_plan_centered_hitl_stage` preserves the exact prompt for an interrupted worker in the existing worker-continuation record.
- Stage retry and rollback reconstruct new work from the same workspace pipeline state.
- The browser already locks the Ordinary-versus-AutoResearch workflow after pipeline state exists and reads that state through `HitlWorkspaceView`.
- Later AutoResearch proposals already describe one targeted modification and distinguish exploitation from exploration.

The implementation should extend these points. It should not introduce another workflow state file, a focused idea field, a focused worker runtime, or focused copies of domain templates.

### One durable setting

Add one Boolean field to AutoResearch pipeline state:

```json
"focused_autoresearch": true
```

The rules for this field are:

- It is written when a fresh HITL AutoResearch pipeline is first created.
- `false` is the default for a new run when focused mode was not selected.
- A missing field means `false` for existing workspaces created before this feature.
- It is valid only for HITL AutoResearch. Ordinary research and non-HITL AutoResearch do not acquire this setting.
- Once pipeline state exists, the value cannot be changed for that workspace.
- Restart, continuation, stage retry, and rollback read this value from pipeline state.

This field belongs in `pipeline_state.json` because it changes how all three initial HITL stages are prompted and must remain stable for the lifetime of the workspace. It does not belong in the submitted idea because it is a workflow choice, not part of the research claim.

`PipelineState` should validate and expose this field. A small class method may read it for callers that do not own an orchestrator, such as an additional resource finder. No second configuration object is needed.

### Launch behavior

A fresh HITL AutoResearch launch receives a `focused_autoresearch` Boolean from the selected interface.

The CLI adds one option:

```text
--focused-autoresearch
```

It is accepted only with `--hitl-autoresearch` before that workspace has pipeline state. It is not accepted for Ordinary research, baseline construction, non-HITL AutoResearch, or as a way to reconfigure an established workspace.

The browser adds one focused-mode control beside the existing AutoResearch launch settings. The control is shown only for AutoResearch. Before pipeline creation it is editable and defaults to off. After pipeline creation it displays the stored value and is locked with the workflow.

Before pipeline state exists, the launch request carries the selected Boolean until `PipelineState` adopts it. Once pipeline state exists, `HitlRunController` reads the stored value and uses it; a request cannot replace it. The launch request and launch-status record are transport and display records, not durable configuration sources.

This decision must use the existence of `pipeline_state.json`, not the launch request's `fresh` or `continue` label. NeuriCo uses `fresh` for an incomplete initial AutoResearch pipeline that has not published its frontier yet. Such a workspace is already established for focused-mode configuration and must retain its stored value.

The request format can remain at version 4. The new key is optional and defaults to `false`, so existing requests remain valid. `hitl_run_worker.py` must still validate that the value is a Boolean before forwarding it.

### Initial pipeline construction

`ResearchRunner.run_research` receives the launch value and passes it into the two paths that can first construct the HITL AutoResearch pipeline:

- `prepare_initial_hitl_resume`
- `run_fresh_hitl_autoresearch_initial_node`

Passing it to `prepare_initial_hitl_resume` is necessary. That function can create `pipeline_state.json` before the fresh initial run begins. If the setting were supplied only to `run_fresh_hitl_autoresearch_initial_node`, the earlier call could establish the workspace with the default mode.

`ResearchPipelineOrchestrator` receives `focused_autoresearch: Optional[bool]`. For a new HITL AutoResearch workspace, the supplied Boolean is persisted by `PipelineState`. For an existing workspace, including an incomplete initial pipeline with no frontier, the orchestrator reads the stored value and rejects a conflicting supplied value. The orchestrator keeps the resolved value for prompt construction.

No focus value is added to `HitlRuntimeState`, `pending_worker_command`, `worker_continuation`, checkpoint metadata, or the frontier. Those objects already preserve either the exact active prompt or the research boundary they own. Adding the mode there would create duplicate authority.

### Recovery and rollback

The existing recovery behavior is sufficient once the setting is in pipeline state.

If a worker is interrupted, NeuriCo resumes the exact prompt stored in the existing worker-continuation record. The prompt must not be regenerated merely because the process restarted.

If a stage is rolled back and relaunched, the orchestrator regenerates the prompt using the same `focused_autoresearch` value from pipeline state.

`pipeline_state.json` is workflow state, not a public experiment artifact or an attempt-local private record. Existing stage rollback does not use logs to reconstruct it and must not be changed to do so.

### Prompt composition

Add `focused_autoresearch: bool = False` to the existing prompt construction calls. The default preserves all current callers.

The flag is threaded through:

- `PromptGenerator.generate_resource_finder_prompt`
- `agents.resource_finder.generate_resource_finder_prompt`
- `run_resource_finder_hitl`
- `generate_rule_maker_prompt`
- `PromptGenerator.generate_research_prompt`
- `PromptGenerator.generate_session_instructions`
- `templates.research_agent_instructions.generate_instructions`
- the corresponding `ResearchPipelineOrchestrator` call sites

When the flag is false, rendered prompt text must remain unchanged.

Keep the focused role contracts in three small shared HITL templates: one for resource finding, one for rule making, and one for experiment running. A role contract may select its bootstrap, additive, or HITL-phase wording inside that template. The Python code only selects and appends the contract; it does not contain a second prose version.

#### Resource finder

In focused mode, render `state_contract.txt` without its current direction-budget section. The state-handoff section remains unchanged.

For the initial bootstrap resource finder, append the agreed focused resource-finder contract after the complete research and domain context in plan, execution, and review. Appending it last makes the scope unambiguous without editing every domain template.

For an additive resource finder requested during later proposal work, keep NeuriCo's existing manager-supplied objective and additive-workspace restrictions. The focused contract tells the worker to support that objective and not reopen the initial direction-selection decision. It must not select a new global direction on its own.

The existing `max_directions` idea field and standard direction-budget behavior remain unchanged outside focused mode.

#### Rule maker

Append the single agreed rule-maker contract to the existing plan, execution, and review contexts.

Do not change the rule-maker schema, outputs, evaluator sealing, phase permissions, or domain supplements. The contract changes only how the evaluator treats alternative methods: it evaluates the task through one stable interface rather than requiring every experiment to implement several methods.

#### Experiment runner

Apply the agreed conditional replacements in `templates/base/researcher.txt` and `templates/agents/session_instructions.txt`. Use Jinja conditions so their standard rendering is unchanged.

The execution prompt is assembled from the base researcher prompt, domain core guidance, and the selected session template. Some domains replace the generic session template and contain broader comparison or publication instructions. Do not copy or edit those domain files. Append the agreed focused experiment-runner objective after the complete rendered session instructions so it is the final scope for all domains.

Plan and review do not use the full execution prompt. Append the agreed concise direction-scope instruction to their existing `hitl/experiment_runner_context.txt` rendering.

This preserves field-specific scientific requirements. It only prevents them from turning deferred methods into mandatory implementations when those methods are not needed to evaluate or improve the selected direction.

### One remaining prompt-composition decision

Five domains replace the generic session template: battery, finance, mathematics, mathematics with Lean, and particle physics. Their templates are rendered after the shared researcher prompt and repeat some broad instructions, including `Motivation & Novelty Assessment`; battery also repeats unconditional baseline implementation. Therefore the conditional replacements in `templates/agents/session_instructions.txt` do not reach those domains.

Copying the same focused conditions into five domain files would create several versions of the policy and make future changes easy to miss. Replacing the domain templates would discard useful scientific guidance.

The minimal correction is to keep the domain templates and add one sentence to the shared focused experiment-runner contract that is appended after the complete rendered session:

```text
When general or domain-specific instructions use novelty-oriented language,
treat them as a request to explain why the selected direction is worth
investigating, not as a requirement to invent a novel method.
```

The already agreed focused objective handles unconditional implementation of alternative methods and baselines. This extra sentence resolves the remaining novelty conflict without weakening domain-specific validity, robustness, or evaluation requirements.

This sentence is included in the implementation plan.

### Additional resource finders

`manager_additional_agents.py` launches the same established resource-finder HITL lifecycle but does not own the initial pipeline orchestrator. Before constructing its three prompt contexts, it reads `focused_autoresearch` from `PipelineState` and passes that value into `run_resource_finder_hitl`.

It must not infer focused mode from the current proposal, manager text, launch status, or idea log. Pipeline state remains the only durable source.

### Components that remain unchanged

The implementation does not change:

- idea schema or idea-log records;
- proposer, verifier, reviewer, or ranking contracts;
- candidate execution and scoring;
- manager and frontier decisions;
- stage permissions or HITL tools;
- workspace write guards;
- checkpoint capture, rollback, or recovery records;
- paper-writer prompts;
- non-HITL AutoResearch;
- Ordinary research;
- domain prompt files.

## Implementation roadmap

Each step is independently reviewable. During implementation, finish the local checks for a step and commit it before moving to the next step.

### Step 1: Add and persist the optional mode

Update the existing launch and workspace-state path:

- add the fresh-run CLI option;
- add the browser control and request field;
- validate the request field in `hitl_run_worker.py`;
- forward it through `ResearchRunner` and the fresh initial-pipeline functions;
- persist and validate it in `PipelineState`;
- expose the stored value in `HitlWorkspaceView` and lock the browser control for established workspaces.

Local checks:

- a standard fresh HITL AutoResearch run stores `false`;
- a focused fresh run stores `true`;
- an older workspace with no field reads as standard;
- continuation retains the stored value;
- an incomplete initial pipeline retains its stored value even though its launch mode is still `fresh`;
- a conflicting reconfiguration is rejected;
- Ordinary and non-HITL runs are unchanged.

### Step 2: Add shared focused contracts and flag plumbing

Add the three role-level focused templates and thread the Boolean through existing prompt-generator signatures with a default of `false`.

Do not yet change the ordinary template bodies in this step.

Local checks:

- every existing prompt call still works without a new argument;
- standard prompt output is byte-for-byte unchanged;
- the orchestrator resolves the same focused value after restart;
- an additional resource finder receives the stored value.

### Step 3: Apply the resource-finder and rule-maker contracts

Conditionally omit the direction-budget section for focused resource finding. Append the shared focused resource contract to bootstrap and additive resource-finder contexts. Append the shared rule-maker contract to all three rule-maker phases.

Local checks:

- focused resource-finder plan, execution, and review each contain one focused contract;
- bootstrap selects one direction;
- additive resource finding follows its manager objective without reopening selection;
- focused rule-maker plan, execution, and review contain the same contract once;
- standard prompts retain their existing direction budget and text.

### Step 4: Apply the experiment-runner prompt changes

Implement only the conditional replacements recorded in this document. Append the shared focused experiment scope at the existing execution, plan, and review composition points.

Do not begin this step until the one remaining domain-template sentence above is accepted or rejected.

Local checks:

- standard base and session templates are unchanged when focused mode is off;
- focused generic execution contains every agreed replacement and one final scope contract;
- focused domain-specific execution receives the final scope contract without modifying its domain template;
- focused plan and review receive the concise direction scope;
- no focused text appears in proposer, candidate, scorer, manager, frontier, paper-writer, Ordinary, or non-HITL prompts.

### Step 5: Verify recovery and the complete workflow

Run local prompt and configuration checks, then one focused HITL AutoResearch smoke run.

The smoke run should confirm:

- the resource finder compares candidates but advances one selected direction;
- the rule maker creates a method-neutral evaluation interface;
- the initial experiment runner implements one direction;
- a later proposal may still exploit the current direction or explore a different one;
- paper writing remains selectable;
- stopping and continuing the run retains focused mode;
- an interrupted active worker resumes its saved prompt;
- a rolled-back stage regenerates the same focused prompt from pipeline state.

The implementation is complete only when the standard-mode prompt comparisons and the focused smoke run both pass.

### Focused paper-writing improvements

No focused paper-writing prompt has been designed for the first version. This remains future work after observing actual focused-mode outputs.

### Verification and implementation sequence

The implementation and verification sequence is defined above. No implementation has been made yet.
