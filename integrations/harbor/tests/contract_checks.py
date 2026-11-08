import asyncio
import json
import os
import signal
import sqlite3
import subprocess
import sys
import time
import tomllib
from pathlib import Path
from typing import Any

import neurico_harbor_agent.agent as agent_module
import neurico_harbor_agent.run_autoresearch as runner_module
import pytest
from acp import PROTOCOL_VERSION, RequestError, spawn_agent_process
from acp.interfaces import Client
from neurico_harbor_agent.agent import (
    NeuricoHarborAgent,
    _autoresearch_iterations,
    _autoresearch_time_limit,
    _harbor_domain,
    _harbor_workflow,
    _reasoning_effort,
    export_neurico_evidence,
    _stream_process_output,
    _terminate_process_tree,
    _text_from_prompt,
)
from neurico_harbor_agent.run_autoresearch import (
    execute_autoresearch,
    execute_focused_managed_ordinary,
)
from neurico_harbor_agent.runtime import (
    CodexInferenceConnection,
    HarborAutoResearchTask,
    build_autoresearch_environment,
    build_harbor_idea,
)
from neurico_harbor_agent.codex_bootstrap import CODEX_VERSION


def test_prompt_text_is_preserved_verbatim() -> None:
    instruction = "First line\n\n  indented line with : and #\n"
    assert _text_from_prompt([{"type": "text", "text": instruction}]) == instruction


def test_harbor_workflow_defaults_to_autoresearch_and_validates_override() -> None:
    assert _harbor_workflow({}) == "autoresearch"
    assert _harbor_workflow({"NEURICO_HARBOR_WORKFLOW": "autoresearch"}) == "autoresearch"
    assert (
        _harbor_workflow({"NEURICO_HARBOR_WORKFLOW": "focused-managed-ordinary"})
        == "focused-managed-ordinary"
    )
    with pytest.raises(ValueError, match="NEURICO_HARBOR_WORKFLOW"):
        _harbor_workflow({"NEURICO_HARBOR_WORKFLOW": ""})
    with pytest.raises(ValueError, match="NEURICO_HARBOR_WORKFLOW"):
        _harbor_workflow({"NEURICO_HARBOR_WORKFLOW": "ordinary"})


def test_reasoning_effort_is_optional_and_validated() -> None:
    assert _reasoning_effort({}) is None
    assert _reasoning_effort({"NEURICO_HARBOR_REASONING_EFFORT": "high"}) == "high"
    with pytest.raises(ValueError, match="NEURICO_HARBOR_REASONING_EFFORT"):
        _reasoning_effort({"NEURICO_HARBOR_REASONING_EFFORT": "maximum"})


def test_harbor_domain_is_optional_and_validated() -> None:
    assert _harbor_domain({}) is None
    assert (
        _harbor_domain({"NEURICO_HARBOR_DOMAIN": "software_maintenance"})
        == "software_maintenance"
    )
    with pytest.raises(ValueError, match="NEURICO_HARBOR_DOMAIN"):
        _harbor_domain({"NEURICO_HARBOR_DOMAIN": "unknown-domain"})


def test_harbor_instruction_uses_neurico_idea_contract(tmp_path: Path) -> None:
    instruction = "# Compare cache policies\n\nTest LRU and LFU on the supplied workload.\n"
    task = HarborAutoResearchTask(instruction=instruction, workspace=tmp_path)
    result = build_harbor_idea(task)
    idea = result["idea"]

    assert idea["title"] == "Compare cache policies"
    assert idea["background"]["description"] == instruction
    assert idea["hypothesis"].startswith("# Compare cache policies")
    assert idea["metadata"]["source"] == "harbor"
    assert idea["metadata"]["local_workspace"] == str(tmp_path)
    assert len(idea["metadata"]["instruction_sha256"]) == 64


def test_focused_managed_ordinary_idea_uses_mode_correct_labels(tmp_path: Path) -> None:
    task = HarborAutoResearchTask(instruction="Fix it", workspace=tmp_path)
    result = build_harbor_idea(task, workflow="focused-managed-ordinary")

    assert result["idea"]["title"].startswith("Harbor focused managed ordinary research")
    assert result["idea"]["metadata"]["tags"] == [
        "harbor",
        "focused-managed-ordinary",
    ]


def test_explicit_harbor_domain_preserves_instruction(tmp_path: Path) -> None:
    instruction = "Repair the supplied implementation exactly as requested.\n"
    task = HarborAutoResearchTask(instruction=instruction, workspace=tmp_path)
    result = build_harbor_idea(task, domain="software_maintenance")

    assert result["idea"]["domain"] == "software_maintenance"
    assert result["idea"]["background"]["description"] == instruction


