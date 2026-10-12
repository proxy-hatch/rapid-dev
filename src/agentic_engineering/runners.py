"""CLI argument and event adapters; all execution belongs to an environment provider.

The supported wire subset follows Codex JSONL, Claude Code stream-json and the
standalone Antigravity CLI stream-json. Unknown event kinds fail closed.
A completed run is a transport result, never approval or verified evidence.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from decimal import Decimal
from threading import Event
from typing import Any, Literal, Protocol
from uuid import UUID

Role = Literal["worker", "reviewer"]


class ProcessOutput(Protocol):
    """Structural boundary matching the process supervisor's result."""

    @property
    def returncode(self) -> int: ...

    @property
    def stdout(self) -> str: ...

    @property
    def stderr(self) -> str: ...

    @property
    def timed_out(self) -> bool: ...

    @property
    def cancelled(self) -> bool: ...


class Executor(Protocol):
    """An environment-bound execute method, never an automatic host fallback."""

    def __call__(
        self,
        argv: list[str],
        timeout_seconds: float,
        input_text: str | None = None,
        cancel_event: Event | None = None,
    ) -> ProcessOutput: ...


@dataclass(frozen=True)
class RunnerResult:
    text: str
    session_id: str
    events: tuple[dict[str, Any], ...]


class RunnerError(RuntimeError):
    """Blocked/failed runner output, retaining raw artifacts for the controller."""

    def __init__(self, message: str, process_result: ProcessOutput | None = None):
        super().__init__(message)
        self.process_result = process_result


