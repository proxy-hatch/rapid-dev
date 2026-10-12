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
        {
            "type": "turn.completed",
            "usage": {"input_tokens": 2, "cached_input_tokens": 0, "output_tokens": 1},
        },
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
      {"type":"turn.completed","usage":{"input_tokens":2,"cached_input_tokens":0,"output_tokens":1}}]
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
                "aggregated_output": "",
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
                "aggregated_output": "",
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


@pytest.mark.parametrize("contradiction", ["update", "complete", "reuse"])
def test_codex_item_type_identity_survives_updates_completion_and_reuse(contradiction):
    events = [json.loads(line) for line in codex_output().splitlines()]
    command = {
        "id": "cmd",
        "type": "command_execution",
        "command": "sleep 10",
        "status": "in_progress",
        "aggregated_output": "",
    }
    if contradiction == "reuse":
        command.update(status="completed", exit_code=0)
        events.insert(2, {"type": "item.completed", "item": command})
    else:
        events.insert(2, {"type": "item.started", "item": command})
    events.insert(
        3,
        {
            "type": "item.updated" if contradiction == "update" else "item.completed",
            "item": {"id": "cmd", "type": "agent_message", "text": "done"},
        },
    )
    if contradiction == "update":
        events.insert(
            4,
            {"type": "item.completed", "item": {**command, "status": "completed", "exit_code": 0}},
        )
    with pytest.raises(RunnerError, match=r"identity|type|completed"):
        RunnerAdapter("codex").parse_output(jsonl(*events))


def test_codex_completed_item_cannot_restart_or_complete_twice():
    events = [json.loads(line) for line in codex_output().splitlines()]
    for kind in ["item.started", "item.completed"]:
        malformed = events[:3] + [{"type": kind, "item": events[2]["item"]}] + events[3:]
        with pytest.raises(RunnerError, match="completed"):
            RunnerAdapter("codex").parse_output(jsonl(*malformed))


@pytest.mark.parametrize(
    "item",
    [
        {"id": "c", "type": "command_execution"},
        {
            "id": "c",
            "type": "command_execution",
            "command": "pwd",
            "aggregated_output": "",
            "status": "in_progress",
        },
        {
            "id": "c",
            "type": "command_execution",
            "command": "pwd",
            "aggregated_output": [],
            "status": "completed",
            "exit_code": 0,
        },
        {
            "id": "c",
            "type": "command_execution",
            "command": "pwd",
            "aggregated_output": "",
            "status": "completed",
            "exit_code": "0",
        },
        {"id": "c", "type": "reasoning"},
        {"id": "c", "type": "web_search"},
        {"id": "c", "type": "file_change", "status": "completed", "changes": [{}]},
        {"id": "c", "type": "todo_list", "items": [{"text": "work", "completed": "yes"}]},
        {
            "id": "c",
            "type": "mcp_tool_call",
            "server": "s",
            "tool": "t",
            "arguments": {},
            "status": "completed",
        },
    ],
)
def test_codex_known_item_kinds_require_valid_payloads(item):
    events = [json.loads(line) for line in codex_output().splitlines()]
    events.insert(2, {"type": "item.completed", "item": item})
    with pytest.raises(RunnerError):
        RunnerAdapter("codex").parse_output(jsonl(*events))


@pytest.mark.parametrize(
    "usage",
    [
        {},
        {"input_tokens": -1, "output_tokens": "bad"},
        {"input_tokens": True, "cached_input_tokens": 0, "output_tokens": 0},
        {"input_tokens": 1, "cached_input_tokens": -1, "output_tokens": 0},
        {"input_tokens": 1, "cached_input_tokens": 0, "output_tokens": 1.0},
    ],
)
def test_codex_usage_requires_complete_nonnegative_integer_counts(usage):
    events = [json.loads(line) for line in codex_output().splitlines()]
    events[-1]["usage"] = usage
    with pytest.raises(RunnerError, match="usage"):
        RunnerAdapter("codex").parse_output(jsonl(*events))