@pytest.mark.parametrize("workflow", ["autoresearch", "focused-managed-ordinary"])
def test_harbor_task_reaches_manager_backend_and_evidence(tmp_path, monkeypatch, workflow):
    from types import SimpleNamespace
    import yaml
    from core.hitl_manager_react import HitlManager
    from core.hitl_runtime_state import HitlRuntimeState

    instruction = "Investigate the supplied package.\n" * 100 + "Required output: /app/final.json\n"
    task = build_harbor_idea(
        HarborAutoResearchTask(instruction=instruction, workspace=tmp_path), workflow=workflow,
    )
    assert "Required output" not in task["idea"]["hypothesis"]
    bound = HitlRuntimeState(tmp_path).bind_task_context(task)
    captured = []

    def send(messages, tools):
        captured.extend(messages)
        return SimpleNamespace(text="Review complete", tool_calls=[])

    monkeypatch.setattr(
        HitlManager, "_backend_for_provider",
        lambda self, provider: SimpleNamespace(backend="test", send=send),
    )
    manager = HitlManager({}, work_dir=tmp_path)
    manager._run_turn("human", "Review the task.", generation=0)
    task_message = next(m for m in captured if m["content"].startswith("User-provided research task"))
    supplied = yaml.safe_load(task_message["content"].split("\n\n", 1)[1])
    assert supplied == bound
    assert supplied["idea"]["background"]["description"] == instruction
    captured.clear()
    manager.set_provider("codex")
    manager._run_turn("human", "Continue the review.", generation=0)
    replacement_message = next(
        m for m in captured if m["content"].startswith("User-provided research task")
    )
    assert yaml.safe_load(replacement_message["content"].split("\n\n", 1)[1]) == supplied
    runtime_path = tmp_path / ".neurico/hitl/runtime.json"
    before = runtime_path.read_bytes()
    export_neurico_evidence(workspace=tmp_path, ideas_dir=tmp_path / "ideas", destination=tmp_path / "export")
    exported = tmp_path / "export/.neurico/hitl/manager/task_context.json"
    assert json.loads(exported.read_text()) == supplied
    assert runtime_path.read_bytes() == before
    assert not (tmp_path / "export/.neurico/hitl/runtime.json").exists()


@pytest.mark.parametrize("runtime_exists", [False, True])
def test_task_evidence_export_does_not_initialize_missing_context(tmp_path, runtime_exists):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    runtime_path = workspace / ".neurico/hitl/runtime.json"
    if runtime_exists:
        runtime_path.parent.mkdir(parents=True)
        runtime_path.write_text('{"manager_provider": "codex"}')
    before = {str(p.relative_to(workspace)): p.read_bytes() for p in workspace.rglob("*") if p.is_file()}
    destination = tmp_path / "export"
    export_neurico_evidence(workspace=workspace, ideas_dir=tmp_path / "ideas", destination=destination)
    after = {str(p.relative_to(workspace)): p.read_bytes() for p in workspace.rglob("*") if p.is_file()}
    assert before == after
    assert not (destination / ".neurico/hitl/manager/task_context.json").exists()


@pytest.mark.parametrize("phase", ["plan", "execution", "review"])
def test_focused_ordinary_workers_receive_complete_harbor_instruction(
    tmp_path: Path, phase: str
) -> None:
    from core.pipeline_orchestrator import ResearchPipelineOrchestrator
    from templates.prompt_generator import PromptGenerator

    instruction = (
        "Repair the supplied package.\n\n"
        + "Inspect the supplied fixtures and reproduce the reported behavior. " * 20
        + "\n\nRequired output: /app/final.json\n"
        + "Do not download task-specific solutions.\n  Preserve this indentation.\n"
    )
    idea = build_harbor_idea(
        HarborAutoResearchTask(instruction=instruction, workspace=tmp_path),
        workflow="focused-managed-ordinary",
    )
    assert "Required output" not in idea["idea"]["hypothesis"]
    templates = Path(runner_module.__file__).resolve().parents[3] / "templates"
    generator = PromptGenerator(templates, workspace_mode="embedded")
    resource_prompt = generator.generate_resource_finder_prompt(
        idea,
        provider="codex",
        hitl_runtime_completion=True,
        hitl_phase=phase,
        focused_managed_ordinary=True,
    )
    assert instruction in resource_prompt
    assert resource_prompt.count(instruction) == 1
    assert generator._extract_user_instructions(resource_prompt) == instruction.strip()

    orchestrator = ResearchPipelineOrchestrator(
        work_dir=tmp_path,
        templates_dir=templates,
        managed_initial_run=True,
        focused_autoresearch=True,
    )
    experiment_prompt = orchestrator._hitl_experiment_runner_source_prompt(
        idea=idea,
        provider="codex",
        use_scribe=False,
        scoring_enabled=False,
        hitl_phase=phase,
        benchmark_mode=True,
    )
    # Plan/review include the idea as JSON; execution renders the description.
    assert (
        instruction in experiment_prompt
        or json.dumps(instruction)[1:-1] in experiment_prompt
    )