def _session(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("session ID must be an explicit UUID")
    try:
        parsed = UUID(value)
    except ValueError as error:
        raise ValueError("session ID must be an explicit UUID") from error
    if str(parsed) != value:
        raise ValueError("session ID must be a canonical UUID")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ValueError(f"{label} must be nonempty text without NUL")
    return value


def _object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON field")
        value[key] = item
    return value


def _invalid_constant(value: str) -> Any:
    raise ValueError(f"invalid JSON constant: {value}")


def _events(output: str, *, kind_key: str = "type") -> tuple[dict[str, Any], ...]:
    events: list[dict[str, Any]] = []
    try:
        for line in output.splitlines():
            if not line.strip():
                continue
            event = json.loads(
                line, object_pairs_hook=_object_pairs, parse_constant=_invalid_constant
            )
            if not isinstance(event, dict) or not isinstance(event.get(kind_key), str):
                raise ValueError(f"event must be an object with a {kind_key}")
            events.append(event)
    except (ValueError, RecursionError) as error:
        raise RunnerError(f"malformed runner JSONL: {error}") from error
    if not events:
        raise RunnerError("incomplete runner output: no events")
    return tuple(events)


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or "\x00" in value:
        raise ValueError(f"{label} must be a string without NUL")
    return value


def _usage(value: object) -> None:
    if not isinstance(value, dict):
        raise ValueError("usage must be an object")
    for name in ("input_tokens", "cached_input_tokens", "output_tokens"):
        count = value.get(name)
        if type(count) is not int or count < 0:
            raise ValueError(f"usage {name} must be a nonnegative integer")
    if "reasoning_output_tokens" in value:
        count = value["reasoning_output_tokens"]
        if type(count) is not int or count < 0:
            raise ValueError("usage reasoning_output_tokens must be a nonnegative integer")


def _codex_payload(item: dict[str, Any], event_kind: str) -> None:
    kind = item["type"]
    if kind in {"agent_message", "reasoning"}:
        _text(item.get("text"), kind)
    elif kind == "command_execution":
        _text(item.get("command"), "command")
        _string(item.get("aggregated_output"), "command output")
        status = item.get("status")
        if status not in {"in_progress", "completed", "failed"}:
            raise ValueError("invalid command status")
        if event_kind == "item.completed" and status == "in_progress":
            raise ValueError("unfinished completed command")
        if event_kind != "item.completed" and status != "in_progress":
            raise ValueError("terminal command without completion event")
        if status == "completed" or "exit_code" in item:
            if type(item.get("exit_code")) is not int:
                raise ValueError("command exit code must be an integer")
    elif kind == "file_change":
        if event_kind != "item.completed" or item.get("status") not in {"completed", "failed"}:
            raise ValueError("invalid file change status")
        changes = item.get("changes")
        if not isinstance(changes, list):
            raise ValueError("file changes must be a list")
        for change in changes:
            if not isinstance(change, dict) or change.get("kind") not in {
                "add",
                "delete",
                "update",
            }:
                raise ValueError("invalid file change")
            _text(change.get("path"), "changed path")
    elif kind == "mcp_tool_call":
        _text(item.get("server"), "MCP server")
        _text(item.get("tool"), "MCP tool")
        if "arguments" not in item:
            raise ValueError("MCP arguments missing")
        status = item.get("status")
        if status not in {"in_progress", "completed", "failed"}:
            raise ValueError("invalid MCP status")
        if event_kind == "item.completed":
            if status == "completed":
                result = item.get("result")
                if not isinstance(result, dict) or not isinstance(result.get("content"), list):
                    raise ValueError("invalid MCP result")
                if "structured_content" not in result:
                    raise ValueError("MCP structured result missing")
                if any(
                    not isinstance(block, dict) or not isinstance(block.get("type"), str)
                    for block in result["content"]
                ):
                    raise ValueError("invalid MCP content")
            elif status == "failed":
                error = item.get("error")
                if not isinstance(error, dict):
                    raise ValueError("invalid MCP error")
                _text(error.get("message"), "MCP error message")
            else:
                raise ValueError("unfinished completed MCP call")
        elif status != "in_progress":
            raise ValueError("terminal MCP call without completion event")
    elif kind == "web_search":
        _text(item.get("query"), "search query")
    elif kind == "todo_list":
        items = item.get("items")
        if not isinstance(items, list):
            raise ValueError("todo items must be a list")
        for todo in items:
            if not isinstance(todo, dict) or type(todo.get("completed")) is not bool:
                raise ValueError("invalid todo item")
            _text(todo.get("text"), "todo text")
    elif kind == "error":
        raise ValueError("runner reported an error item")
    else:
        raise ValueError("unsupported item payload")


def _claude_content(block: object) -> None:
    if not isinstance(block, dict):
        raise ValueError("content block must be an object")
    kind = block.get("type")
    if kind == "text":
        _string(block.get("text"), "message text")
    elif kind == "thinking":
        _string(block.get("thinking"), "thinking text")
        _text(block.get("signature"), "thinking signature")
    elif kind == "redacted_thinking":
        _text(block.get("data"), "redacted thinking data")
    elif kind == "tool_use":
        _text(block.get("id"), "tool ID")
        _text(block.get("name"), "tool name")
        if not isinstance(block.get("input"), dict):
            raise ValueError("tool input must be an object")
    elif kind == "tool_result":
        _text(block.get("tool_use_id"), "tool result ID")
        if "is_error" in block and type(block["is_error"]) is not bool:
            raise ValueError("tool result error flag must be boolean")
        content = block.get("content")
        if isinstance(content, str):
            _string(content, "tool result text")
        elif isinstance(content, list):
            for child in content:
                if not isinstance(child, dict) or child.get("type") != "text":
                    raise ValueError("unsupported tool result content")
                _claude_content(child)
        else:
            raise ValueError("tool result content must be text or a content list")
    else:
        raise ValueError("unsupported message content")


@dataclass(frozen=True)
class RunnerAdapter:
    name: Literal["codex", "claude", "agy"]
    model: str | None = None

    def __post_init__(self) -> None:
        if self.name not in {"codex", "claude", "agy"}:
            raise ValueError("unsupported runner")
        if self.model is not None:
            model = _text(self.model, "model")
            if model.startswith("-") or any(character.isspace() for character in model):
                raise ValueError("model must be a token, not a command option")

    def build_argv(
        self, prompt: str, *, role: Role = "worker", session_id: str | None = None
    ) -> list[str]:
        """Use stdin for prompts and UUID-only resume, without escalation flags."""
        _text(prompt, "prompt")
        if role not in {"worker", "reviewer"}:
            raise ValueError("unsupported runner role")
        if session_id is not None:
            _session(session_id)
        if self.name == "codex":
            argv = [
                "codex",
                "exec",
                "--sandbox",
                "workspace-write" if role == "worker" else "read-only",
                "--config",
                'approval_policy="never"',
                "--ignore-user-config",
                "--ignore-rules",
                "--disable",
                "hooks",
            ]
            if session_id is not None:
                argv.append("resume")
            argv.append("--json")
            if self.model is not None:
                argv.extend(["--model", self.model])
            if session_id is not None:
                argv.append(session_id)
            argv.append("-")
        elif self.name == "claude":
            argv = [
                "claude",
                "--print",
                "--output-format",
                "stream-json",
                "--verbose",
                "--permission-mode",
                "dontAsk",
                "--setting-sources",
                "",
                "--settings",
                '{"disableAllHooks":true}',
                "--strict-mcp-config",
                "--mcp-config",
                '{"mcpServers":{}}',
            ]
            if role == "reviewer":
                # Review source and diff must be supplied by the controller in stdin.
                argv.extend(["--tools", ""])
            else:
                argv.extend(["--allowedTools", "Read,Edit,Write,Bash"])
            if self.model is not None:
                argv.extend(["--model", self.model])
            if session_id is not None:
                argv.extend(["--resume", session_id])
        else:
            # agy has no per-role tool switch. A reviewer is read-only by instruction only; the
            # controller blocks the task if Git shows a change in the reviewer's clone.
            argv = ["agy", "--input-format", "stream-json", "--output-format", "stream-json"]
            if self.model is not None:
                argv.extend(["--model", self.model])
            if session_id is not None:
                argv.extend(["--conversation", session_id])
        return argv

    def build_input(self, prompt: str) -> str:
        _text(prompt, "prompt")
        if self.name == "agy":
            return json.dumps({"event": "user", "message": {"content": prompt}}) + "\n"
        return prompt

    def validate_execution(self, role: Role, execution_provider: str | None) -> None:
        if self.name != "agy":
            return
        if execution_provider != "docker":
            raise RunnerError(
                f"agy {role}s require the Docker provider with an isolated HOME; "
                "native and other providers have not been verified"
            )
        if self.model is None:
            raise RunnerError("agy requires an explicit model identifier from agy models")

    def parse_output(
        self, output: str, *, expected_session_id: str | None = None, stderr: str = ""
    ) -> RunnerResult:
        # agy can exit zero with SUCCESS while soft-denying tools only on stderr.
        # Until it provides structured denials, diagnostics cannot count as success.
        if self.name == "agy" and stderr.strip():
            raise RunnerError("agy emitted diagnostics; inspect stderr for denied tools")
        events = _events(output, kind_key="event" if self.name == "agy" else "type")
        try:
            if expected_session_id is not None:
                _session(expected_session_id)
            if self.name == "codex":
                result = self._codex(events)
            elif self.name == "claude":
                result = self._claude(events)
            else:
                result = self._agy(events)
            if expected_session_id is not None and result.session_id != expected_session_id:
                raise ValueError("runner changed the requested session ID")
            return result
        except (ValueError, TypeError, KeyError, OverflowError) as error:
            raise RunnerError(f"invalid {self.name} output: {error}") from error

    def _codex(self, events: tuple[dict[str, Any], ...]) -> RunnerResult:
        session_id: str | None = None
        started = False
        completed = False
        messages: list[str] = []
        pending_items: set[str] = set()
        item_types: dict[str, str] = {}
        completed_items: set[str] = set()
        known_items = {
            "agent_message",
            "reasoning",
            "command_execution",
            "file_change",
            "mcp_tool_call",
            "web_search",
            "todo_list",
            "error",
        }
        for event in events:
            kind = event["type"]
            if completed:
                raise ValueError("event after completed turn")
            if kind == "thread.started":
                if session_id is not None or started:
                    raise ValueError("duplicate/out-of-order session start")
                session_id = _session(event.get("thread_id"))
            elif kind == "turn.started":
                if session_id is None or started:
                    raise ValueError("duplicate/out-of-order turn start")
                started = True
            elif kind in {"item.started", "item.updated", "item.completed"}:
                if not started:
                    raise ValueError("item outside a turn")
                item = event.get("item")
                if not isinstance(item, dict) or item.get("type") not in known_items:
                    raise ValueError("unknown or malformed item")
                item_id = _text(item.get("id"), "item ID")
                _codex_payload(item, kind)
                if item_id in completed_items:
                    raise ValueError("completed item ID reused")
                if item_id in item_types and item_types[item_id] != item["type"]:
                    raise ValueError("item type changed during its lifecycle")
                item_types[item_id] = item["type"]
                if kind == "item.started":
                    if item_id in pending_items:
                        raise ValueError("duplicate item start")
                    pending_items.add(item_id)
                elif kind == "item.updated":
                    if item_id not in pending_items:
                        raise ValueError("item update without matching start")
                elif kind == "item.completed":
                    pending_items.discard(item_id)
                    completed_items.add(item_id)
                if item["type"] == "agent_message":
                    text = _text(item.get("text"), "agent message")
                    if kind == "item.completed":
                        messages.append(text)
            elif kind == "turn.completed":
                if pending_items:
                    raise ValueError("unfinished items in completed turn")
                _usage(event.get("usage"))
                if not started or not messages:
                    raise ValueError("incomplete completed turn")
                completed = True
            elif kind in {"error", "turn.failed"}:
                raise ValueError("runner reported failure")
            else:
                raise ValueError(f"unknown event type: {kind}")
        if not completed or session_id is None:
            raise ValueError("incomplete runner output")
        return RunnerResult(messages[-1], session_id, events)

    def _claude(self, events: tuple[dict[str, Any], ...]) -> RunnerResult:
        session_id: str | None = None
        text: str | None = None
        pending_tools: set[str] = set()
        seen_tools: set[str] = set()
        for event in events:
            if text is not None:
                raise ValueError("event after completed result")
            kind = event["type"]
            if kind == "system" and event.get("subtype") == "init":
                if session_id is not None:
                    raise ValueError("duplicate session start")
                session_id = _session(event.get("session_id"))
                if event.get("plugin_errors") or event.get("mcp_server_errors"):
                    raise ValueError("runner initialization failed")
                continue
            if session_id is None:
                raise ValueError("event before session initialization")
            if _session(event.get("session_id")) != session_id:
                raise ValueError("mixed session IDs")
            if kind in {"assistant", "user"}:
                message = event.get("message")
                if not isinstance(message, dict) or not isinstance(message.get("content"), list):
                    raise ValueError("malformed message")
                if message.get("role") != kind:
                    raise ValueError("message role does not match event type")
                for block in message["content"]:
                    _claude_content(block)
                    if block["type"] == "tool_use":
                        if kind != "assistant" or block["id"] in seen_tools:
                            raise ValueError("invalid or reused tool use identity")
                        seen_tools.add(block["id"])
                        pending_tools.add(block["id"])
                    elif block["type"] == "tool_result":
                        if kind != "user" or block["tool_use_id"] not in pending_tools:
                            raise ValueError("tool result without matching unfinished use")
                        pending_tools.remove(block["tool_use_id"])
            elif kind == "system" and event.get("subtype") == "api_retry":
                continue
            elif kind == "result":
                if pending_tools:
                    raise ValueError("unfinished tool uses in completed result")
                if event.get("subtype") != "success" or event.get("is_error") is not False:
                    raise ValueError("runner reported failure")
                denials = event.get("permission_denials", [])
                if not isinstance(denials, list) or denials:
                    raise ValueError("runner reported denied permissions")
                text = _text(event.get("result"), "final result")
            else:
                raise ValueError(f"unknown event type/subtype: {kind}/{event.get('subtype')}")
        if session_id is None or text is None:
            raise ValueError("incomplete runner output")
        return RunnerResult(text, session_id, events)

    def _agy(self, events: tuple[dict[str, Any], ...]) -> RunnerResult:
        """Conservative subset of antigravity.google/docs/cli/headless/."""
        session: str | None = None
        text: str | None = None
        steps: dict[int, tuple[str, str]] = {}
        for event in events:
            if text is not None:
                raise ValueError("event after completed result")
            kind = event["event"]
            if kind not in {"init", "step_update", "result"}:
                raise ValueError("unknown agy event")
            payload = event.get(kind)
            if not isinstance(payload, dict):
                raise ValueError("missing agy event payload")
            if "error" in payload or payload.get("permission_denials", []) != []:
                raise ValueError("agy reported an error or denied permission")
            if kind == "init":
                if session is not None:
                    raise ValueError("duplicate session initialization")
                session = _session(event.get("conversation_id"))
                _text(payload.get("cwd"), "cwd")
                tool_names = payload.get("tools")
                if not isinstance(tool_names, list):
                    raise ValueError("init tools must be a list")
                for name in tool_names:
                    _text(name, "tool name")
                if payload.get("permission_mode") not in {
                    "request-review",
                    "proceed-in-sandbox",
                    "strict",
                }:
                    raise ValueError("unverified agy permission mode")
                if self.model is not None and payload.get("model") != self.model:
                    raise ValueError("agy did not use the pinned model")
                continue
            if session is None or _session(payload.get("conversation_id")) != session:
                raise ValueError("event outside the requested conversation")
            if "duration_seconds" in payload:
                duration = payload["duration_seconds"]
                if (
                    type(duration) not in {int, float}
                    or not math.isfinite(duration)
                    or duration < 0
                ):
                    raise ValueError("invalid agy duration")
            if "usage" in payload:
                usage = payload["usage"]
                if not isinstance(usage, dict):
                    raise ValueError("usage must be an object")
                for name in (
                    "input_tokens",
                    "output_tokens",
                    "thinking_tokens",
                    "cache_read_tokens",
                    "total_tokens",
                ):
                    if type(usage.get(name)) is not int or usage[name] < 0:
                        raise ValueError("invalid agy token count")
            if kind == "result":
                if any(state != "DONE" for _, state in steps.values()):
                    raise ValueError("unfinished agy steps")
                if payload.get("status") != "SUCCESS":
                    raise ValueError("agy did not complete successfully")
                if (
                    type(payload.get("num_turns")) is not int
                    or payload["num_turns"] < 1
                    or "usage" not in payload
                    or "duration_seconds" not in payload
                ):
                    raise ValueError("incomplete agy result")
                text = _text(payload.get("response"), "response")
                continue
            index = payload.get("step_index")
            state = payload.get("state")
            step_type = payload.get("step_type")
            if type(index) is not int or index < 0 or state not in {"ACTIVE", "DONE"}:
                raise ValueError("invalid agy step")
            if step_type not in {"user_input", "agent_response", "tool", "checkpoint"}:
                raise ValueError("unsupported agy step type")
            if index in steps and (steps[index][0] != step_type or steps[index][1] == "DONE"):
                raise ValueError("agy step identity changed or completed step reused")
            if "text_delta" in payload:
                _string(payload["text_delta"], "text delta")
            if "subagent_info" in payload:
                raise ValueError("agy subagent execution has not been verified")
            if step_type == "tool":
                name = _text(payload.get("tool_name"), "tool name")
                if name == "ask_permission":
                    raise ValueError("agy requested unapproved permission")
                info = payload.get("tool_info")
                if not isinstance(info, dict) or info.get("name") != name:
                    raise ValueError("missing or mismatched agy tool info")
                if "error" in info or not isinstance(info.get("parameters"), dict):
                    raise ValueError("invalid or failed agy tool")
                if state == "DONE":
                    _string(info.get("output"), "tool output")
            steps[index] = (step_type, state)
        if session is None or text is None:
            raise ValueError("incomplete agy output")
        return RunnerResult(text, session, events)

    def run(
        self,
        execute: Executor,
        prompt: str,
        *,
        role: Role = "worker",
        timeout_seconds: float,
        session_id: str | None = None,
        cancel_event: Event | None = None,
        execution_provider: str | None = None,
    ) -> RunnerResult:
        """Execute once through the provider; keep failure output for durable storage."""
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout must be positive and finite")
        argv = self.build_argv(prompt, role=role, session_id=session_id)
        self.validate_execution(role, execution_provider)
        if self.name == "agy":
            # Go duration flags do not accept exponent notation or values beyond int64 ns.
            duration = max(Decimal(str(timeout_seconds)), Decimal("0.000000001"))
            if duration > Decimal(2**63 - 1) / Decimal(1_000_000_000):
                raise ValueError("agy timeout exceeds its supported duration range")
            argv.extend(["--print-timeout", f"{duration:f}s"])
        try:
            result = execute(
                argv,
                timeout_seconds=timeout_seconds,
                input_text=self.build_input(prompt),
                cancel_event=cancel_event,
            )
        except (OSError, TimeoutError) as error:
            raise RunnerError(f"runner execution unavailable: {error}") from error
        if result.cancelled:
            raise RunnerError("runner execution cancelled", result)
        if result.timed_out:
            raise RunnerError("runner execution timed out", result)
        if result.returncode != 0:
            raise RunnerError(f"runner exited with code {result.returncode}", result)
        try:
            return self.parse_output(
                result.stdout, expected_session_id=session_id, stderr=result.stderr
            )
        except RunnerError as error:
            raise RunnerError(str(error), result) from error
