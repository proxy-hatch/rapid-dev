"""Bounded, credential-free subprocess execution with process-group supervision."""

from __future__ import annotations

import math
import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import IO

MAX_OUTPUT_BYTES = 1024 * 1024
_TRUNCATED = b"\n[output truncated]\n"


@dataclass(frozen=True)
class ProcessResult:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False
    cancelled: bool = False


def safe_environment(env: dict[str, str] | None = None) -> dict[str, str]:
    """Inherit no caller environment; add only explicitly supplied values."""
    result = {
        "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }
    if env:
        result.update(env)
    return result


class _Capture:
    def __init__(self, stream: IO[bytes]) -> None:
        self.stream = stream
        self.data = bytearray()
        self.truncated = False

    def read(self) -> None:
        try:
            while chunk := self.stream.read(65536):
                remaining = MAX_OUTPUT_BYTES - len(self.data)
                self.data.extend(chunk[:remaining])
                self.truncated |= len(chunk) > remaining
        finally:
            self.stream.close()

    def text(self) -> str:
        data = bytes(self.data)
        if self.truncated:
            data = data[: MAX_OUTPUT_BYTES - len(_TRUNCATED)] + _TRUNCATED
        # Invalid UTF-8 is replaced with ASCII to keep the byte bound as well.
        return data.decode("utf-8", errors="replace").replace("\ufffd", "?")


def _kill_group(pid: int, sig: int) -> None:
    try:
        os.killpg(pid, sig)
    except ProcessLookupError:
        pass


def run_process(
    argv: list[str],
    cwd: Path,
    timeout_seconds: float,
    env: dict[str, str] | None = None,
    input_text: str | None = None,
    cancel_event: threading.Event | None = None,
) -> ProcessResult:
    """Run argv without a shell. Supervise the entire POSIX process group.

    Retention is capped separately for stdout/stderr; readers keep draining after
    the cap. Native execution is a project-authorized trust boundary, not a
    filesystem sandbox. Callers must explicitly pass any needed environment.
    """
    if not argv or any(not isinstance(a, str) or "\0" in a for a in argv):
        raise ValueError("argv must contain non-NUL strings and a command")
    if not argv[0] or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("command and positive finite timeout_seconds required")
    if os.name != "posix":
        raise RuntimeError("process-group supervision requires POSIX")
    start = time.monotonic()
    if cancel_event is not None and cancel_event.is_set():
        return ProcessResult(list(argv), -signal.SIGTERM, "", "", 0.0, cancelled=True)
    proc = subprocess.Popen(
        argv,
        cwd=cwd,
        env=safe_environment(env),
        start_new_session=True,
        stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.stdout is not None and proc.stderr is not None
    captures = [_Capture(proc.stdout), _Capture(proc.stderr)]
    readers = [threading.Thread(target=c.read, daemon=True) for c in captures]
    for reader in readers:
        reader.start()
    writer: threading.Thread | None = None
    if input_text is not None:
        assert proc.stdin is not None
        stdin = proc.stdin
        content = input_text.encode("utf-8")

        def write_input() -> None:
            try:
                stdin.write(content)
                stdin.flush()
            except (BrokenPipeError, OSError):
                pass
            finally:
                stdin.close()

        writer = threading.Thread(target=write_input, daemon=True)
        writer.start()
    timed_out = cancelled = False
    try:
        while proc.poll() is None:
            cancelled = cancel_event is not None and cancel_event.is_set()
            timed_out = not cancelled and time.monotonic() - start >= timeout_seconds
            if cancelled or timed_out:
                break
            time.sleep(0.01)
    finally:
        # Even when the leader has exited, descendants can still hold pipes or
        # ignore TERM. Always signal the group, then KILL it after a grace period.
        _kill_group(proc.pid, signal.SIGTERM)
        if timed_out or cancelled:
            time.sleep(0.15)
        proc.poll()  # Reap an exited leader before signaling remaining descendants.
        _kill_group(proc.pid, signal.SIGKILL)
        proc.wait()
        if writer:
            writer.join(timeout=1)
        for reader in readers:
            reader.join(timeout=1)
    return ProcessResult(
        list(argv),
        proc.returncode,
        captures[0].text(),
        captures[1].text(),
        time.monotonic() - start,
        timed_out,
        cancelled,
    )
