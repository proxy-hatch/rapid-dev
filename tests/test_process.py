import os
import signal
import sys
import threading
import time

import pytest

from agentic_engineering.process import MAX_OUTPUT_BYTES, run_process


def python(code):
    return [sys.executable, "-c", code]


def test_real_process_stdin_stdout_stderr_and_no_secret_inheritance(tmp_path, monkeypatch):
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


def test_explicit_environment_and_output_are_bounded(tmp_path):
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
    assert "truncated" in result.stdout


def is_running(pid):
    # A zombie has terminated, though its parent has not reaped it yet.
    import subprocess

    result = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True)
    return result.returncode == 0 and not result.stdout.strip().startswith("Z")


@pytest.mark.parametrize("cancel", [False, True])
def test_timeout_or_cancel_kills_grandchild_even_if_it_ignores_sigterm(tmp_path, cancel):
    pid_file = tmp_path / "grandchild.pid"
    grandchild = (
        "import os,time,signal; signal.signal(signal.SIGTERM,signal.SIG_IGN); "
        f"open({str(pid_file)!r},'w').write(str(os.getpid())); time.sleep(60)"
    )
    code = (
        "import subprocess,sys,time; "
        f"subprocess.Popen([sys.executable,'-c',{grandchild!r}]); time.sleep(60)"
    )
    event = threading.Event()
    timer = threading.Timer(0.5, event.set) if cancel else None
    if timer:
        timer.start()
    started = time.monotonic()
    result = run_process(python(code), tmp_path, 4 if cancel else 0.5, cancel_event=event)
    if timer:
        timer.join()
    pid = int(pid_file.read_text())
    try:
        assert not is_running(pid)
        assert result.returncode != 0
        assert result.timed_out is (not cancel)
        assert result.cancelled is cancel
        assert time.monotonic() - started < 3
    finally:
        if is_running(pid):
            os.kill(pid, signal.SIGKILL)


def test_large_stdin_cannot_deadlock_timeout(tmp_path):
    result = run_process(
        python("import time; time.sleep(60)"), tmp_path, 0.1, input_text="x" * 3000000
    )
    assert result.timed_out


def test_cancel_before_launch_does_not_execute(tmp_path):
    event = threading.Event()
    event.set()
    result = run_process(python("open('ran','w').write('yes')"), tmp_path, 2, cancel_event=event)
    assert result.cancelled
    assert not (tmp_path / "ran").exists()


@pytest.mark.parametrize("argv,timeout", [([], 1), (["echo"], 0), (["echo"], -1)])
def test_invalid_process_arguments_are_rejected(tmp_path, argv, timeout):
    with pytest.raises(ValueError):
        run_process(argv, tmp_path, timeout)


def test_successful_leader_exit_quiesces_background_descendant(tmp_path):
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


def test_kill_denial_is_ignored_only_after_group_disappears(monkeypatch):
    from agentic_engineering.process import _kill_group

    calls = []

    def teardown(pid, sig):
        calls.append(sig)
        if len(calls) <= 2:
            raise PermissionError("group is exiting")
        raise ProcessLookupError("group is gone")

    monkeypatch.setattr(os, "killpg", teardown)
    _kill_group(123, signal.SIGKILL)
    assert calls == [signal.SIGKILL, 0, 0]


@pytest.mark.parametrize("probe_denied", [False, True])
def test_kill_denial_for_existing_group_remains_an_error(monkeypatch, probe_denied):
    import agentic_engineering.process as process

    elapsed = [0.0]
    calls = []
    denial = PermissionError("real permission failure")

    def denied(pid, sig):
        calls.append(sig)
        if sig or probe_denied:
            raise denial

    monkeypatch.setattr(os, "killpg", denied)
    monkeypatch.setattr(process.time, "monotonic", lambda: elapsed[0])
    monkeypatch.setattr(
        process.time, "sleep", lambda seconds: elapsed.__setitem__(0, elapsed[0] + seconds)
    )
    with pytest.raises(PermissionError) as caught:
        process._kill_group(123, signal.SIGKILL)
    assert caught.value is denial
    assert calls.count(signal.SIGKILL) == 1
    assert 0 in calls
    assert elapsed[0] <= 0.051