@pytest.mark.parametrize(
    "block",
    [
        {"type": "tool_use"},
        {"type": "tool_use", "id": "t", "name": "Read", "input": "file"},
        {"type": "tool_result"},
        {"type": "tool_result", "tool_use_id": "t", "content": 1},
        {"type": "thinking"},
        {"type": "redacted_thinking"},
        {"type": "image"},
        {"type": "document"},
    ],
)
def test_claude_known_content_kinds_require_valid_payloads(block):
    events = [json.loads(line) for line in claude_output().splitlines()]
    events[1]["message"]["content"] = [block]
    with pytest.raises(RunnerError):
        RunnerAdapter("claude").parse_output(jsonl(*events))


def test_supported_tool_and_command_payloads_preserve_final_result():
    events = [json.loads(line) for line in codex_output().splitlines()]
    items = [
        {
            "id": "cmd",
            "type": "command_execution",
            "command": "pwd",
            "aggregated_output": "/work",
            "status": "completed",
            "exit_code": 0,
        },
        {
            "id": "mcp",
            "type": "mcp_tool_call",
            "server": "docs",
            "tool": "read",
            "arguments": {},
            "status": "completed",
            "result": {"content": [], "structured_content": None},
        },
        {
            "id": "f",
            "type": "file_change",
            "status": "completed",
            "changes": [{"path": "src/main.py", "kind": "update"}],
        },
        {"id": "r", "type": "reasoning", "text": "inspect"},
        {"id": "w", "type": "web_search", "query": "docs"},
        {"id": "t", "type": "todo_list", "items": [{"text": "test", "completed": True}]},
    ]
    events[2:2] = [{"type": "item.completed", "item": item} for item in items]
    assert RunnerAdapter("codex").parse_output(jsonl(*events)).text == "done"
    claude = [json.loads(line) for line in claude_output().splitlines()]
    claude[1]["message"]["content"] = [
        {"type": "tool_use", "id": "read1", "name": "Read", "input": {"file_path": "main.py"}}
    ]
    claude.insert(
        2,
        {
            "type": "user",
            "session_id": SESSION,
            "message": {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "read1", "content": "print(1)"}],
            },
        },
    )
    assert RunnerAdapter("claude").parse_output(jsonl(*claude)).text == "done"


@pytest.mark.parametrize("mode", ["unfinished", "unknown-result", "duplicate-result"])
def test_claude_tool_lifecycle_requires_matching_unique_completion(mode):
    events = [json.loads(line) for line in claude_output().splitlines()]
    use = {"type": "tool_use", "id": "read1", "name": "Read", "input": {"file_path": "x"}}
    result = {
        "type": "user",
        "session_id": SESSION,
        "message": {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "read1", "content": "ok"}],
        },
    }
    if mode != "unknown-result":
        events[1]["message"]["content"] = [use]
    if mode != "unfinished":
        events.insert(2, result)
    if mode == "duplicate-result":
        events.insert(3, result)
    with pytest.raises(RunnerError, match="tool"):
        RunnerAdapter("claude").parse_output(jsonl(*events))


def agy_output(model="gemini-3.7-flash-medium", session=SESSION):
    """Documented standalone CLI wire format; no live capability claim."""
    return jsonl(
        {
            "event": "init",
            "conversation_id": session,
            "init": {
                "cwd": "/workspace",
                "tools": ["write_to_file"],
                "permission_mode": "request-review",
                "model": model,
            },
        },
        {
            "event": "step_update",
            "step_update": {
                "conversation_id": session,
                "step_index": 0,
                "state": "DONE",
                "step_type": "user_input",
            },
        },
        {
            "event": "step_update",
            "step_update": {
                "conversation_id": session,
                "step_index": 1,
                "state": "ACTIVE",
                "step_type": "agent_response",
                "text_delta": "do",
            },
        },
        {
            "event": "step_update",
            "step_update": {
                "conversation_id": session,
                "step_index": 1,
                "state": "DONE",
                "step_type": "agent_response",
                "text_delta": "ne",
            },
        },
        {
            "event": "result",
            "result": {
                "conversation_id": session,
                "status": "SUCCESS",
                "response": "done",
                "duration_seconds": 1.5,
                "num_turns": 1,
                "usage": {
                    "input_tokens": 4,
                    "output_tokens": 2,
                    "thinking_tokens": 0,
                    "cache_read_tokens": 0,
                    "total_tokens": 6,
                },
            },
        },
    )


