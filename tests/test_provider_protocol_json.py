"""Offline native CLI fixtures reject ambiguous JSON before it becomes provider evidence."""

import json

import pytest
from test_providers import executable, providers


def raw_claude_cli(tmp_path, monkeypatch, *, status, response=None):
    log = tmp_path / "requests.jsonl"
    executable(
        tmp_path,
        monkeypatch,
        "claude",
        f"""
import json, pathlib, sys
log = pathlib.Path({str(log)!r})
with log.open('a') as stream:
    stream.write(json.dumps(sys.argv[1:]) + '\\n')
if sys.argv[1:] == ['auth', 'status', '--json']:
    print({status!r})
    sys.exit(0)
for line in sys.stdin:
    with log.open('a') as stream:
        stream.write(line)
    request = json.loads(line)
    assert request['request']['subtype'] == 'initialize'
    response = {response!r}
    if response is None:
        response = json.dumps({{
            'type': 'control_response',
            'response': {{
                'subtype': 'success', 'request_id': request['request_id'],
                'response': {{'models': [{{'value': 'chosen', 'displayName': 'Chosen'}}]}}
            }}
        }})
    print(response, flush=True)
""",
    )
    return log


@pytest.mark.parametrize(
    "status",
    [
        '{"loggedIn":false,"loggedIn":true,"email":"PRIVATE_STATUS"}',
        *[
            '{"loggedIn":true,"metadata":{"private":"PRIVATE_STATUS","quota":' + constant + "}}"
            for constant in ("NaN", "Infinity", "-Infinity")
        ],
    ],
    ids=["duplicate-login", "nan", "infinity", "negative-infinity"],
)
def test_invalid_claude_status_cannot_authenticate_or_start_discovery(
    tmp_path, monkeypatch, status
):
    log = raw_claude_cli(tmp_path, monkeypatch, status=status)

    result = providers().verify_provider("claude", "chosen")

    assert result["authenticated"] is None
    assert result["ready"] is False
    assert result["verified"] is False
    assert result["verified_at"] is None
    assert result["request_sent"] is False
    assert result["models"] == []
    assert "PRIVATE_STATUS" not in json.dumps(result)
    assert [json.loads(line) for line in log.read_text().splitlines()] == [
        ["auth", "status", "--json"]
    ]


def raw_codex_cli(tmp_path, monkeypatch, catalog):
    log = tmp_path / "requests.jsonl"
    executable(
        tmp_path,
        monkeypatch,
        "codex",
        f"""
import json, pathlib, sys
for line in sys.stdin:
    with pathlib.Path({str(log)!r}).open('a') as stream:
        stream.write(line)
    request = json.loads(line)
    method = request['method']
    if method == 'initialized':
        continue
    if method == 'initialize':
        result = '{{}}'
    elif method == 'account/read':
        assert request['params'] == {{'refreshToken': False}}
        result = '{{"account":{{"type":"chatgpt"}}}}'
    elif method == 'model/list':
        result = {catalog!r}
    else:
        raise AssertionError('Unexpected RPC: ' + method)
    print('{{"id":' + json.dumps(request['id']) + ',"result":' + result + '}}', flush=True)
""",
    )
    return log


def malformed_catalog(provider, fault):
    id_key = "model" if provider == "codex" else "value"
    models_key = "data" if provider == "codex" else "models"
    entry = json.dumps({id_key: "chosen", "displayName": "Chosen"})
    metadata = '{"private":"PRIVATE_PROTOCOL"}'
    if fault == "duplicate-model":
        entry = (
            '{"' + id_key + '":"PRIVATE_PROTOCOL","' + id_key + '":"chosen","displayName":"Chosen"}'
        )
    elif fault == "duplicate-session":
        metadata = '{"session":{"id":"PRIVATE_PROTOCOL","id":"current"}}'
    else:
        metadata = '{"private":"PRIVATE_PROTOCOL","quota":' + fault + "}"
    return '{"' + models_key + '":[' + entry + '],"metadata":' + metadata + "}"


