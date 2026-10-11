"""Provider checks use native status/catalog responses and never infer login from models."""

import importlib
import json
import os
import sys
import time
from datetime import datetime

import pytest


def providers():
    try:
        return importlib.import_module("agentic_engineering.providers")
    except ModuleNotFoundError:
        pytest.fail("Provider inspection must report missing CLIs without running inference")


def executable(tmp_path, monkeypatch, name, body):
    path = tmp_path / name
    path.write_text(f"#!{sys.executable}\n" + body)
    path.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))
    return path


def codex_cli(tmp_path, monkeypatch, account, pages, malformed=False):
    return executable(
        tmp_path,
        monkeypatch,
        "codex",
        f"""
import json, sys
account = {account!r}
pages = {pages!r}
for line in sys.stdin:
    request = json.loads(line)
    method = request['method']
    if method == 'initialized':
        continue
    if method == 'initialize':
        result = {{}}
    elif method == 'account/read':
        assert request['params'] == {{'refreshToken': False}}
        result = account
    elif method == 'model/list':
        assert request['params']['includeHidden'] is False
        if {malformed!r}:
            print('untrusted secret diagnostic', flush=True)
            continue
        cursor = request['params'].get('cursor')
        result = pages[0 if cursor is None else 1]
    else:
        raise AssertionError('Unexpected or mutating RPC: ' + method)
    print(json.dumps({{'id': request['id'], 'result': result}}), flush=True)
""",
    )


def claude_cli(tmp_path, monkeypatch, status, code=0, models=None):
    return executable(
        tmp_path,
        monkeypatch,
        "claude",
        f"""
import json, sys
if sys.argv[1:] == ['auth', 'status', '--json']:
    print(json.dumps({status!r}))
    sys.exit({code})
assert '--no-session-persistence' in sys.argv
assert '--strict-mcp-config' in sys.argv
assert json.loads(sys.argv[sys.argv.index('--settings')+1])['disableAllHooks'] is True
for line in sys.stdin:
    request = json.loads(line)
    assert request['type'] == 'control_request'
    assert request['request']['subtype'] == 'initialize'
    print(json.dumps({{'type': 'control_response', 'response': {{
        'subtype': 'success', 'request_id': request['request_id'],
        'response': {{'models': {models!r}, 'account': {{'email': 'private@example.invalid'}}}}
    }}}}), flush=True)
""",
    )


def agy_events(model="new-flash", *, tool=False):
    session = "57ea62a5-bf57-4548-861c-d15c0c385482"
    values = [
        {
            "event": "init",
            "conversation_id": session,
            "init": {
                "cwd": "/fixture",
                "tools": [],
                "permission_mode": "strict",
                "model": model,
            },
        },
    ]
    if tool:
        values.append(
            {
                "event": "step_update",
                "step_update": {
                    "conversation_id": session,
                    "step_index": 0,
                    "state": "DONE",
                    "step_type": "tool",
                    "tool_name": "view_file",
                    "tool_info": {"name": "view_file", "parameters": {}, "output": "read"},
                },
            }
        )
    values.append(
        {
            "event": "result",
            "result": {
                "conversation_id": session,
                "status": "SUCCESS",
                "response": "RAPID_SHIP_AUTH_OK",
                "duration_seconds": 0.1,
                "num_turns": 1,
                "usage": {
                    "input_tokens": 1,
                    "output_tokens": 1,
                    "thinking_tokens": 0,
                    "cache_read_tokens": 0,
                    "total_tokens": 2,
                },
            },
        }
    )
    return values


def agy_cli(tmp_path, monkeypatch, catalog="new-flash\tNew Flash\n", events=None, code=0):
    log = tmp_path / "invocations.jsonl"
    executable(
        tmp_path,
        monkeypatch,
        "agy",
        f"""
import json, pathlib, sys
with open({str(log)!r}, 'a') as stream:
    stream.write(json.dumps(sys.argv[1:])+'\\n')
if sys.argv[1:] == ['models']:
    print({catalog!r}, end='')
    sys.exit(0)
assert sys.argv[sys.argv.index('--model')+1] == 'new-flash'
assert '--dangerously-skip-permissions' not in sys.argv
assert '--agent' in sys.argv
agent = pathlib.Path('.agents/agents/rapid-ship-auth.md').read_text()
assert 'tools: []' in agent
events = {events!r} or []
if events:
    print(json.dumps(events[0]), flush=True)
for line in sys.stdin:
    with open({str(tmp_path / "prompts.jsonl")!r}, 'a') as stream:
        stream.write(line)
    for event in events[1:]:
        print(json.dumps(event), flush=True)
    break
sys.exit({code})
""",
    )
    return log


