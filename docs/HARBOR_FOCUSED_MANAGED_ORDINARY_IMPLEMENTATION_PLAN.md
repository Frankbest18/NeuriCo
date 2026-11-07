# Harbor Focused Managed Ordinary Research Implementation Plan

## Purpose

Extend NeuriCo's current Harbor adapter so Harbor can run either:

- the existing managed AutoResearch workflow; or
- focused managed ordinary research.

This is an incremental adapter change. The current adapter already establishes
the important integration pattern: Harbor supplies the instruction, workspace,
model, and authentication; the adapter converts the instruction into a NeuriCo
idea, launches NeuriCo in the task workspace, streams its output, and supervises
the process. The new mode should reuse that mechanism.

The first target is one unframed Terminal-Bench 4.1 task. Once that run works,
we can use the same adapter for the Astra-versus-NeuriCo study and later add the
safety and capability frames at the experiment level.

## Branch and baseline

Implement on:

```text
harbor-focused-managed-ordinary
```

This branch is based on:

```text
focused-managed-ordinary
311c3bd9e51e8f86860b2dbcd15c6097d6b00821
```

The focused managed ordinary workflow itself remains owned by NeuriCo core.
This branch only connects that workflow to Harbor and makes the small runtime
adjustments needed for the benchmark run.

Keep this boundary throughout implementation. Do not reproduce NeuriCo's
detached managed-launch infrastructure or turn this work into a general Harbor
compatibility redesign.

## Scope

The initial implementation includes:

1. a validated workflow selector;
2. a focused managed ordinary execution path in the existing child runner;
3. explicit Codex version and reasoning-effort configuration;
4. preservation of the NeuriCo records needed for later analysis;
5. contract tests and adapter documentation for both modes;
6. one reproducible Harbor smoke run on `embedding-drift-monitor`.

The initial implementation does not attempt to solve every task-specific
compatibility issue in the 62-task set. MCP tasks, unusual task users, and broad
artifact declarations should be tested after the basic path works and handled
only when they create a concrete failure.

## Existing adapter behavior to reuse

Keep the current mechanisms for:

- extracting the complete Harbor text instruction;
- validating Harbor's task workspace;
- converting the instruction into a NeuriCo idea;
- using the Harbor workspace as `metadata.local_workspace`;
- selecting Harbor's requested model;
- creating an isolated `CODEX_HOME`;
- using the mounted Codex login without modifying it;
- starting NeuriCo under the existing process supervisor;
- streaming child output through ACP;
- cancellation and process-tree cleanup;
- leaving Harbor's verifier as the authoritative scorer.

Avoid a general adapter refactor. Rename or extract a helper only when both
workflows actually need it.

## Step 1: Add the workflow selector

Add one adapter setting:

```text
NEURICO_HARBOR_WORKFLOW=autoresearch
NEURICO_HARBOR_WORKFLOW=focused-managed-ordinary
```

If the setting is absent, select `autoresearch`. This preserves the current
adapter behavior.

Use one small validation function. Reject an empty or unknown value before a
child process starts.

The existing AutoResearch-only controls remain available on the AutoResearch
path:

```text
NEURICO_HARBOR_AUTORESEARCH_ITERATIONS
NEURICO_HARBOR_TIME_LIMIT_SECONDS
```

The focused managed ordinary path does not read those controls. Workflow
dispatch should parse only the settings used by the selected workflow.

### Tests

- no setting selects the existing AutoResearch path;
- each supported value selects the corresponding path;
- invalid values fail before process launch;
- the existing AutoResearch configuration tests continue to pass.

## Step 2: Add the focused managed ordinary execution path

Extend the current child runner instead of adding a parallel entrypoint. Keep
the existing AutoResearch execution function and add one focused managed
ordinary execution function. Select between them with the validated workflow
value passed by the ACP adapter.

Both paths should share the current instruction-file parsing, idea conversion,
workspace, provider, process supervisor, signal handling, and CLI main
function. This avoids duplicating the adapter lifecycle.

Its NeuriCo call should be:

```python
runner.run_research(
    idea_id=idea_id,
    provider="codex",
    full_permissions=True,
    multi_agent=True,
    use_scribe=False,
    write_paper=False,
    scoring_enabled=False,
    benchmark_mode=True,
    hitl_research="cli",
    hitl_manager_no_browser=True,
    hitl_mode="auto",
    focused_autoresearch=True,
    workspace_mode="embedded",
)
```

The internal flag is still named `focused_autoresearch`; pairing it with
`hitl_research` selects focused managed ordinary research.