@pytest.mark.parametrize("provider", ["codex", "claude"])
@pytest.mark.parametrize(
    "fault", ["duplicate-model", "duplicate-session", "NaN", "Infinity", "-Infinity"]
)
def test_malformed_catalog_blocks_readiness_and_preserves_prior_authentication(
    tmp_path, monkeypatch, provider, fault
):
    catalog = malformed_catalog(provider, fault)
    if provider == "codex":
        log = raw_codex_cli(tmp_path, monkeypatch, catalog)
    else:
        log = raw_claude_cli(
            tmp_path,
            monkeypatch,
            status='{"loggedIn":true}',
            response=(
                '{"type":"control_response","response":{"subtype":"success",'
                '"request_id":"rapid-ship-discovery","response":' + catalog + "}}"
            ),
        )

    result = providers().inspect_provider(provider)

    assert result["authenticated"] is True
    assert result["ready"] is False
    assert result["models"] == []
    assert "PRIVATE_PROTOCOL" not in json.dumps(result)
    requests = [json.loads(line) for line in log.read_text().splitlines()]
    if provider == "codex":
        assert [request["method"] for request in requests] == [
            "initialize",
            "initialized",
            "account/read",
            "model/list",
        ]
    else:
        assert len(requests) == 3
        assert requests[0] == ["auth", "status", "--json"]
        assert requests[2]["request"]["subtype"] == "initialize"


def raw_agy_cli(tmp_path, monkeypatch, initial, final):
    prompts = tmp_path / "prompts.jsonl"
    executable(
        tmp_path,
        monkeypatch,
        "agy",
        f"""
import pathlib, sys
if sys.argv[1:] == ['models']:
    print('chosen\\tChosen')
    sys.exit(0)
assert sys.argv[sys.argv.index('--model')+1] == 'chosen'
print({initial!r}, flush=True)
for line in sys.stdin:
    with pathlib.Path({str(prompts)!r}).open('a') as stream:
        stream.write(line)
    print({final!r}, flush=True)
    break
""",
    )
    return prompts


def agy_messages():
    initial = '{"event":"init","conversation_id":"session","init":{"model":"chosen"}}'
    final = (
        '{"event":"result","result":{"conversation_id":"session","status":"SUCCESS",'
        '"response":"RAPID_SHIP_AUTH_OK"}}'
    )
    return initial, final


@pytest.mark.parametrize(
    "fault", ["duplicate-model", "duplicate-session", "NaN", "Infinity", "-Infinity"]
)
def test_malformed_agy_initialization_sends_no_authentication_prompt(tmp_path, monkeypatch, fault):
    initial, final = agy_messages()
    if fault == "duplicate-model":
        initial = initial.replace('"model":"chosen"', '"model":"PRIVATE_PROTOCOL","model":"chosen"')
    elif fault == "duplicate-session":
        initial = initial.replace(
            '"conversation_id":"session"',
            '"conversation_id":"PRIVATE_PROTOCOL","conversation_id":"session"',
        )
    else:
        initial = initial[:-1] + ',"metadata":{"private":"PRIVATE_PROTOCOL","quota":' + fault + "}}"
    prompts = raw_agy_cli(tmp_path, monkeypatch, initial, final)

    result = providers().verify_provider("agy", "chosen")

    assert result["authenticated"] is None
    assert result["ready"] is False
    assert result["verified"] is False
    assert result["verified_at"] is None
    assert result["request_sent"] is False
    assert not prompts.exists()
    assert "PRIVATE_PROTOCOL" not in json.dumps(result)
    assert "no authentication prompt was sent" in result["hint"]


@pytest.mark.parametrize("fault", ["duplicate-session", "NaN", "Infinity", "-Infinity"])
def test_malformed_agy_result_cannot_issue_verification_evidence(tmp_path, monkeypatch, fault):
    initial, final = agy_messages()
    if fault == "duplicate-session":
        final = final.replace(
            '"conversation_id":"session"',
            '"conversation_id":"PRIVATE_PROTOCOL","conversation_id":"session"',
        )
    else:
        final = final[:-1] + ',"metadata":{"private":"PRIVATE_PROTOCOL","quota":' + fault + "}}"
    prompts = raw_agy_cli(tmp_path, monkeypatch, initial, final)

    result = providers().verify_provider("agy", "chosen")

    assert result["authenticated"] is None
    assert result["ready"] is False
    assert result["verified"] is False
    assert result["verified_at"] is None
    assert result["request_sent"] is True
    assert len(prompts.read_text().splitlines()) == 1
    assert "PRIVATE_PROTOCOL" not in json.dumps(result)
