"""devctl's bounded process runner, against real child processes (offline).

One tool is simulated: a stand-in executable placed on PATH.
"""

import os
import signal
import sys
import time
from pathlib import Path

import pytest

import devctl.process as process
from devctl.process import MAX_OUTPUT_BYTES, run_process


def python(code: str) -> list[str]:
    return [sys.executable, "-c", code]


def test_real_process_stdin_stdout_stderr_and_no_secret_inheritance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "must-not-inherit")
    result = run_process(
        python(
            "import sys,os; print(sys.stdin.read()); print('err',file=sys.stderr); "
            "print(os.getenv('AWS_SECRET_ACCESS_KEY'))"
        ),
        tmp_path,
        3,
        input_text="hello",
    )
    assert result.returncode == 0
    assert result.stdout == "hello\nNone\n"
    assert result.stderr == "err\n"
    assert result.argv[0] == sys.executable
    assert result.duration_seconds >= 0
    assert not result.timed_out


def test_explicit_environment_and_output_are_bounded(tmp_path: Path) -> None:
    result = run_process(
        python(
            "import os,sys; print(os.environ['EXPLICIT']); sys.stdout.write('x'*3000000); "
            "sys.stderr.write('y'*3000000)"
        ),
        tmp_path,
        5,
        env={"EXPLICIT": "yes"},
    )
    assert result.returncode == 0
    assert result.stdout.startswith("yes\n")
    assert len(result.stdout.encode()) <= MAX_OUTPUT_BYTES
    assert len(result.stderr.encode()) <= MAX_OUTPUT_BYTES
    assert result.stdout_truncated


def is_running(pid: int) -> bool:
    # A zombie has terminated, though its parent has not reaped it yet.
    result = run_process(["ps", "-o", "stat=", "-p", str(pid)], Path.cwd(), 5)
    return result.returncode == 0 and not result.stdout.strip().startswith("Z")


def test_timeout_kills_grandchild_even_if_it_ignores_sigterm(tmp_path: Path) -> None:
    pid_file = tmp_path / "grandchild.pid"
    grandchild = (
        "import os,time,signal; signal.signal(signal.SIGTERM,signal.SIG_IGN); "
        f"open({str(pid_file)!r},'w').write(str(os.getpid())); time.sleep(60)"
    )
    code = (
        "import subprocess,sys,time; "
        f"subprocess.Popen([sys.executable,'-c',{grandchild!r}]); time.sleep(60)"
    )
    started = time.monotonic()
    result = run_process(python(code), tmp_path, 0.5)
    pid = int(pid_file.read_text())
    try:
        assert not is_running(pid)
        assert result.returncode != 0
        assert result.timed_out
        assert time.monotonic() - started < 3
    finally:
        if is_running(pid):
            os.kill(pid, signal.SIGKILL)


def test_large_stdin_cannot_deadlock_timeout(tmp_path: Path) -> None:
    result = run_process(
        python("import time; time.sleep(60)"), tmp_path, 0.1, input_text="x" * 3000000
    )
    assert result.timed_out


@pytest.mark.parametrize(("argv", "timeout"), [([], 1), (["echo"], 0), (["echo"], -1)])
def test_invalid_process_arguments_are_rejected(
    tmp_path: Path, argv: list[str], timeout: float
) -> None:
    with pytest.raises(ValueError, match=r"argv must contain|positive finite"):
        run_process(argv, tmp_path, timeout)


def test_successful_leader_exit_quiesces_background_descendant(tmp_path: Path) -> None:
    pid_file = tmp_path / "background.pid"
    child = f"import os,time; open({str(pid_file)!r},'w').write(str(os.getpid())); time.sleep(60)"
    leader = (
        "import subprocess,sys,time,pathlib; "
        f"subprocess.Popen([sys.executable,'-c',{child!r}]); "
        f"p=pathlib.Path({str(pid_file)!r}); "
        "\nwhile not p.exists(): time.sleep(.01)\n"
    )
    result = run_process(python(leader), tmp_path, 3)
    pid = int(pid_file.read_text())
    try:
        assert result.returncode == 0
        assert not result.timed_out
        assert not is_running(pid)
    finally:
        if is_running(pid):
            os.kill(pid, signal.SIGKILL)