Wrap this ordinary runner call in NeuriCo's existing
`activate_hitl_run_stop_control(HitlRunStopControl(workspace, request_id))`
context, using a fresh request ID. Direct managed ordinary calls do not create
that control; NeuriCo's normal managed launcher supplies it. The adapter must
supply it here so the shared interrupt handler can request cooperative stop.
Leave workspace lease ownership with the runner and keep AutoResearch's
existing control initialization unchanged.

This is only the bridge required by the adapter's existing interrupt handler.
Do not add the detached launcher's request queue, launch-status protocol, or
managed rollback lifecycle to the Harbor adapter in this change.

The adapter should dispatch to this execution path when the new workflow is
selected. Its completion and error messages should say focused managed ordinary
research rather than AutoResearch.

Keep persisted and user-visible mode labels accurate. The focused managed
ordinary path should not write the existing AutoResearch idea tag or use the
AutoResearch fallback title, and shared adapter descriptions should be neutral
or reflect the selected workflow. Preserve the current values on the
AutoResearch path. Do not add another workflow metadata field: NeuriCo's
pipeline state already records the workflow and focused setting. Internal class,
module, and helper names do not need to change for this integration.

Do not add a second manager, prompt system, scoring loop, or timeout mechanism
inside the adapter. Those behaviors remain owned by NeuriCo and Harbor.

Reuse the current process supervision and cancellation code, but keep result
interpretation workflow-specific. Exit code `124` and the retained best
checkpoint message belong to managed AutoResearch's native budget handling.
Focused managed ordinary research should report only its own success, failure,
or cancellation result.

### Tests

- the new path passes the exact runner arguments above;
- the original Harbor instruction and instruction hash reach the NeuriCo idea;
- persisted idea labels and user-visible messages identify the selected
  workflow, while the existing AutoResearch values remain unchanged;
- the selected workspace remains Harbor's supplied workspace;
- scoring and paper generation are disabled;
- the existing AutoResearch execution function and runner arguments remain
  unchanged;
- AutoResearch budget completion retains its current exit-code handling, while
  focused managed ordinary completion does not claim budget finalization or a
  retained best checkpoint;
- cancellation reaches the active native stop control on the ordinary path,
  exercising the real runner ownership wrapper rather than only mocked runner
  arguments; existing process-supervisor cancellation checks still pass.

## Step 3: Configure the benchmark runtime

Update the adapter's Codex pin to the locally validated version:

```text
0.167.0
```

Add a validated reasoning-effort setting:

```text
NEURICO_HARBOR_REASONING_EFFORT=high
```

When present, write it into the isolated Codex configuration as:

```toml
model_reasoning_effort = "high"
```

The study job will set `high` explicitly. Because the manager and workers share
the isolated `CODEX_HOME`, the setting should apply to every Codex-backed stage
without stage-specific adapter logic.

When the setting is absent, preserve the adapter's current behavior and omit
`model_reasoning_effort` from the generated Codex configuration. Updating the
Codex pin is an intentional shared runtime update for both adapter workflows;
the existing AutoResearch workflow behavior remains otherwise unchanged.

The study job should use the normal pinned launcher and should not set
`NEURICO_CODEX_EXECUTABLE`. Preserve the existing explicit-executable override
behavior. Record the actual Codex version during the real smoke run.

### Tests

- the launcher requires or installs Codex `0.167.0`;
- parsing the generated TOML shows `model_reasoning_effort = "high"` at the
  top level rather than inside a provider table;
- an absent setting leaves `model_reasoning_effort` unspecified;
- an invalid value is rejected;
- the mounted authentication file is still copied into the isolated home and
  is never included in logs or saved study files.

## Step 4: Preserve the existing NeuriCo records

Harbor already preserves ACP output. For semantic analysis we also need the
records NeuriCo already creates during the run.

Export the records available at finalization. Native stage rollback may already
have restored earlier manager history, so this export does not guarantee a
complete history of failed runs. Preserving history across rollback is separate
work and does not add tracing infrastructure to this adapter change.

After the NeuriCo child stops, but before the adapter's temporary control
directory is removed, copy a small whitelist into:

```text
/logs/agent/neurico
```

Preserve, when present:

- the submitted idea from the temporary idea registry;
- `.neurico/pipeline_state.json` and `.neurico/pipeline_results.json`;
- `.neurico/research_state.json`;
- worker prompts, logs, and transcript JSONL files under `logs/`;
- `.neurico/hitl/manager/context.jsonl` and
  `.neurico/hitl/manager/history.sqlite`;
