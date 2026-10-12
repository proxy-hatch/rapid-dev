"""Native CLI discovery, with inference reserved for an explicit selected-model check."""

from __future__ import annotations

import json
import os
import selectors
import shutil
import signal
import subprocess
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from agentic_engineering.process import ProcessResult, _kill_group, run_process
from agentic_engineering.project.provider_evidence import (
    ProviderModel,
    ProviderName,
    ProviderObservation,
)

PROBE_TIMEOUT_SECONDS = 15.0
AUTH_TIMEOUT_SECONDS = 30.0
_MAX_PROTOCOL_BYTES = 1024 * 1024
_DOCS = {
    "codex": "https://learn.chatgpt.com/docs/app-server",
    "claude": "https://code.claude.com/docs/en/cli-reference",
    "agy": "https://www.antigravity.google/docs/cli/headless/",
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _environment() -> dict[str, str]:
    # These are trusted installed CLIs using their own existing login state.
    # Probes run outside the project, without loading its scripts or settings.
    return {
        **os.environ,
        "DISABLE_AUTOUPDATER": "1",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    }


def _command(
    argv: list[str], cwd: Path, *, input_text: str | None = None, timeout: float | None = None
) -> ProcessResult:
    result = run_process(
        argv, cwd, timeout or PROBE_TIMEOUT_SECONDS, env=_environment(), input_text=input_text
    )
    if result.timed_out:
        raise TimeoutError
    return result


class _Protocol:
    def __init__(self, process: subprocess.Popen[bytes]) -> None:
        self.process = process
        self.deadline = time.monotonic() + PROBE_TIMEOUT_SECONDS
        self.pending = b""
        self.received = 0
        self.sequence = 0
        self.selector = selectors.DefaultSelector()
        assert process.stdout is not None
        self.selector.register(process.stdout, selectors.EVENT_READ)

    def send(self, value: dict[str, Any]) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write((json.dumps(value) + "\n").encode())
        self.process.stdin.flush()

    def read(self) -> dict[str, Any]:
        assert self.process.stdout is not None
        while b"\n" not in self.pending:
            remaining = self.deadline - time.monotonic()
            if remaining <= 0 or not self.selector.select(remaining):
                raise TimeoutError
            chunk = os.read(self.process.stdout.fileno(), 65536)
            if not chunk:
                if self.pending:
                    raise ValueError("CLI closed an incomplete protocol message")
                raise EOFError("CLI closed its protocol")
            self.received += len(chunk)
            if self.received > _MAX_PROTOCOL_BYTES:
                raise ValueError("CLI discovery response exceeded its limit")
            self.pending += chunk
        line, self.pending = self.pending.split(b"\n", 1)
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError("CLI discovery response must be an object")
        return value

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self.sequence += 1
        self.send({"id": self.sequence, "method": method, "params": params})
        while True:
            value = self.read()
            if value.get("id") == self.sequence:
                if "error" in value or not isinstance(value.get("result"), dict):
                    raise ValueError("CLI rejected discovery request")
                return dict(value["result"])


@contextmanager
def _session(argv: list[str], cwd: Path) -> Iterator[_Protocol]:
    process = subprocess.Popen(
        argv,
        cwd=cwd,
        env=_environment(),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    protocol = _Protocol(process)
    try:
        yield protocol
    finally:
        protocol.selector.close()
        _kill_group(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=0.2)
        except subprocess.TimeoutExpired:
            pass
        _kill_group(process.pid, signal.SIGKILL)
        process.wait()
        for stream in (process.stdin, process.stdout):
            if stream is not None:
                stream.close()


def _models(rows: Any, id_key: str, label_key: str) -> list[ProviderModel]:
    if not isinstance(rows, list):
        raise ValueError("Missing model catalog")
    models: list[ProviderModel] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid model entry")
        identifier, label = row.get(id_key), row.get(label_key)
        if (
            not isinstance(identifier, str)
            or not identifier
            or identifier.startswith("-")
            or not identifier.isprintable()
            or any(c.isspace() for c in identifier)
            or not isinstance(label, str)
            or not label.strip()
            or not label.isprintable()
            or identifier in seen
        ):
            raise ValueError("Invalid model entry")
        if row.get("hidden") is not True:
            models.append(ProviderModel(id=identifier, label=label))
        seen.add(identifier)
    return models


def _codex(executable: str, cwd: Path, result: ProviderObservation) -> None:
    result.sources.append("codex app-server: account/read, model/list")
    with _session([executable, "app-server", "--listen", "stdio://"], cwd) as protocol:
        protocol.request(
            "initialize",
            {
                "clientInfo": {"name": "rapid_ship_provider_check", "version": "0.1.0"},
                "capabilities": {},
            },
        )
        protocol.send({"method": "initialized", "params": {}})
        status = protocol.request("account/read", {"refreshToken": False})
        account = status.get("account")
        account_type = account.get("type") if isinstance(account, dict) else None
        if isinstance(account_type, str) and account_type in {"chatgpt", "apiKey"}:
            result.authenticated = True
        elif account is None and status.get("requiresOpenaiAuth") is True:
            result.authenticated = False
        rows: list[Any] = []
        cursor: str | None = None
        cursors: set[str] = set()
        for _ in range(20):
            params: dict[str, Any] = {"limit": 100, "includeHidden": False}
            if cursor is not None:
                params["cursor"] = cursor
            page = protocol.request("model/list", params)
            if not isinstance(page.get("data"), list):
                raise ValueError("Invalid model page")
            rows.extend(page["data"])
            cursor = page.get("nextCursor")
            if cursor is None:
                result.models = _models(rows, "model", "displayName")
                return
            if not isinstance(cursor, str) or not cursor or cursor in cursors:
                raise ValueError("Invalid model pagination")
            cursors.add(cursor)
        raise ValueError("Model catalog exceeded its page limit")


def _claude(executable: str, cwd: Path, result: ProviderObservation) -> None:
    result.sources.append("claude auth status --json; SDK initialize models")
    status = _command([executable, "auth", "status", "--json"], cwd)
    value = json.loads(status.stdout)
    if not isinstance(value, dict) or type(value.get("loggedIn")) is not bool:
        raise ValueError("Invalid authentication status")
    authenticated = value["loggedIn"]
    if status.returncode != (0 if authenticated else 1):
        raise ValueError("Conflicting authentication status")
    result.authenticated = authenticated
    if not authenticated:
        return
    argv = [
        executable,
        "--print",
        "--input-format",
        "stream-json",
        "--output-format",
        "stream-json",
        "--verbose",
        "--no-session-persistence",
        "--setting-sources",
        "user",
        "--settings",
        '{"disableAllHooks":true}',
        "--strict-mcp-config",
        "--mcp-config",
        '{"mcpServers":{}}',
        "--tools",
        "",
    ]
    with _session(argv, cwd) as protocol:
        protocol.send(
            {
                "type": "control_request",
                "request_id": "rapid-ship-discovery",
                "request": {"subtype": "initialize", "hooks": {}},
            }
        )
        while True:
            response = protocol.read()
            if response.get("type") != "control_response":
                continue
            body = response.get("response")
            if not isinstance(body, dict) or body.get("request_id") != "rapid-ship-discovery":
                raise ValueError("Invalid initialization response")
            if body.get("subtype") != "success" or not isinstance(body.get("response"), dict):
                raise ValueError("Initialization failed")
            result.models = _models(body["response"].get("models"), "value", "displayName")
            return


def _inspect_provider(name: str) -> ProviderObservation:
    """Read native status and catalog; do not log in, change accounts, or send a prompt.

    Authentication means the CLI reports a configured login, not that a cached
    token or every listed model has been accepted by the upstream service.
    """
    if name not in _DOCS:
        raise ValueError("Unsupported provider; choose codex, claude, or agy")
    executable = shutil.which(name)
    result = ProviderObservation(
        provider=cast(ProviderName, name),
        installed=executable is not None,
        authenticated=None,
        models=[],
        checked_at=_now(),
        sources=[_DOCS[name]],
        hint="",
        ready=False,
    )
    if executable is None:
        result.hint = f"Install {name}, then run the provider check again."
        return result
    try:
        with tempfile.TemporaryDirectory(prefix="rapid-ship-provider-") as temporary:
            cwd = Path(temporary)
            if name == "codex":
                _codex(executable, cwd, result)
            elif name == "claude":
                _claude(executable, cwd, result)
            else:
                result.sources.append("agy models")
                output = _command([executable, "models"], cwd)
                if output.returncode != 0:
                    raise ValueError("Model discovery failed")
                rows = []
                for line in output.stdout.splitlines():
                    identifier, separator, label = line.partition("\t")
                    if not separator:
                        raise ValueError("Unsupported model catalog format")
                    rows.append({"id": identifier, "label": label})
                result.models = _models(rows, "id", "label")
    except TimeoutError:
        result.hint = f"{name} discovery timed out. Check the CLI connection and retry."
        return result
    except (OSError, ValueError, EOFError):
        # CLI diagnostics can contain identities or credentials; never echo them.
        result.hint = f"Could not read {name} status/catalog. Check its CLI and retry."
        return result
    result.ready = result.observed_ready
    if result.authenticated is False:
        login = "claude auth login" if name == "claude" else "codex login"
        result.hint = f"Sign in with `{login}`, then run the provider check again."
    elif result.authenticated is None:
        result.hint = (
            "The CLI has no verified read-only auth status for this configuration. "
            "Select a listed model, then explicitly verify it."
        )
    elif not result.models:
        result.hint = "No models were returned. Check the CLI model picker and retry."
    else:
        result.hint = (
            "CLI sign-in and model catalog found. Catalogs may be cached; "
            "model entitlement and execution environments are untested."
        )
    return result


def inspect_provider(name: str) -> dict[str, Any]:
    """Read native status/catalog without signing in or sending an inference request."""
    return _inspect_provider(name).report()


def verify_provider(name: str, model: str) -> dict[str, Any]:
    """Explicitly check a selected model; only agy needs a tiny inference request."""
    result = _inspect_provider(name)
    result.selected_model = model
    result.verified = False
    result.verified_at = None
    result.verification_method = "inference" if name == "agy" else "native-status"
    result.request_sent = False
    result.tool_activity = None
    result.tool_event_count = None
    if model not in {entry.id for entry in result.models}:
        result.ready = False
        result.hint = "Choose an exact model ID from the current catalog."
        return result.report()
    if name != "agy":
        result.verified = result.ready
        result.verified_at = _now() if result.verified else None
        return result.report()
    result.ready = False
    result.sources.append("agy stream-json: explicit selected-model authentication request")
    executable = shutil.which("agy")
    if executable is None:
        result.hint = "agy is no longer installed; run discovery again."
        return result.report()
    try:
        with tempfile.TemporaryDirectory(prefix="rapid-ship-auth-") as temporary:
            cwd = Path(temporary)
            argv = [
                executable,
                "--input-format",
                "stream-json",
                "--output-format",
                "stream-json",
                "--model",
                model,
                "--mode",
                "plan",
                "--disable-slash-commands",
                "--print-timeout",
                f"{AUTH_TIMEOUT_SECONDS:g}s",
            ]
            with _session(argv, cwd) as protocol:
                protocol.deadline = time.monotonic() + AUTH_TIMEOUT_SECONDS
                first = protocol.read()
                initial = first.get("init")
                if (
                    first.get("event") != "init"
                    or not isinstance(initial, dict)
                    or initial.get("model") != model
                    or not isinstance(first.get("conversation_id"), str)
                    or not first["conversation_id"]
                ):
                    raise ValueError("CLI did not confirm the selected model and session")
                result.request_sent = True
                result.tool_event_count = 0
                protocol.send(
                    {
                        "event": "user",
                        "message": {
                            "content": "Hi. Reply with exactly RAPID_SHIP_AUTH_OK. "
                            "Do not use tools or access files."
                        },
                    }
                )
                assert protocol.process.stdin is not None
                protocol.process.stdin.close()
                completed = False
                while True:
                    try:
                        event = protocol.read()
                    except EOFError:
                        break
                    kind = event.get("event")
                    payload = event.get(kind) if isinstance(kind, str) else None
                    if (
                        completed
                        or kind not in ("step_update", "result")
                        or not isinstance(payload, dict)
                        or payload.get("conversation_id") != first["conversation_id"]
                    ):
                        raise ValueError("Invalid authentication response")
                    if kind == "step_update":
                        step = payload.get("step_type")
                        if step not in ("user_input", "agent_response", "tool", "checkpoint"):
                            raise ValueError("Unknown authentication activity")
                        if step == "tool":
                            result.tool_activity = True
                            assert result.tool_event_count is not None
                            result.tool_event_count += 1
                        continue
                    if (
                        payload.get("status") != "SUCCESS"
                        or not isinstance(payload.get("response"), str)
                        or payload["response"].strip() != "RAPID_SHIP_AUTH_OK"
                        or payload.get("model", model) != model
                        or payload.get("error")
                    ):
                        raise ValueError("Authentication request failed")
                    completed = True
                try:
                    code = protocol.process.wait(
                        timeout=max(0, protocol.deadline - time.monotonic())
                    )
                except subprocess.TimeoutExpired as error:
                    raise TimeoutError from error
                if code != 0 or not completed:
                    raise ValueError("Authentication request failed")
            if result.tool_activity is None:
                result.tool_activity = False
            result.authenticated = True
            result.verified = True
            result.verified_at = _now()
            result.ready = result.observed_ready
            tools = (
                "Tool activity was observed."
                if result.tool_activity
                else "No tool activity was observed."
            )
            result.hint = (
                f"The selected model answered the authentication request. {tools} "
                "This does not qualify a worker, reviewer, execution environment "
                "or unattended delivery."
            )
    except TimeoutError:
        result.hint = "agy authentication request timed out; no fallback was attempted."
    except (OSError, ValueError, EOFError):
        result.hint = (
            "agy did not confirm the selected model and session; no authentication prompt was sent."
            if not result.request_sent
            else "agy authentication request was not verified. Check agy login and retry."
        )
    return result.report()
