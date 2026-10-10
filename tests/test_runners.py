"""Simulated CLI fixtures: these tests do not verify live model capabilities."""

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from threading import Event

import pytest

from agentic_engineering.runners import RunnerAdapter, RunnerError

SESSION = "0199a213-81c0-7800-8aa1-bbab2a035a53"


def jsonl(*events):
    return "\n".join(json.dumps(event) for event in events)


def codex_output(text="done", session=SESSION):
    return jsonl(
        {"type": "thread.started", "thread_id": session},
        {"type": "turn.started"},
        {"type": "item.completed", "item": {"id": "item_0", "type": "agent_message", "text": text}},
        {"type": "turn.completed", "usage": {"input_tokens": 2, "output_tokens": 1}},
    )


def claude_output(text="done", session=SESSION):
    return jsonl(
        {
            "type": "system",
            "subtype": "init",
            "session_id": session,
            "model": "test-model",
            "tools": [],
        },
        {
            "type": "assistant",
            "session_id": session,
            "parent_tool_use_id": None,
            "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
        },
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": text,
            "session_id": session,
            "permission_denials": [],
        },
    )


@pytest.mark.parametrize("name", ["codex", "claude"])
def test_commands_use_stdin_explicit_model_and_explicit_resume_only(name):
    runner = RunnerAdapter(name, model="fixed-model")
    fresh = runner.build_argv("--dangerously-bypass $(whoami)", role="worker")
    resumed = runner.build_argv("repair", role="worker", session_id=SESSION)
    assert "--dangerously-bypass $(whoami)" not in fresh
    assert fresh[fresh.index("--model") + 1] == "fixed-model"
    assert SESSION not in fresh
    assert SESSION in resumed
    assert not {"--last", "--continue", "--fallback-model", "--full-auto"}.intersection(resumed)
    if name == "codex":
        assert fresh[-1] == "-"
        assert fresh[fresh.index("--sandbox") + 1] == "workspace-write"
        assert resumed.index("--sandbox") < resumed.index("resume")
        assert resumed[-2:] == [SESSION, "-"]
    else:
        assert "--print" in fresh
        assert fresh[fresh.index("--output-format") + 1] == "stream-json"
        assert resumed[resumed.index("--resume") + 1] == SESSION
        assert fresh[fresh.index("--permission-mode") + 1] == "dontAsk"


@pytest.mark.parametrize("name", ["codex", "claude"])
def test_reviewer_has_no_edit_authority(name):
    argv = RunnerAdapter(name).build_argv("review exact diff", role="reviewer")
    if name == "codex":
        assert argv[argv.index("--sandbox") + 1] == "read-only"
    else:
        assert argv[argv.index("--tools") + 1] == ""
        assert "--allowedTools" not in argv
    assert not any("bypass" in arg for arg in argv)


@pytest.mark.parametrize("name", ["codex", "claude"])
def test_untrusted_project_settings_hooks_and_mcp_are_not_autoloaded(name):
    argv = RunnerAdapter(name).build_argv("work")
    if name == "codex":
        assert "--ignore-user-config" in argv
        assert "--ignore-rules" in argv
    else:
        assert argv[argv.index("--setting-sources") + 1] == ""
        assert json.loads(argv[argv.index("--settings") + 1])["disableAllHooks"] is True
        assert json.loads(argv[argv.index("--mcp-config") + 1]) == {"mcpServers": {}}
        assert "--strict-mcp-config" in argv


@pytest.mark.parametrize("name", ["codex", "claude"])
@pytest.mark.parametrize("session", ["", "latest", "--last", "../transcript.jsonl"])
def test_resume_refuses_ambiguous_names_paths_and_flags(name, session):
    with pytest.raises(ValueError):
        RunnerAdapter(name).build_argv("work", session_id=session)