def test_agy_uses_documented_stdin_protocol_and_explicit_session():
    runner = RunnerAdapter("agy", "gemini-3.7-flash-medium")
    argv = runner.build_argv("first\nsecond", session_id=SESSION)
    assert argv == [
        "agy",
        "--input-format",
        "stream-json",
        "--output-format",
        "stream-json",
        "--model",
        "gemini-3.7-flash-medium",
        "--conversation",
        SESSION,
    ]
    # agy has no per-role tool switch; a reviewer is read-only by instruction.
    assert runner.build_argv("first\nsecond", role="reviewer", session_id=SESSION) == argv
    stdin = runner.build_input("first\nsecond")
    assert len(stdin.splitlines()) == 1
    assert json.loads(stdin) == {"event": "user", "message": {"content": "first\nsecond"}}
    assert runner.parse_output(agy_output(), expected_session_id=SESSION).text == "done"


@pytest.mark.parametrize(
    "mode",
    [
        "status",
        "model",
        "missing-model",
        "session",
        "error",
        "unknown",
        "unfinished",
        "duplicate-step",
        "changed-step",
        "usage",
        "denial",
    ],
)
def test_agy_rejects_failure_incomplete_or_contradictory_output(mode):
    events = [json.loads(line) for line in agy_output().splitlines()]
    if mode == "status":
        events[-1]["result"]["status"] = "WAITING"
    elif mode == "model":
        events[0]["init"]["model"] = "different-model"
    elif mode == "missing-model":
        del events[0]["init"]["model"]
    elif mode == "session":
        events[-1]["result"]["conversation_id"] = "e7418679-9358-4163-bb74-d221f7b83e74"
    elif mode == "error":
        events[-1]["result"]["error"] = "failure despite success status"
    elif mode == "unknown":
        events.insert(-1, {"event": "permission_request"})
    elif mode == "unfinished":
        del events[-2]
    elif mode == "duplicate-step":
        events.insert(-1, events[-2])
    elif mode == "changed-step":
        events[-2]["step_update"]["step_type"] = "checkpoint"
    elif mode == "usage":
        events[-1]["result"]["usage"]["input_tokens"] = True
    elif mode == "denial":
        events[-1]["result"]["permission_denials"] = ["run_command"]
    with pytest.raises(RunnerError):
        RunnerAdapter("agy", "gemini-3.7-flash-medium").parse_output(jsonl(*events))


@pytest.mark.parametrize("failure", ["error", "ask_permission", "subagent_info"])
def test_agy_tool_errors_or_unverified_permission_and_subagent_steps_block(failure):
    events = [json.loads(line) for line in agy_output().splitlines()]
    tool = {
        "conversation_id": SESSION,
        "step_index": 2,
        "state": "DONE",
        "step_type": "tool",
        "tool_name": "write_to_file",
        "tool_info": {"name": "write_to_file", "parameters": {}, "output": "written"},
    }
    if failure == "error":
        tool["tool_info"]["error"] = {"type": "denied", "message": "permission required"}
    elif failure == "ask_permission":
        tool["tool_name"] = tool["tool_info"]["name"] = "ask_permission"
    else:
        tool["subagent_info"] = {"subagents": [{"conversation_id": SESSION}]}
    events.insert(-1, {"event": "step_update", "step_update": tool})
    with pytest.raises(RunnerError):
        RunnerAdapter("agy").parse_output(jsonl(*events))