@pytest.mark.parametrize("name", ["codex", "claude", "agy"])
def test_missing_cli_is_not_ready_or_authenticated(tmp_path, monkeypatch, name):
    monkeypatch.setenv("PATH", str(tmp_path))
    result = providers().inspect_provider(name)
    assert result["provider"] == name
    assert result["installed"] is False
    assert result["authenticated"] is None
    assert result["models"] == []
    assert result["ready"] is False
    assert datetime.fromisoformat(result["checked_at"]).utcoffset().total_seconds() == 0
    assert name in result["hint"]


def test_codex_uses_native_auth_and_paged_catalog_without_leaking_identity(tmp_path, monkeypatch):
    codex_cli(
        tmp_path,
        monkeypatch,
        {"account": {"type": "chatgpt", "email": "private"}},
        [
            {
                "data": [{"id": "internal", "model": "new-code", "displayName": "New Code"}],
                "nextCursor": "page-two",
            },
            {"data": [{"model": "new-review", "displayName": "New Review"}], "nextCursor": None},
        ],
    )
    result = providers().inspect_provider("codex")
    assert result["authenticated"] is True
    assert result["models"] == [
        {"id": "new-code", "label": "New Code"},
        {"id": "new-review", "label": "New Review"},
    ]
    assert result["ready"] is True
    assert "private" not in json.dumps(result)


@pytest.mark.parametrize(("requires_auth", "expected"), [(True, False), (False, None)])
def test_codex_catalog_does_not_establish_authentication(
    tmp_path, monkeypatch, requires_auth, expected
):
    codex_cli(
        tmp_path,
        monkeypatch,
        {"account": None, "requiresOpenaiAuth": requires_auth},
        [
            {"data": [{"model": "cached-model", "displayName": "Cached model"}]},
        ],
    )
    result = providers().inspect_provider("codex")
    assert result["models"]
    assert result["authenticated"] is expected
    assert result["ready"] is False


@pytest.mark.parametrize(
    "bad", [None, {}, [{"model": 42}], [{"model": "", "displayName": "Empty"}]]
)
def test_bad_codex_catalog_preserves_known_auth_but_blocks_readiness(tmp_path, monkeypatch, bad):
    codex_cli(tmp_path, monkeypatch, {"account": {"type": "apiKey"}}, [{"data": bad}])
    result = providers().inspect_provider("codex")
    assert result["authenticated"] is True
    assert result["models"] == []
    assert result["ready"] is False


def test_codex_malformed_protocol_is_redacted(tmp_path, monkeypatch):
    codex_cli(tmp_path, monkeypatch, {"account": {"type": "chatgpt"}}, [], malformed=True)
    result = providers().inspect_provider("codex")
    assert result["ready"] is False
    assert "secret" not in json.dumps(result)


@pytest.mark.parametrize("account_type", [[], {}, 42, "unsupported-auth"])
def test_codex_unrecognized_auth_shape_stays_unknown(tmp_path, monkeypatch, account_type):
    codex_cli(tmp_path, monkeypatch, {"account": {"type": account_type}}, [{"data": []}])
    result = providers().inspect_provider("codex")
    assert result["authenticated"] is None
    assert result["ready"] is False


def test_claude_catalog_preserves_native_aliases_and_separate_auth(tmp_path, monkeypatch):
    claude_cli(
        tmp_path,
        monkeypatch,
        {"loggedIn": True, "email": "private"},
        models=[
            {"value": "native-alias", "displayName": "Native model"},
        ],
    )
    result = providers().inspect_provider("claude")
    assert result["authenticated"] is True
    assert result["models"] == [{"id": "native-alias", "label": "Native model"}]
    assert result["ready"] is True
    assert "private" not in json.dumps(result)


@pytest.mark.parametrize(
    ("status", "code", "expected"),
    [
        ({"loggedIn": False}, 1, False),
        ({"loggedIn": "true"}, 0, None),
        ({"loggedIn": True}, 1, None),
        ({}, 0, None),
    ],
)
def test_claude_missing_or_invalid_auth_is_not_ready(tmp_path, monkeypatch, status, code, expected):
    claude_cli(tmp_path, monkeypatch, status, code=code, models=[])
    result = providers().inspect_provider("claude")
    assert result["authenticated"] is expected
    assert result["ready"] is False