@pytest.mark.parametrize("name,output", [("codex", codex_output()), ("claude", claude_output())])
def test_completed_output_retains_session_text_and_original_events(name, output):
    result = RunnerAdapter(name).parse_output(output, expected_session_id=SESSION)
    assert result.session_id == SESSION
    assert result.text == "done"
    assert len(result.events) >= 3
    assert result.events[0] == json.loads(output.splitlines()[0])


@pytest.mark.parametrize("name,output", [("codex", codex_output()), ("claude", claude_output())])
def test_resume_output_cannot_switch_sessions(name, output):
    with pytest.raises(RunnerError, match="session"):
        RunnerAdapter(name).parse_output(
            output, expected_session_id="0199a213-81c0-7800-8aa1-bbab2a035a54"
        )


@pytest.mark.parametrize("name", ["codex", "claude"])
@pytest.mark.parametrize(
    "output",
    [
        "",
        "approved",
        "[]",
        '{"type":"unknown"}',
        '{"type":"result","type":"turn.completed"}',
        '{"type":"turn.completed","usage":NaN}',
    ],
)
def test_malformed_unknown_or_incomplete_output_never_succeeds(name, output):
    with pytest.raises(RunnerError):
        RunnerAdapter(name).parse_output(output)


@pytest.mark.parametrize("name,output", [("codex", codex_output()), ("claude", claude_output())])
def test_missing_final_event_and_events_after_final_are_blocked(name, output):
    with pytest.raises(RunnerError):
        RunnerAdapter(name).parse_output("\n".join(output.splitlines()[:-1]))
    with pytest.raises(RunnerError):
        RunnerAdapter(name).parse_output(output + '\n{"type":"error","message":"late error"}')


def test_codex_unknown_item_or_failed_turn_is_blocked():
    prefix = jsonl({"type": "thread.started", "thread_id": SESSION}, {"type": "turn.started"})
    for event in [
        {"type": "turn.failed", "error": {"message": "provider failed"}},
        {"type": "item.completed", "item": {"id": "x", "type": "unknown"}},
        {"type": "item.completed", "item": {"id": "x", "type": "agent_message", "text": 1}},
    ]:
        with pytest.raises(RunnerError):
            RunnerAdapter("codex").parse_output(prefix + "\n" + jsonl(event))


@pytest.mark.parametrize(
    "patch",
    [
        {"is_error": True},
        {"subtype": "error_max_turns"},
        {"permission_denials": [{"tool_name": "Bash"}]},
        {"result": 1},
        {"session_id": "unknown"},
    ],
)
def test_claude_error_or_denied_result_is_blocked(patch):
    events = [json.loads(line) for line in claude_output().splitlines()]
    events[-1].update(patch)
    with pytest.raises(RunnerError):
        RunnerAdapter("claude").parse_output(jsonl(*events))


@dataclass
class FixtureProcessResult:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str = ""
    duration_seconds: float = 0.0
    timed_out: bool = False
    cancelled: bool = False


@pytest.fixture
def fixture_cli(tmp_path):
    path = tmp_path / "simulated_cli.py"
    path.write_text("""import json, sys, time
args = sys.argv[1:]
prompt = sys.stdin.read()
if prompt == "timeout":
    time.sleep(2)
if prompt == "nonzero":
    print("partial artifact")
    sys.exit(7)
if prompt == "malformed":
    print("not json")
    sys.exit(0)
session = "0199a213-81c0-7800-8aa1-bbab2a035a53"
if "resume" in args:
    session = args[-2]
if "--resume" in args:
    session = args[args.index("--resume") + 1]
if "--json" in args:
    events = [{"type":"thread.started","thread_id":session}, {"type":"turn.started"},
      {"type":"item.completed","item":{"id":"0","type":"agent_message","text":prompt}},
      {"type":"turn.completed","usage":{}}]
else:
    events = [{"type":"system","subtype":"init","session_id":session},
      {"type":"result","subtype":"success","is_error":False,"session_id":session,
       "result":prompt,"permission_denials":[]}]
for event in events:
    print(json.dumps(event))
""")
    return path