def test_hosted_gateway_uses_neutral_credential_and_full_model(tmp_path: Path) -> None:
    connection = CodexInferenceConnection.from_environment(
        {
            "HOSTED_INFERENCE_TOKEN": "secret",
            "HOSTED_INFERENCE_URL": "https://gateway.example/v1",
        },
        requested_model="openrouter/example/model",
    )
    assert connection.backend_model == "openrouter/example/model"
    environment = connection.prepare_codex_home(tmp_path / "codex-home")
    config = (tmp_path / "codex-home" / "config.toml").read_text()
    assert environment["HOSTED_INFERENCE_TOKEN"] == "secret"
    assert 'model = "openrouter/example/model"' in config
    assert 'base_url = "https://gateway.example/v1"' in config
    assert 'env_key = "HOSTED_INFERENCE_TOKEN"' in config
    assert "secret" not in config
    assert "model_reasoning_effort" not in tomllib.loads(config)
    assert tomllib.loads(config)["allow_login_shell"] is False


def test_chatgpt_auth_mode_strips_openai_provider_prefix(tmp_path: Path) -> None:
    auth_file = tmp_path / "mounted-auth.json"
    auth_file.write_text('{"tokens": {}}')
    connection = CodexInferenceConnection.from_environment(
        {"NEURICO_CODEX_AUTH_FILE": str(auth_file)},
        requested_model="openai/gpt-5.6-sol",
    )
    assert connection.mode == "chatgpt"
    assert connection.backend_model == "gpt-5.6-sol"


def test_direct_non_openai_model_is_rejected(tmp_path: Path) -> None:
    auth_file = tmp_path / "mounted-auth.json"
    auth_file.write_text('{"tokens": {}}')
    with pytest.raises(ValueError, match="requires an OpenAI model"):
        CodexInferenceConnection.from_environment(
            {"NEURICO_CODEX_AUTH_FILE": str(auth_file)},
            requested_model="anthropic/claude-sonnet-5",
        )


def test_environment_exposes_locked_codex_and_isolated_home(tmp_path: Path) -> None:
    auth_file = tmp_path / "mounted-auth.json"
    auth_file.write_text('{"tokens": {}}')
    connection = CodexInferenceConnection(
        requested_model="openai/test-model",
        mode="chatgpt",
        auth_file=auth_file,
    )
    ideas_dir = tmp_path / "control" / "ideas"
    codex_home = tmp_path / "control" / "codex-home"
    environment = build_autoresearch_environment(
        {"PATH": "/usr/bin"},
        connection,
        ideas_dir=ideas_dir,
        codex_home=codex_home,
        reasoning_effort="high",
    )
    assert environment["NEURICO_IDEAS"] == str(ideas_dir)
    assert environment["CODEX_HOME"] == str(codex_home)
    assert (codex_home / "auth.json").read_text() == '{"tokens": {}}'
    config = tomllib.loads((codex_home / "config.toml").read_text())
    assert config["model"] == "test-model"
    assert config["model_reasoning_effort"] == "high"
    assert config["allow_login_shell"] is False
    first_path = Path(environment["PATH"].split(os.pathsep)[0])
    assert (first_path / "codex").is_file()


def test_codex_runtime_pin_matches_study_version() -> None:
    assert CODEX_VERSION == "0.167.0"