- `.neurico/hitl/idea/idea.jsonl`;
- `.neurico/hitl/whiteboard/whiteboard.json`;
- approved worker plans under `plans/`;
- `literature_review.md`, `resources.md`, and `planning.md`;
- `REPORT.md`, if the worker created it.

Exclude the isolated Codex home, authentication files, manager tokens, locks,
PIDs, and sockets. Copying evidence must not change the child exit status.

Use NeuriCo's existing `HitlManagerHistory.snapshot_lock()` while copying the
manager history so its SQLite WAL is checkpointed consistently. This reuses
NeuriCo's current snapshot mechanism rather than adding an adapter-specific
database format.

Use one finalization path in the existing shared launcher. After normal
completion, await the NeuriCo child without terminating task services that the
Harbor verifier may need. After failure, cancellation, or an output-stream
error, complete the existing process-supervisor cleanup. Then copy the records
while the temporary registry still exists and finally remove the temporary
files. Surface copy failures without replacing the original run outcome.

Final copying supports the first completed smoke run. Harbor's outer timeout
does not establish that ACP cancellation and final export will run; timeout
record preservation remains unverified until the check described below. Do not
add a new tracing system or periodic snapshot service for this first smoke.

### Tests

- a completed fake run copies the expected files;
- a failed or cancelled fake run still attempts to copy available records;
- successful completion does not terminate task services retained for Harbor's
  verifier;
- an output-stream error completes existing process cleanup before copying and
  temporary cleanup;
- the submitted idea is copied before the temporary registry is removed;
- manager history remains readable after copying;
- secrets and transient control files are excluded;
- an evidence-copy error is reported without replacing the actual NeuriCo result.

## Step 5: Make benchmark completion consistent

The new execution path passes `benchmark_mode=True`. NeuriCo already defines that
mode to use the benchmark workspace artifact as the deliverable. The boolean
reaches `ResearchPipelineOrchestrator.run_pipeline()`, but the managed branch
drops it when calling `_run_experiment_runner_hitl()`. That branch then adds
`REPORT.md` independently through its stage expected outputs, finish validator,
research prompt, and session instructions.

Carry the existing boolean through the managed experiment-runner path. For a
managed ordinary benchmark run:

- use no adapter-imposed `REPORT.md` stage output;
- do not install the ordinary-report finish validator;
- condition mandatory `REPORT.md` instructions in the research and session
  templates used to render the execution context, including the selected
  domain-specific session override. Preserve unrelated instructions and
  optional report-format guidance. The plan and review contexts do not render
  these templates and require no report-specific changes.

The original Harbor instruction remains in the rendered context unchanged. If
that instruction itself requires documentation or a report, the worker must
still satisfy it. The adapter does not infer a separate documentation contract.

Keep ordinary managed research unchanged when `benchmark_mode=False`.
Keep managed AutoResearch prompt and completion behavior unchanged even though
its existing adapter invocation also passes `benchmark_mode=True`.

This is the one required NeuriCo-core correction in the adapter work. Transport
and apply the existing boolean at the four points above. Keep the focused
workflow's planning, execution, review, and manager behavior otherwise
unchanged. Do not append a second prompt paragraph that contradicts an inherited
mandatory-report instruction; render one consistent benchmark prompt instead.

Do not use this step to rewrite the surrounding research templates or to infer
task-specific documentation requirements. The supplied Harbor instruction
remains authoritative; this correction only removes NeuriCo's unconditional
benchmark report obligation from the managed ordinary path.

### Tests

- ordinary managed research still requires its normal report;
- managed benchmark mode can complete without that report;
- scored AutoResearch completion remains unchanged;
- the fully rendered execution context for focused managed ordinary benchmark
  mode contains no NeuriCo-imposed mandatory-`REPORT.md` obligation; cover the
  default session template and a selected domain-specific session override;
- the existing plan and review prompt rendering remains unchanged;
- a report requirement present in the original Harbor instruction remains
  present in the rendered worker context;
- compare the original task instruction with the actual rendered worker prompt
  to verify complete delivery; decode the instruction field where the context
  embeds the idea as JSON;
- the rendered benchmark prompt, stage expected outputs, and runtime validator
  agree;
- the rendered AutoResearch prompt remains unchanged.

## Step 6: Run the local adapter tests

Extend the existing Harbor contract suite rather than creating a parallel test
harness.

Run:

```text
integrations/harbor/tests/contract_checks.py
tests/test_focused_managed_ordinary.py
tests/test_managed_ordinary_report.py
directly affected cancellation and provider-failure tests
```

The local gate is satisfied when:

- the default adapter path still runs managed AutoResearch;
- the selector runs focused managed ordinary research;
- both paths preserve the Harbor instruction and workspace;
- model and effort configuration are correct;
- the expected NeuriCo records are copied into Harbor's agent-log directory;
- all affected existing tests pass.

Update `integrations/harbor/README.md` in the same change. Document the workflow
selector, the focused managed ordinary example, the reasoning-effort setting,
the retained-record location, and the fact that the existing AutoResearch mode
remains the default. Keep the documentation aligned with the validated adapter
surface rather than exposing raw NeuriCo CLI arguments.

## Step 7: Run one real Harbor smoke task

Use the official Terminal-Bench 4.1 task:

```text
embedding-drift-monitor
```

Run it with:

```text
workflow: focused-managed-ordinary
model: openai/gpt-6-astra
reasoning effort: high
attempts: 1
framing: none
agent timeout: 3600 seconds
retries: 0
official Harbor verifier: unchanged
```

Do not set `NEURICO_HARBOR_AUTORESEARCH_ITERATIONS` or
`NEURICO_HARBOR_TIME_LIMIT_SECONDS` for this condition. Those settings belong
to the AutoResearch workflow; Harbor's agent timeout is the outer limit for the
focused managed ordinary run.

Pin the NeuriCo source commit used by Harbor and save the Harbor job
configuration in the standalone study workspace. Confirm and record the actual
Codex version selected by the normal pinned launcher. Save the exact runnable
Harbor command next to the job configuration so the smoke can be repeated
without reconstructing invocation details from shell history.

The smoke passes when:

- Harbor installs and starts the NeuriCo source agent;
- the adapter selects focused managed ordinary research;
- NeuriCo works in the supplied task workspace;
- Harbor runs the official separate verifier and records a reward;
- ACP output and the copied NeuriCo records are available for inspection;
- there is no adapter or infrastructure exception.

Inspect the retained records before declaring the integration smoke successful.
They must show that:

- focused managed ordinary mode was active;
- the resource finder, experiment runner, and autonomous manager participated;
- no rule-maker, internal scorer, or AutoResearch proposal iteration ran;
- the complete supplied task instruction reached the worker context, verified
  against the saved rendered prompt (decoding an embedded JSON instruction
  field where applicable); the stored source and SHA-256 provide provenance,
  not a substitute for this delivery check;
- the copied worker prompts and transcripts, manager context, manager history,
  idea log, and pipeline state are present when produced and are readable.

This inspection is a workflow contract check, not a semantic judgment of the
solution. Record the result beside the Harbor job artifacts.

The reward does not determine whether the integration worked. A reward of zero
with a completed official verifier is a valid task failure; an adapter,
installation, or verifier-launch error is a pipeline failure.

## After the smoke

Before a benchmark batch, run a short controlled Harbor timeout check and
inspect the retained NeuriCo records. A successful completed smoke does not
prove preservation on timeout. If records are missing, fix that demonstrated
gap before relying on timed-out runs for semantic analysis; choose the smallest
change supported by the check.

Run additional selected tasks through the same adapter. When a task exposes a
specific incompatibility, fix that incompatibility with the smallest change and
add a representative test.

Known cases to check include the task requiring Playwright MCP, task images
without Git, and tasks that submit a broad `/app` artifact. These are follow-up
compatibility checks, not prerequisites for wiring and validating the new mode.

Safety and capability framing should be introduced after the unframed Astra and
NeuriCo paths both run reproducibly. The framing layer should preserve the raw
official instruction alongside the framed instruction so we can attribute any
performance difference to the intended condition.

## Completion criteria for this branch

This branch is ready for review when:

1. the current AutoResearch adapter remains the default;
2. Harbor can explicitly select focused managed ordinary research;
3. the new path uses the existing native NeuriCo workflow;
4. Codex `0.167.0` and top-level `high` effort are reproducibly configured;
5. available NeuriCo prompts, logs, results, and manager records are exported
   on completion, failure, and handled cancellation; complete failed-run history
   is not guaranteed across native rollback, and timeout preservation remains
   subject to the pre-batch check;
6. local contract and regression tests pass;
7. the official one-hour `embedding-drift-monitor` Harbor smoke completes, its
   workflow evidence passes the checks above, and its configuration, runnable
   command, and artifacts are saved in the study workspace.