def fixture_execute(path: Path):
    """Real child process, simulated CLI; production never calls subprocess here."""

    def execute(argv, timeout_seconds, input_text=None, cancel_event=None):
        if cancel_event is not None and cancel_event.is_set():
            return FixtureProcessResult(argv, -15, "partial interruption", cancelled=True)
        try:
            completed = subprocess.run(
                [sys.executable, str(path), *argv[1:]],
                input=input_text,
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as error:
            return FixtureProcessResult(argv, -9, (error.stdout or b"").decode(), timed_out=True)
        return FixtureProcessResult(argv, completed.returncode, completed.stdout, completed.stderr)

    return execute


@pytest.mark.parametrize("name", ["codex", "claude"])
def test_actual_simulated_cli_executes_via_injected_environment_and_resumes(name, fixture_cli):
    result = RunnerAdapter(name).run(
        fixture_execute(fixture_cli),
        "--literal prompt $(id)",
        timeout_seconds=2,
        session_id=SESSION,
    )
    assert result.text == "--literal prompt $(id)"
    assert result.session_id == SESSION


@pytest.mark.parametrize("mode", ["nonzero", "timeout", "malformed"])
def test_process_failures_retain_partial_artifacts(mode, fixture_cli):
    with pytest.raises(RunnerError) as caught:
        RunnerAdapter("codex").run(fixture_execute(fixture_cli), mode, timeout_seconds=0.1)
    assert caught.value.process_result is not None
    if mode == "nonzero":
        assert caught.value.process_result.returncode == 7
        assert "partial artifact" in caught.value.process_result.stdout
    elif mode == "timeout":
        assert caught.value.process_result.timed_out


def test_cancellation_does_not_parse_or_approve_partial_output(fixture_cli):
    cancel = Event()
    cancel.set()
    with pytest.raises(RunnerError) as caught:
        RunnerAdapter("codex").run(
            fixture_execute(fixture_cli), "work", timeout_seconds=1, cancel_event=cancel
        )
    assert caught.value.process_result.cancelled


def test_missing_executable_is_blocked_without_fallback():
    def unavailable(argv, timeout_seconds, input_text=None, cancel_event=None):
        raise FileNotFoundError("runner unavailable")

    with pytest.raises(RunnerError, match="unavailable"):
        RunnerAdapter("codex").run(unavailable, "work", timeout_seconds=1)


@pytest.mark.parametrize("kwargs", [{"name": "unknown"}, {"name": "codex", "model": "--flag"}])
def test_unsupported_runner_and_model_option_injection_are_rejected(kwargs):
    with pytest.raises(ValueError):
        RunnerAdapter(**kwargs)


def test_codex_completed_turn_with_unfinished_command_is_blocked():
    events = [json.loads(line) for line in codex_output().splitlines()]
    events.insert(
        2,
        {
            "type": "item.started",
            "item": {
                "id": "cmd",
                "type": "command_execution",
                "command": "sleep 10",
                "status": "in_progress",
            },
        },
    )
    with pytest.raises(RunnerError, match="unfinished"):
        RunnerAdapter("codex").parse_output(jsonl(*events))


def test_codex_progress_items_complete_before_terminal_message():
    events = [json.loads(line) for line in codex_output().splitlines()]
    events[2:2] = [
        {
            "type": "item.started",
            "item": {
                "id": "cmd",
                "type": "command_execution",
                "command": "pwd",
                "status": "in_progress",
            },
        },
        {
            "type": "item.completed",
            "item": {
                "id": "cmd",
                "type": "command_execution",
                "command": "pwd",
                "status": "completed",
                "exit_code": 0,
                "aggregated_output": "/work",
            },
        },
    ]
    assert RunnerAdapter("codex").parse_output(jsonl(*events)).text == "done"


def test_codex_disables_hook_feature_even_when_project_configuration_enables_it():
    argv = RunnerAdapter("codex").build_argv("work")
    assert any(argv[index : index + 2] == ["--disable", "hooks"] for index in range(len(argv)))