def test_agy_stderr_soft_denial_cannot_look_like_success():
    with pytest.raises(RunnerError, match="diagnostic"):
        RunnerAdapter("agy").parse_output(agy_output(), stderr="run_command requires approval")


@pytest.mark.parametrize(
    "provider,role,model",
    [
        (None, "worker", "pinned"),
        ("native", "worker", "pinned"),
        ("sbx", "worker", "pinned"),
        ("docker", "worker", None),
        ("docker", "reviewer", None),
        ("native", "reviewer", None),
    ],
)
def test_agy_unverified_execution_never_launches_a_process(provider, role, model):
    def no_execute(*args, **kwargs):
        pytest.fail("Blocked agy configuration must not launch a process")

    with pytest.raises((RunnerError, ValueError)):
        RunnerAdapter("agy", model).run(
            no_execute, "work", role=role, execution_provider=provider, timeout_seconds=1
        )


@pytest.mark.parametrize(
    "role,provider",
    [("worker", "docker"), ("reviewer", "docker"), ("reviewer", "native")],
)
def test_agy_runner_delivers_one_stdin_turn_and_closes_the_pipe(tmp_path, role, provider):
    path = tmp_path / "simulated_agy.py"
    path.write_text(
        "import sys, json\n"
        "prompt = json.loads(sys.stdin.read())\n"
        "assert prompt == {'event':'user','message':{'content':'work'}}\n"
        f"sys.stdout.write({agy_output()!r})\n"
    )
    result = RunnerAdapter("agy", "gemini-3.7-flash-medium").run(
        fixture_execute(path), "work", role=role, execution_provider=provider, timeout_seconds=2
    )
    assert result.text == "done"


@pytest.mark.parametrize("session", ["", "latest", "--last", "../saved.jsonl", "not-a-uuid"])
def test_agy_rejects_ambiguous_conversation_identity(session):
    runner = RunnerAdapter("agy", "gemini-3.7-flash-medium")
    with pytest.raises(ValueError):
        runner.build_argv("work", session_id=session)
    with pytest.raises(RunnerError):
        runner.parse_output(agy_output(session=session))


@pytest.mark.parametrize(
    "field,value",
    [
        ("step_index", -1),
        ("step_index", True),
        ("state", "FAILED"),
        ("duration_seconds", -0.1),
        ("duration_seconds", True),
    ],
)
def test_agy_invalid_step_metadata_cannot_produce_success(field, value):
    events = [json.loads(line) for line in agy_output().splitlines()]
    events[-2]["step_update"][field] = value
    with pytest.raises(RunnerError):
        RunnerAdapter("agy").parse_output(jsonl(*events))


def test_agy_completed_tool_retains_output_without_granting_extra_permissions():
    events = [json.loads(line) for line in agy_output().splitlines()]
    events.insert(
        -1,
        {
            "event": "step_update",
            "step_update": {
                "conversation_id": SESSION,
                "step_index": 2,
                "state": "DONE",
                "step_type": "tool",
                "tool_name": "write_to_file",
                "tool_info": {
                    "name": "write_to_file",
                    "parameters": {"TargetFile": "/workspace/example.py"},
                    "output": "file written",
                },
            },
        },
    )
    result = RunnerAdapter("agy").parse_output(jsonl(*events))
    assert result.events[-2]["step_update"]["tool_info"]["output"] == "file written"


@pytest.mark.parametrize("timeout,flag", [(1800, "1800s"), (1e-7, "0.0000001s")])
def test_agy_headless_timeout_uses_the_assigned_task_budget(timeout, flag):
    commands = []

    def execute(argv, **kwargs):
        commands.append(argv)
        return FixtureProcessResult(argv, 0, agy_output())

    RunnerAdapter("agy", "gemini-3.7-flash-medium").run(
        execute, "work", execution_provider="docker", timeout_seconds=timeout
    )
    argv = commands[0]
    assert argv[argv.index("--print-timeout") + 1] == flag