def test_kill_denial_is_ignored_only_after_group_disappears(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from devctl.process import _kill_group

    calls: list[int] = []

    def teardown(pid: int, sig: int) -> None:
        calls.append(sig)
        if len(calls) <= 2:
            raise PermissionError("group is exiting")
        raise ProcessLookupError("group is gone")

    monkeypatch.setattr(os, "killpg", teardown)
    _kill_group(123, signal.SIGKILL)
    assert calls == [signal.SIGKILL, 0, 0]


@pytest.mark.parametrize("probe_denied", [False, True])
def test_kill_denial_for_existing_group_remains_an_error(
    monkeypatch: pytest.MonkeyPatch, probe_denied: bool
) -> None:
    elapsed = [0.0]
    calls: list[int] = []
    denial = PermissionError("real permission failure")

    def denied(pid: int, sig: int) -> None:
        calls.append(sig)
        if sig or probe_denied:
            raise denial

    monkeypatch.setattr(os, "killpg", denied)
    monkeypatch.setattr(time, "monotonic", lambda: elapsed[0])
    monkeypatch.setattr(time, "sleep", lambda seconds: elapsed.__setitem__(0, elapsed[0] + seconds))
    with pytest.raises(PermissionError) as caught:
        process._kill_group(123, signal.SIGKILL)
    assert caught.value is denial
    assert calls.count(signal.SIGKILL) == 1
    assert 0 in calls
    assert elapsed[0] <= 0.051


def test_tools_are_found_on_the_callers_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tools = tmp_path / "bin"
    tools.mkdir()
    tool = tools / "fake-tool"
    tool.write_text("#!/bin/sh\necho found\n")
    tool.chmod(0o700)
    monkeypatch.setenv("PATH", f"{tools}{os.pathsep}{os.environ['PATH']}")

    result = run_process(["fake-tool"], tmp_path, 5)

    assert result.returncode == 0
    assert result.stdout == "found\n"


def test_truncation_is_reported_beside_the_output_not_inside_it(tmp_path: Path) -> None:
    result = run_process(
        python(
            "import sys; sys.stdout.write('x' * 3000000); sys.stderr.write('[output truncated]')"
        ),
        tmp_path,
        10,
    )

    assert result.stdout_truncated
    assert result.stdout == "x" * MAX_OUTPUT_BYTES
    assert not result.stderr_truncated
    assert result.stderr == "[output truncated]"


def test_waiting_for_a_process_does_not_poll(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(time, "sleep", sleeps.append)

    result = run_process(python("import time; time.sleep(0.3)"), tmp_path, 5)

    assert result.returncode == 0
    assert sleeps == []


def test_timeout_kills_a_leader_that_ignores_sigterm(tmp_path: Path) -> None:
    started = time.monotonic()
    result = run_process(
        python("import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)"),
        tmp_path,
        0.3,
    )

    assert result.timed_out
    assert time.monotonic() - started < 3


def test_a_timed_out_group_is_sent_sigterm_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # macOS answers EPERM to SIGTERM for a group that holds only killed, unreaped
    # processes, so the timer's TERM and KILL must not be followed by another TERM.
    sent: list[int] = []
    real_killpg = os.killpg

    def record(pid: int, sig: int) -> None:
        sent.append(sig)
        real_killpg(pid, sig)

    monkeypatch.setattr(os, "killpg", record)

    result = run_process(python("import time; time.sleep(60)"), tmp_path, 0.2)

    assert result.timed_out
    assert sent[:2] == [signal.SIGTERM, signal.SIGKILL]
    assert sent.count(signal.SIGTERM) == 1


def test_a_refused_sigterm_still_ends_the_group_and_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A child under another user can refuse our SIGTERM. The timer must still escalate to
    # SIGKILL, so the call ends at the timeout plus the grace period instead of at the
    # child's own exit, and the refusal reaches the caller as it did before the timer.
    real_killpg = os.killpg

    def refuse_term(pid: int, sig: int) -> None:
        if sig == signal.SIGTERM:
            raise PermissionError("not permitted")
        real_killpg(pid, sig)

    monkeypatch.setattr(os, "killpg", refuse_term)

    started = time.monotonic()
    with pytest.raises(PermissionError, match="not permitted"):
        run_process(python("import time; time.sleep(4)"), tmp_path, 0.3)

    assert time.monotonic() - started < 2
