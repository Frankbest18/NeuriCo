# NeuriCo Harbor agent

This directory is the locked ACP runtime for using NeuriCo's managed workflows
as a Harbor agent. The adapter converts Harbor's prompt through NeuriCo's
existing local-idea converter and launches the selected workflow in headless
Auto mode inside Harbor's supplied repository, using NeuriCo's Codex provider.
Auto mode uses the manager for every review boundary but never waits for human
input.

## Contract

- The ACP `cwd` becomes the idea's `metadata.local_workspace`. The adapter
  never assumes `/app`, and NeuriCo uses Harbor's repository as its research
  workspace.
- Harbor's complete text prompt is preserved in
  `idea.background.description`. NeuriCo's prompt generator already promotes
  that field as high-priority user instructions.
- `NEURICO_HARBOR_WORKFLOW` selects `autoresearch` or
  `focused-managed-ordinary`. If it is absent, the adapter preserves its
  existing `autoresearch` behavior.
- `NEURICO_HARBOR_DOMAIN` optionally selects an explicitly configured NeuriCo
  domain for the generated idea. It is never inferred from Harbor or the task
  text. If absent, idea conversion preserves its existing domain behavior; an
  invalid value fails before research starts.
- In `autoresearch`, NeuriCo runs fresh manager-driven HITL AutoResearch in
  Auto mode. The manager
  reviews resource-finder, rule-maker, experiment, and scoring boundaries and
  may request repairs or replacement workers without human interaction. The
  resource finder may use Harbor's supplied repository and any external sources
  allowed by the task's Harbor network policy. The scored lifecycle then
  continues with a baseline experiment, scoring, proposals, candidate
  experiments, and manager-governed accept-or-restore checkpointing.
- In `focused-managed-ordinary`, the resource finder, experiment runner, and
  manager concentrate on producing and validating one final solution. NeuriCo
  internal scoring and proposal iteration are disabled. The supplied workspace
  artifact is the deliverable, so NeuriCo does not add a mandatory `REPORT.md`
  requirement. Paper generation and scribe/notebook output remain disabled.
  Harbor's verifier is the authoritative benchmark result after the agent
  exits.
- One AutoResearch improvement iteration is used by default, matching
  NeuriCo's CLI default. `NEURICO_HARBOR_AUTORESEARCH_ITERATIONS` may select a
  larger positive count. This changes search depth within one Harbor trial; it
  does not change Harbor's number of independent attempts or limit the
  manager's stage-level repair and replacement decisions.
- `NEURICO_HARBOR_TIME_LIMIT_SECONDS` optionally gives NeuriCo a whole-run
  budget through NeuriCo's native managed-AutoResearch deadline. NeuriCo owns
  stop propagation and budget-specific selected-frontier finalization; the
  adapter only translates the completed budget stop for Harbor. Set this below
  Harbor's agent timeout so native finalization has time
  to finish; for example, use 3480 seconds with a 3600-second Harbor timeout.
  If native shutdown itself stalls, the adapter terminates the isolated NeuriCo
  process tree, including separately grouped provider processes, after a
  30-second grace period. ACP cancellation follows the same ownership boundary:
  it requests NeuriCo's native stop first, then terminates any surviving owned
  groups. A dedicated Linux supervisor retains orphaned provider processes
  until cleanup finishes, including providers started during shutdown. It
  remains independent of the manager so stalled manager cleanup cannot lose
  process ownership. Failed, cancelled, and forcibly terminated runs clean all
  retained descendants. After normal completion or completed native budget
  finalization, detached task services remain available to Harbor's verifier;
  NeuriCo's provider launchers have already rejected and terminated any
  lingering provider process group before those outcomes can be reported.
  Harbor's ACP launcher does not
  currently expose its resolved hard deadline to the agent, so the Harbor
  timeout and the smaller NeuriCo budget are explicit paired job settings.
- The requested Harbor model is advertised as an ACP session configuration
  option and written to an isolated `CODEX_HOME`, pinning every Codex-backed
  NeuriCo stage to the same model. `NEURICO_HARBOR_REASONING_EFFORT` optionally
  selects a validated Codex reasoning effort; the study configuration uses
  `high`.
- Local runs use a Codex login cache supplied through
  `NEURICO_CODEX_AUTH_FILE`. The adapter copies it into the isolated run home;
  it never writes the mounted source file.
- Hosted runs may instead supply `HOSTED_INFERENCE_TOKEN` together with
  `HOSTED_INFERENCE_URL`. Direct OpenAI API mode accepts `OPENAI_API_KEY` and
  optional `OPENAI_BASE_URL`.