def test_agy_reads_tsv_catalog_without_claiming_auth_or_sending_prompt(tmp_path, monkeypatch):
    log = agy_cli(tmp_path, monkeypatch)
    result = providers().inspect_provider("agy")
    assert result["models"] == [{"id": "new-flash", "label": "New Flash"}]
    assert result["authenticated"] is None
    assert result["ready"] is False
    assert [json.loads(line) for line in log.read_text().splitlines()] == [["models"]]


@pytest.mark.parametrize("catalog", ["", "login required\n", "\tMissing ID\n", "model\t\n"])
def test_agy_malformed_catalog_is_not_a_model_choice(tmp_path, monkeypatch, catalog):
    agy_cli(tmp_path, monkeypatch, catalog=catalog)
    result = providers().inspect_provider("agy")
    assert result["models"] == []
    assert result["ready"] is False


@pytest.mark.parametrize("name", ["codex", "claude", "agy"])
def test_timeout_is_bounded_and_probe_process_is_reaped(tmp_path, monkeypatch, name):
    pidfile = tmp_path / "pid"
    executable(
        tmp_path,
        monkeypatch,
        name,
        f"import os,time\nopen({str(pidfile)!r},'w').write(str(os.getpid()))\ntime.sleep(60)\n",
    )
    monkeypatch.setattr(providers(), "PROBE_TIMEOUT_SECONDS", 1.0)
    started = time.monotonic()
    result = providers().inspect_provider(name)
    assert time.monotonic() - started < 3
    assert result["ready"] is False
    assert "timed out" in result["hint"]
    with pytest.raises(ProcessLookupError):
        os.kill(int(pidfile.read_text()), 0)


def test_unknown_provider_is_rejected():
    with pytest.raises(ValueError, match="provider"):
        providers().inspect_provider("unknown")


def test_agy_verification_uses_only_selected_catalog_model_and_records_request_scope(
    tmp_path, monkeypatch
):
    log = agy_cli(tmp_path, monkeypatch, events=agy_events())
    result = providers().verify_provider("agy", "new-flash")
    assert result["authenticated"] is True
    assert result["ready"] is True
    assert result["verified"] is True
    assert result["selected_model"] == "new-flash"
    assert result["verification_method"] == "inference"
    assert result["verified_at"]
    assert "request" in result["hint"]
    assert len(log.read_text().splitlines()) == 2


def test_agy_verification_never_substitutes_an_unlisted_model(tmp_path, monkeypatch):
    log = agy_cli(tmp_path, monkeypatch, events=agy_events())
    result = providers().verify_provider("agy", "not-listed")
    assert result["verified"] is False
    assert result["ready"] is False
    assert len(log.read_text().splitlines()) == 1


@pytest.mark.parametrize("failure", ["tools", "missing-tools", "missing-init", "model"])
def test_agy_sends_no_prompt_until_native_session_confirms_selected_model_without_tools(
    tmp_path, monkeypatch, failure
):
    events = agy_events()
    if failure == "tools":
        events[0]["init"]["tools"] = ["run_command", "call_mcp_tool"]
    elif failure == "missing-tools":
        del events[0]["init"]["tools"]
    elif failure == "missing-init":
        events.pop(0)
    else:
        events[0]["init"]["model"] = "wrong-model"
    agy_cli(tmp_path, monkeypatch, events=events)

    result = providers().verify_provider("agy", "new-flash")

    assert not (tmp_path / "prompts.jsonl").exists()
    assert result["verified"] is False
    assert result["ready"] is False
    assert result["request_sent"] is False
    assert "no authentication prompt was sent" in result["hint"]


@pytest.mark.parametrize("failure", ["model", "tool", "failed", "missing", "exit"])
def test_agy_verification_rejects_incomplete_changed_or_tool_using_turns(
    tmp_path, monkeypatch, failure
):
    events = agy_events(
        model="other" if failure == "model" else "new-flash", tool=failure == "tool"
    )
    if failure == "failed":
        events[-1]["result"]["status"] = "FAILED"
    if failure == "missing":
        events.pop()
    agy_cli(tmp_path, monkeypatch, events=events, code=1 if failure == "exit" else 0)
    result = providers().verify_provider("agy", "new-flash")
    assert result["verified"] is False
    assert result["ready"] is False
    assert result["authenticated"] is not True