def test_evidence_export_copies_whitelist_and_excludes_secrets(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    ideas_dir = tmp_path / "ideas"
    destination = tmp_path / "evidence"
    (ideas_dir / "completed").mkdir(parents=True)
    (ideas_dir / "completed" / "idea.yaml").write_text("idea: {}\n")
    manager_dir = workspace / ".neurico" / "hitl" / "manager"
    manager_dir.mkdir(parents=True)
    (workspace / ".neurico" / "pipeline_state.json").write_text("{}\n")
    (workspace / "logs").mkdir()
    (workspace / "logs" / "execution_codex.log").write_text("worker output\n")
    (workspace / "plans").mkdir()
    (workspace / "plans" / "experiment_runner_plan.md").write_text("# Plan\n")
    (workspace / "planning.md").write_text("# Working plan\n")
    (manager_dir / "manager.token").write_text("secret")
    (workspace / "logs" / "secret.key").write_text("secret")
    from core.hitl_manager_history import HitlManagerHistory

    history = HitlManagerHistory(manager_dir)
    history.append(
        {
            "id": "message-1",
            "type": "message",
            "speaker": "manager",
            "content": "Review complete",
            "timestamp": "2026-11-07T00:00:00Z",
        }
    )

    export_neurico_evidence(
        workspace=workspace,
        ideas_dir=ideas_dir,
        destination=destination,
    )

    assert (destination / "idea_registry" / "completed" / "idea.yaml").is_file()
    assert (destination / ".neurico" / "pipeline_state.json").is_file()
    assert (destination / "logs" / "execution_codex.log").is_file()
    assert (destination / "plans" / "experiment_runner_plan.md").is_file()
    assert (destination / "planning.md").is_file()
    copied_history = destination / ".neurico" / "hitl" / "manager" / "history.sqlite"
    with sqlite3.connect(copied_history) as connection:
        assert connection.execute("SELECT COUNT(*) FROM conversation_records").fetchone() == (1,)
    assert not (destination / ".neurico" / "hitl" / "manager" / "manager.token").exists()
    assert not (destination / "logs" / "secret.key").exists()


def test_iteration_override_must_be_positive() -> None:
    assert _autoresearch_iterations({}) == 1
    assert _autoresearch_iterations({"NEURICO_HARBOR_AUTORESEARCH_ITERATIONS": "3"}) == 3
    with pytest.raises(ValueError, match="at least 1"):
        _autoresearch_iterations({"NEURICO_HARBOR_AUTORESEARCH_ITERATIONS": "0"})


def test_time_limit_override_is_optional_and_positive() -> None:
    assert _autoresearch_time_limit({}) is None
    assert _autoresearch_time_limit({"NEURICO_HARBOR_TIME_LIMIT_SECONDS": "1740"}) == 1740
    with pytest.raises(ValueError, match="positive integer"):
        _autoresearch_time_limit({"NEURICO_HARBOR_TIME_LIMIT_SECONDS": "0"})
    with pytest.raises(ValueError, match="positive integer"):
        _autoresearch_time_limit({"NEURICO_HARBOR_TIME_LIMIT_SECONDS": "1.5"})
    with pytest.raises(ValueError, match="positive integer"):
        _autoresearch_time_limit({"NEURICO_HARBOR_TIME_LIMIT_SECONDS": "later"})


def test_cancellation_requests_native_stop_and_terminates_detached_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def exercise() -> None:
        child_pid_file = tmp_path / "provider.pid"
        stop_file = tmp_path / "native-stop-requested"
        script = tmp_path / "process_tree.py"
        script.write_text(
            "\n".join(
                [
                    "import signal",
                    "import subprocess",
                    "import sys",
                    "import time",
                    "from pathlib import Path",
                    f"child_pid_file = Path({str(child_pid_file)!r})",
                    f"stop_file = Path({str(stop_file)!r})",
                    "provider = subprocess.Popen(",
                    "    [sys.executable, '-c', 'import time; time.sleep(30)'],",
                    "    start_new_session=True,",
                    ")",
                    "child_pid_file.write_text(str(provider.pid))",
                    "signal.signal(signal.SIGINT, lambda *_args: stop_file.write_text('yes'))",
                    "while True:",
                    "    time.sleep(1)",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            str(script),
            start_new_session=True,
        )
        deadline = time.monotonic() + 5
        while not child_pid_file.is_file():
            if time.monotonic() >= deadline:
                process.kill()
                await process.wait()
                raise AssertionError("Detached provider did not start")
            await asyncio.sleep(0.01)
        provider_pid = int(child_pid_file.read_text())

        monkeypatch.setattr(agent_module, "_CANCELLATION_GRACE_SECONDS", 0.1)
        monkeypatch.setattr(agent_module, "_FORCED_TERMINATION_GRACE_SECONDS", 0.1)
        await _terminate_process_tree(process, request_cooperative_stop=True)

        assert process.returncode is not None
        assert stop_file.read_text() == "yes"
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            status = subprocess.run(
                ["ps", "-p", str(provider_pid), "-o", "stat="],
                capture_output=True,
                text=True,
                check=False,
            ).stdout.strip()
            if not status or status.startswith("Z"):
                break
            await asyncio.sleep(0.05)
        else:
            os.killpg(provider_pid, 9)
            raise AssertionError("Detached provider survived Harbor cancellation")

    asyncio.run(exercise())


@pytest.mark.skipif(sys.platform != "linux", reason="child subreapers are Linux-specific")
@pytest.mark.parametrize("shutdown", ["cooperative", "forced", "hard_timeout"])
def test_cancellation_retains_provider_started_during_shutdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, shutdown: str
) -> None:
    async def exercise() -> None:
        ready_file = tmp_path / "worker.ready"
        provider_pid_file = tmp_path / "provider.pid"
        worker_script = tmp_path / "worker.py"
        worker_script.write_text(
            "\n".join(
                [
                    "import os, signal, subprocess, sys, time",
                    "from pathlib import Path",
                    f"ready_file = Path({str(ready_file)!r})",
                    f"provider_pid_file = Path({str(provider_pid_file)!r})",
                    f"shutdown = {shutdown!r}",
                    "def launch_provider():",
                    "    provider = subprocess.Popen(",
                    "        [sys.executable, '-c',",
                    "         'import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)'],",
                    "        start_new_session=True,",
                    "        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,",
                    "    )",
                    "    provider_pid_file.write_text(str(provider.pid))",
                    "def interrupt(*_args):",
                    "    launch_provider()",
                    "    if shutdown == 'cooperative':",
                    "        os._exit(0)",
                    "    signal.signal(signal.SIGTERM, signal.SIG_IGN)",
                    "def terminate(*_args):",
                    "    launch_provider()",
                    "    os._exit(0)",
                    "signal.signal(signal.SIGINT, interrupt)",
                    "signal.signal(signal.SIGTERM, terminate)",
                    "ready_file.write_text('yes')",
                    "while True: time.sleep(0.01)",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "neurico_harbor_agent.process_control",
            sys.executable,
            str(worker_script),
            start_new_session=True,
        )
        provider_pid = None
        try:
            deadline = time.monotonic() + 5
            while not ready_file.is_file():
                assert process.returncode is None, "Supervisor exited before worker startup"
                if time.monotonic() >= deadline:
                    raise AssertionError("Worker did not become ready")
                await asyncio.sleep(0.01)
            # Every provider starts in a signal handler, after the adapter's
            # initial ownership snapshot. The cooperative case immediately
            # exits its parent; the forced case keeps the manager stuck alive.
            monkeypatch.setattr(agent_module, "_CANCELLATION_GRACE_SECONDS", 0.2)
            await asyncio.wait_for(
                _terminate_process_tree(
                    process,
                    request_cooperative_stop=shutdown != "hard_timeout",
                ),
                timeout=10,
            )
            assert process.returncode is not None
            provider_pid = int(provider_pid_file.read_text())
            with pytest.raises(ProcessLookupError):
                os.kill(provider_pid, 0)
        finally:
            if process.returncode is None:
                await _terminate_process_tree(process)
            if provider_pid_file.is_file():
                provider_pid = int(provider_pid_file.read_text())
                try:
                    os.killpg(provider_pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

    asyncio.run(exercise())


@pytest.mark.skipif(sys.platform != "linux", reason="child subreapers are Linux-specific")
@pytest.mark.parametrize("exit_code", [1, 10])
def test_supervisor_preserves_manager_failure_and_reaps_orphans(
    tmp_path: Path, exit_code: int
) -> None:
    provider_pid_file = tmp_path / "provider.pid"
    code = (
        "import os, subprocess, sys; from pathlib import Path; "
        "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], "
        "start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); "
        f"Path({str(provider_pid_file)!r}).write_text(str(p.pid)); os._exit({exit_code})"
    )
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "neurico_harbor_agent.process_control",
                sys.executable,
                "-c",
                code,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == exit_code, result.stderr
        provider_pid = int(provider_pid_file.read_text())
        with pytest.raises(ProcessLookupError):
            os.kill(provider_pid, 0)
    finally:
        if provider_pid_file.is_file():
            try:
                os.killpg(int(provider_pid_file.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass


@pytest.mark.skipif(sys.platform != "linux", reason="child subreapers are Linux-specific")
@pytest.mark.parametrize("exit_code", [0, 124])
def test_supervisor_preserves_task_service_after_success(
    tmp_path: Path, exit_code: int
) -> None:
    service_pid_file = tmp_path / "service.pid"
    code = (
        "import os, subprocess, sys; from pathlib import Path; "
        "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], "
        "start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); "
        f"Path({str(service_pid_file)!r}).write_text(str(p.pid)); os._exit({exit_code})"
    )
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "neurico_harbor_agent.process_control",
                sys.executable,
                "-c",
                code,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == exit_code, result.stderr
        service_pid = int(service_pid_file.read_text())
        os.kill(service_pid, 0)
    finally:
        if service_pid_file.is_file():
            try:
                os.killpg(int(service_pid_file.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass


def test_cancellation_during_child_spawn_is_honored_after_registration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def exercise() -> None:
        auth_file = tmp_path / "auth.json"
        auth_file.write_text('{"tokens": {}}')
        spawn_started = asyncio.Event()
        allow_spawn = asyncio.Event()
        spawned_process: asyncio.subprocess.Process | None = None
        create_subprocess_exec = asyncio.create_subprocess_exec

        async def delayed_create_subprocess_exec(*_args: Any, **kwargs: Any):
            nonlocal spawned_process
            spawn_started.set()
            await allow_spawn.wait()
            spawned_process = await create_subprocess_exec(
                sys.executable,
                "-c",
                "import time; time.sleep(30)",
                cwd=kwargs["cwd"],
                env=kwargs["env"],
                stdout=kwargs["stdout"],
                stderr=kwargs["stderr"],
                start_new_session=kwargs["start_new_session"],
            )
            return spawned_process

        monkeypatch.setattr(
            agent_module.asyncio,
            "create_subprocess_exec",
            delayed_create_subprocess_exec,
        )
        agent = NeuricoHarborAgent(
            {
                "NEURICO_MODEL": "openai/test-model",
                "NEURICO_CODEX_AUTH_FILE": str(auth_file),
            }
        )
        session = await agent.new_session(cwd=str(tmp_path), mcp_servers=[])
        prompt_task = asyncio.create_task(
            agent.prompt(
                session_id=session.session_id,
                prompt=[{"type": "text", "text": "Run this benchmark"}],
            )
        )

        await asyncio.wait_for(spawn_started.wait(), timeout=5)
        await agent.cancel(session.session_id)
        allow_spawn.set()
        response = await asyncio.wait_for(prompt_task, timeout=5)

        assert response.stop_reason == "cancelled"
        assert spawned_process is not None
        assert spawned_process.returncode is not None

    asyncio.run(exercise())


def test_child_output_stream_accepts_events_larger_than_asyncio_line_limit() -> None:
    async def exercise() -> None:
        payload_size = 200_000
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            f"import sys; sys.stdout.write('x' * {payload_size})",
            stdout=asyncio.subprocess.PIPE,
        )
        chunks: list[str] = []

        async def emit(text: str) -> None:
            chunks.append(text)

        return_code = await _stream_process_output(process, emit)
        assert return_code == 0
        assert len("".join(chunks)) == payload_size

    asyncio.run(exercise())


def test_output_stream_failure_cleans_process_before_evidence_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []

    class FakeProcess:
        returncode: int | None = None

    process = FakeProcess()

    async def create_process(*_args: Any, **_kwargs: Any) -> FakeProcess:
        return process

    async def fail_stream(*_args: Any, **_kwargs: Any) -> int:
        raise RuntimeError("stream failed")

    async def terminate(target: FakeProcess, **_kwargs: Any) -> None:
        events.append("terminated")
        target.returncode = 1

    def export(**_kwargs: Any) -> None:
        events.append("exported")

    monkeypatch.setattr(agent_module.asyncio, "create_subprocess_exec", create_process)
    monkeypatch.setattr(agent_module, "_stream_process_output", fail_stream)
    monkeypatch.setattr(agent_module, "_terminate_process_tree", terminate)
    monkeypatch.setattr(agent_module, "export_neurico_evidence", export)
    monkeypatch.setattr(agent_module, "build_autoresearch_environment", lambda *_args, **_kwargs: {})

    async def exercise() -> None:
        with pytest.raises(RuntimeError, match="stream failed"):
            await agent_module.run_autoresearch_process(
                task=HarborAutoResearchTask("Complete the task", tmp_path),
                connection=CodexInferenceConnection("openai/test", "chatgpt"),
                base_environment={},
                workflow="focused-managed-ordinary",
                domain=None,
                reasoning_effort="high",
                iterations=None,
                time_limit_seconds=None,
                emit=lambda _text: asyncio.sleep(0),
                register_process=lambda _process: False,
            )

    asyncio.run(exercise())
    assert events == ["terminated", "exported"]


def test_evidence_export_failure_preserves_child_exit_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    messages: list[str] = []

    class FakeProcess:
        returncode: int | None = None

    process = FakeProcess()

    async def create_process(*_args: Any, **_kwargs: Any) -> FakeProcess:
        return process

    async def finish_stream(target: FakeProcess, _emit: Any) -> int:
        target.returncode = 7
        return 7

    def fail_export(**_kwargs: Any) -> None:
        raise OSError("log volume unavailable")

    async def emit(text: str) -> None:
        messages.append(text)

    monkeypatch.setattr(agent_module.asyncio, "create_subprocess_exec", create_process)
    monkeypatch.setattr(agent_module, "_stream_process_output", finish_stream)
    monkeypatch.setattr(agent_module, "export_neurico_evidence", fail_export)
    monkeypatch.setattr(agent_module, "build_autoresearch_environment", lambda *_args, **_kwargs: {})

    async def exercise() -> int:
        return await agent_module.run_autoresearch_process(
            task=HarborAutoResearchTask("Complete the task", tmp_path),
            connection=CodexInferenceConnection("openai/test", "chatgpt"),
            base_environment={},
            workflow="focused-managed-ordinary",
            domain=None,
            reasoning_effort="high",
            iterations=None,
            time_limit_seconds=None,
            emit=emit,
            register_process=lambda _process: False,
        )

    assert asyncio.run(exercise()) == 7
    assert messages == ["NeuriCo evidence export failed: log volume unavailable\n"]


def test_child_entrypoint_invokes_manager_driven_auto_hitl_runner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    class FakeManager:
        def __init__(self, ideas_dir: Path):
            captured["ideas_dir"] = ideas_dir

        def submit_idea(self, idea: dict[str, Any], validate: bool) -> str:
            captured["idea"] = idea
            captured["validate"] = validate
            return "harbor-idea"

    class FakeRunner:
        def __init__(self, *, use_github: bool):
            captured["use_github"] = use_github

        def run_research(self, **kwargs: Any) -> dict[str, Any]:
            captured["run"] = kwargs
            return {"success": True, "work_dir": str(tmp_path)}

    monkeypatch.setattr(runner_module, "IdeaManager", FakeManager)
    monkeypatch.setattr(runner_module, "ResearchRunner", FakeRunner)

    result = execute_autoresearch(
        instruction="Investigate whether the supplied cache can reduce tail latency.",
        workspace=tmp_path,
        ideas_dir=tmp_path / "ideas",
        iterations=2,
        time_limit_seconds=1740,
    )

    assert result["success"] is True
    assert captured["validate"] is True
    assert captured["use_github"] is False
    assert captured["idea"]["idea"]["metadata"]["local_workspace"] == str(tmp_path)
    assert captured["run"] == {
        "idea_id": "harbor-idea",
        "provider": "codex",
        "full_permissions": True,
        "multi_agent": True,
        "use_scribe": False,
        "write_paper": False,
        "scoring_enabled": True,
        "benchmark_mode": True,
        "hitl_autoresearch": "cli",
        "hitl_manager_no_browser": True,
        "hitl_mode": "auto",
        "autoresearch_iterations": 2,
        "time_limit_seconds": 1740,
        "workspace_mode": "embedded",
    }
    assert "autoresearch" not in captured["run"]


def test_child_entrypoint_invokes_focused_managed_ordinary_runner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    class FakeManager:
        def __init__(self, ideas_dir: Path):
            captured["ideas_dir"] = ideas_dir

        def submit_idea(self, idea: dict[str, Any], validate: bool) -> str:
            captured["idea"] = idea
            captured["validate"] = validate
            return "harbor-idea"

    class FakeRunner:
        def __init__(self, *, use_github: bool):
            captured["use_github"] = use_github

        def run_research(self, **kwargs: Any) -> dict[str, Any]:
            captured["run"] = kwargs
            captured["control"] = runner_module.active_hitl_run_stop_control()
            return {"success": True, "work_dir": str(tmp_path)}

    monkeypatch.setattr(runner_module, "IdeaManager", FakeManager)
    monkeypatch.setattr(runner_module, "ResearchRunner", FakeRunner)

    result = execute_focused_managed_ordinary(
        instruction="Implement the supplied benchmark task.",
        workspace=tmp_path,
        ideas_dir=tmp_path / "ideas",
        domain="software_maintenance",
    )

    assert result["success"] is True
    assert captured["validate"] is True
    assert captured["control"] is not None
    assert captured["control"].work_dir == tmp_path
    assert captured["idea"]["idea"]["metadata"]["tags"] == [
        "harbor",
        "focused-managed-ordinary",
    ]
    assert captured["idea"]["idea"]["domain"] == "software_maintenance"
    assert captured["run"] == {
        "idea_id": "harbor-idea",
        "provider": "codex",
        "full_permissions": True,
        "multi_agent": True,
        "use_scribe": False,
        "write_paper": False,
        "scoring_enabled": False,
        "benchmark_mode": True,
        "hitl_research": "cli",
        "hitl_manager_no_browser": True,
        "hitl_mode": "auto",
        "focused_autoresearch": True,
        "workspace_mode": "embedded",
    }


def test_child_translates_native_budget_stop_after_neurico_finalization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    class FakeManager:
        def __init__(self, ideas_dir: Path):
            pass

        def submit_idea(self, idea: dict[str, Any], validate: bool) -> str:
            return "harbor-idea"

    class FakeRunner:
        def __init__(self, *, use_github: bool):
            pass

        def run_research(self, **kwargs: Any) -> dict[str, Any]:
            captured.update(kwargs)
            raise runner_module.HitlRunStopRequested("HITL run stopped: budget_exhausted.")

    monkeypatch.setattr(runner_module, "IdeaManager", FakeManager)
    monkeypatch.setattr(runner_module, "ResearchRunner", FakeRunner)
    result = execute_autoresearch(
        instruction="Run until the benchmark budget expires.",
        workspace=tmp_path,
        ideas_dir=tmp_path / "ideas",
        time_limit_seconds=20,
    )

    assert result["stopped"] is True
    assert result["time_limit_reached"] is True
    assert captured["time_limit_seconds"] == 20


def test_harbor_interrupt_requests_native_run_stop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[str] = []

    class FakeControl:
        def request(self, *, requested_by: str) -> None:
            requests.append(requested_by)

    control = FakeControl()
    monkeypatch.setattr(runner_module, "active_hitl_run_stop_control", lambda: control)
    stop_requested = runner_module.threading.Event()
    finished = runner_module.threading.Event()
    stop_requested.set()

    runner_module._propagate_native_stop(stop_requested, finished)

    assert requests == ["harbor_cancel"]


def test_child_does_not_reclassify_non_budget_native_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeManager:
        def __init__(self, ideas_dir: Path):
            pass

        def submit_idea(self, idea: dict[str, Any], validate: bool) -> str:
            return "harbor-idea"

    class FakeRunner:
        def __init__(self, *, use_github: bool):
            pass

        def run_research(self, **kwargs: Any) -> dict[str, Any]:
            raise runner_module.HitlRunStopRequested("HITL run stopped: provider_unavailable.")

    monkeypatch.setattr(runner_module, "IdeaManager", FakeManager)
    monkeypatch.setattr(runner_module, "ResearchRunner", FakeRunner)

    with pytest.raises(runner_module.HitlRunStopRequested, match="provider_unavailable"):
        execute_autoresearch(
            instruction="Run this benchmark.",
            workspace=tmp_path,
            ideas_dir=tmp_path / "ideas",
            time_limit_seconds=20,
        )


def test_acp_prompt_launches_autoresearch_not_direct_inference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    instruction = "Keep this exact:\n\n  value: '# literal'\n"
    captured: dict[str, Any] = {}
    task_venv = tmp_path / ".venv" / "pyvenv.cfg"
    task_venv.parent.mkdir()
    task_venv.write_text("owned by task\n")

    async def fake_autoresearch(**kwargs: Any) -> int:
        captured.update(kwargs)
        await kwargs["emit"]("AutoResearch output\n")
        return 0

    monkeypatch.setattr(agent_module, "run_autoresearch_process", fake_autoresearch)

    async def run_prompt() -> None:
        auth_file = tmp_path / "auth.json"
        auth_file.write_text('{"tokens": {}}')
        agent = NeuricoHarborAgent(
            {
                "NEURICO_MODEL": "openai/test-model",
                "NEURICO_CODEX_AUTH_FILE": str(auth_file),
                "NEURICO_HARBOR_TIME_LIMIT_SECONDS": "1740",
            }
        )
        session = await agent.new_session(cwd=str(tmp_path), mcp_servers=[])
        response = await agent.prompt(
            session_id=session.session_id,
            prompt=[{"type": "text", "text": instruction}],
        )
        assert response.stop_reason == "end_turn"

    asyncio.run(run_prompt())
    assert captured["task"].instruction == instruction
    assert captured["task"].workspace == tmp_path
    assert captured["workflow"] == "autoresearch"
    assert captured["reasoning_effort"] is None
    assert captured["iterations"] == 1
    assert captured["time_limit_seconds"] == 1740
    assert captured["connection"].backend_model == "test-model"
    assert captured["connection"].mode == "chatgpt"
    assert task_venv.read_text() == "owned by task\n"


def test_acp_prompt_launches_focused_managed_ordinary_without_autoresearch_controls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    async def fake_runner(**kwargs: Any) -> int:
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(agent_module, "run_autoresearch_process", fake_runner)

    async def run_prompt() -> None:
        auth_file = tmp_path / "auth.json"
        auth_file.write_text('{"tokens": {}}')
        agent = NeuricoHarborAgent(
            {
                "NEURICO_MODEL": "openai/test-model",
                "NEURICO_CODEX_AUTH_FILE": str(auth_file),
                "NEURICO_HARBOR_WORKFLOW": "focused-managed-ordinary",
                "NEURICO_HARBOR_REASONING_EFFORT": "high",
                "NEURICO_HARBOR_DOMAIN": "software_maintenance",
                "NEURICO_HARBOR_AUTORESEARCH_ITERATIONS": "invalid but unused",
                "NEURICO_HARBOR_TIME_LIMIT_SECONDS": "invalid but unused",
            }
        )
        session = await agent.new_session(cwd=str(tmp_path), mcp_servers=[])
        response = await agent.prompt(
            session_id=session.session_id,
            prompt=[{"type": "text", "text": "Implement the supplied task."}],
        )
        assert response.stop_reason == "end_turn"

    asyncio.run(run_prompt())
    assert captured["workflow"] == "focused-managed-ordinary"
    assert captured["domain"] == "software_maintenance"
    assert captured["reasoning_effort"] == "high"
    assert captured["iterations"] is None
    assert captured["time_limit_seconds"] is None


def test_autoresearch_failure_fails_the_acp_turn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    task_venv = tmp_path / ".venv" / "pyvenv.cfg"
    task_venv.parent.mkdir()
    task_venv.write_text("owned by task\n")

    async def failing_autoresearch(**kwargs: Any) -> int:
        return 7

    monkeypatch.setattr(agent_module, "run_autoresearch_process", failing_autoresearch)

    async def run_prompt() -> None:
        auth_file = tmp_path / "auth.json"
        auth_file.write_text('{"tokens": {}}')
        agent = NeuricoHarborAgent(
            {
                "NEURICO_MODEL": "openai/test-model",
                "NEURICO_CODEX_AUTH_FILE": str(auth_file),
            }
        )
        session = await agent.new_session(cwd=str(tmp_path), mcp_servers=[])
        with pytest.raises(RuntimeError, match="status 7"):
            await agent.prompt(
                session_id=session.session_id,
                prompt=[{"type": "text", "text": "Run AutoResearch on this task"}],
            )

    asyncio.run(run_prompt())
    assert task_venv.read_text() == "owned by task\n"


def test_task_provided_mcp_servers_are_rejected_explicitly(tmp_path: Path) -> None:
    async def exercise() -> None:
        agent = NeuricoHarborAgent({"NEURICO_MODEL": "openai/test-model"})
        with pytest.raises(RequestError):
            await agent.new_session(
                cwd=str(tmp_path),
                mcp_servers=[{"name": "task-tools"}],
            )

    asyncio.run(exercise())


def test_stdio_acp_handshake_and_model_selection(tmp_path: Path) -> None:
    class RecordingClient(Client):
        async def request_permission(self, session_id, tool_call, options, **kwargs: Any):
            return {"outcome": {"outcome": "cancelled"}}

        async def session_update(self, session_id, update, **kwargs: Any) -> None:
            return None

    async def exercise_protocol() -> None:
        environment = dict(os.environ)
        environment["NEURICO_MODEL"] = "openai/test-model"
        async with spawn_agent_process(
            RecordingClient(),
            sys.executable,
            "-m",
            "neurico_harbor_agent",
            env=environment,
            cwd=tmp_path,
        ) as (connection, _process):
            initialized = await connection.initialize(protocol_version=PROTOCOL_VERSION)
            assert initialized.agent_info is not None
            assert initialized.agent_info.name == "neurico"

            session = await connection.new_session(cwd=str(tmp_path), mcp_servers=[])
            assert session.config_options is not None
            model_option = session.config_options[0]
            assert model_option.id == "model"
            assert model_option.current_value == "openai/test-model"

            response = await connection.set_config_option(
                session_id=session.session_id,
                config_id="model",
                value="openai/test-model",
            )
            assert response.config_options[0].current_value == "openai/test-model"

    asyncio.run(exercise_protocol())