- NeuriCo's idea registry and Codex home are kept in a temporary control
  directory outside the task repository. Research state and the retained best
  implementation remain in Harbor's workspace.
- At finalization, the adapter copies the available submitted idea, pipeline
  state, worker prompts, logs, transcripts, manager records, approved plans,
  and ordinary-research root records into `/logs/agent/neurico`. Authentication
  and transient process-control files are excluded.
- Harbor runs NeuriCo in embedded workspace mode. NeuriCo-owned dependency
  metadata and its virtual environment live under `neurico-research-env/`,
  while the task's root `.venv` is never read, reused, or removed by the
  adapter. Harbor's verifier remains responsible for its own environment.
- Task-provided MCP servers are rejected when the ACP session is created. The
  adapter does not silently start a run without capabilities declared by the
  benchmark.
- Harbor runs its own verifier after NeuriCo exits; the adapter does not inspect
  or translate Harbor's verifier.

The Python source runtime exposes a locked `codex` launcher. It uses an already
available Codex CLI only when its version exactly matches the adapter pin;
otherwise it installs `@openai/codex@0.167.0` into the execution user's cache.
This mirrors Harbor's own Codex-agent installation strategy while keeping the
NeuriCo source manifest compatible with Harbor's `python-uv` runtime. The
launcher also ensures that Git, which AutoResearch needs for local checkpoints,
is present in minimal task images.

## Local Harbor with ChatGPT authentication

First authenticate the host Codex CLI and confirm the active method:

```bash
codex login
codex login status
```

Then expose only the cached login file to the task container. A local job
configuration looks like this:

```yaml
agents:
  - name: acp
    model_name: openai/gpt-5.6-sol
    override_timeout_sec: 3600
    env:
      NEURICO_CODEX_AUTH_FILE: /run/secrets/neurico-codex-auth.json
      NEURICO_HARBOR_WORKFLOW: focused-managed-ordinary
      NEURICO_HARBOR_REASONING_EFFORT: high
      # Optional opt-in intervention:
      # NEURICO_HARBOR_DOMAIN: software_maintenance
    kwargs:
      source:
        repo_url: https://github.com/ChicagoHAI/neurico
        ref: <branch-tag-or-commit>
        source_dir: .
        manifest_path: integrations/harbor/harbor-agent.json

environment:
  type: docker
  mounts:
    - type: bind
      source: /absolute/host/path/to/.codex/auth.json
      target: /run/secrets/neurico-codex-auth.json
      read_only: true
```

Use a branch while developing and a full commit SHA once the integration is
stable. This executes on the local Harbor/Docker stack and consumes the Codex
entitlement of the ChatGPT account represented by the mounted login cache. The
cache is a secret and must never be committed or included in job artifacts.

## Hosted Harbor

Hosted automation should use a per-user credential, an enterprise Codex access
token exposed through an appropriate provider, or Harbor's hosted inference
gateway. Gateway mode is configured with:

```yaml
agents:
  - name: acp
    model_name: openai/gpt-5.6-sol
    override_timeout_sec: 3600
    env:
      NEURICO_HARBOR_AUTORESEARCH_ITERATIONS: "1"
      NEURICO_HARBOR_TIME_LIMIT_SECONDS: "3480"
    kwargs:
      source:
        repo_url: https://github.com/ChicagoHAI/neurico
        ref: <full-commit-sha>
        source_dir: .
        manifest_path: integrations/harbor/harbor-agent.json
```

Supply `HOSTED_INFERENCE_TOKEN` and `HOSTED_INFERENCE_URL` as Harbor secrets,
not literal configuration values. The gateway must expose an OpenAI Responses
API-compatible endpoint.

The adapter intentionally does not accept raw NeuriCo command-line arguments.
Benchmark controls are added as individually validated `NEURICO_HARBOR_*`
environment variables. The workflow and reasoning effort apply to the selected
run. Iteration count and the optional whole-run time limit apply only to
AutoResearch. Model choice belongs to Harbor, and paper generation remains off.

## Contract tests

```bash
cd integrations/harbor
uv sync --frozen --extra dev
uv run --frozen --extra dev pytest -q tests/contract_checks.py
```

The suite includes a real stdio ACP handshake and model-selection round trip,
checks both workflow paths and their completion semantics, and verifies retained
evidence and isolated Codex configuration. Model-backed execution is replaced
at the process boundary during contract tests, so the tests do not consume
model usage.
