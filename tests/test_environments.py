"""Real Git/native tests; injected Docker lifecycle tests are NOT live trials."""

import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from agentic_engineering.environments import (
    EnvironmentBlocked,
    EnvironmentManager,
    resolve_environment,
)
from agentic_engineering.models import EnvironmentSpec, ProjectConfig, Resources, TaskSpec
from agentic_engineering.process import ProcessResult


def git(path, *argv):
    return subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "-C", str(path), *argv],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def repository(tmp_path):
    repo = tmp_path / "source"
    repo.mkdir()
    git(repo, "init")
    git(repo, "config", "user.email", "fixture@example.invalid")
    git(repo, "config", "user.name", "Fixture")
    (repo / "tracked.txt").write_text("committed")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "fixture")
    return repo, git(repo, "rev-parse", "HEAD")


def native(**changes):
    return EnvironmentSpec(
        name="native",
        execution="native",
        workspace="clone",
        allow_native=True,
        private_network=False,
        **changes,
    )


def test_native_grant_and_private_network_blockers(tmp_path):
    manager = EnvironmentManager(tmp_path / "managed")
    spec = EnvironmentSpec(name="native", execution="native", workspace="clone")
    assert "allow_native" in " ".join(manager.inspect(spec))
    assert "private_network" in " ".join(manager.inspect(spec))
    assert not manager.inspect(native())
    assert not (tmp_path / "managed").exists()


def test_clone_is_independent_preserves_dirty_source_and_cleans_only_owned_path(
    tmp_path, repository
):
    repo, sha = repository
    (repo / "tracked.txt").write_text("dirty")
    (repo / "untracked").write_text("keep")
    manager = EnvironmentManager(tmp_path / "managed")
    handle = manager.prepare(native(), repo, "task", sha)
    other = manager.prepare(native(), repo, "task", sha)
    assert handle.workspace != other.workspace
    assert (handle.workspace / "tracked.txt").read_text() == "committed"
    assert (repo / "tracked.txt").read_text() == "dirty"
    assert (repo / "untracked").read_text() == "keep"
    assert git(handle.workspace, "rev-parse", "--git-common-dir") == ".git"
    src_object = next((repo / ".git/objects").glob("*/*"))
    clone_object = handle.workspace / ".git/objects" / src_object.relative_to(repo / ".git/objects")
    if clone_object.exists():
        assert src_object.stat().st_ino != clone_object.stat().st_ino
    result = manager.execute(
        handle,
        [
            sys.executable,
            "-c",
            "import os; print(os.getenv('HOME')); print(os.getenv('AWS_SECRET_ACCESS_KEY'))",
        ],
        3,
    )
    assert result.returncode == 0
    assert result.stdout.splitlines()[0].startswith(str(handle.workspace.parent))
    assert result.stdout.splitlines()[1] == "None"
    manager.cleanup(handle)
    assert not handle.workspace.parent.exists()
    assert other.workspace.exists()
    assert repo.exists()
    manager.cleanup(other)


def test_worktree_unique_branches_and_dirty_parent_survives(tmp_path, repository):
    repo, sha = repository
    (repo / "tracked.txt").write_text("dirty")
    manager = EnvironmentManager(tmp_path / "managed")
    spec = native().model_copy(update={"workspace": "worktree"})
    a = manager.prepare(spec, repo, "a", sha)
    b = manager.prepare(spec, repo, "b", sha)
    assert git(a.workspace, "branch", "--show-current") != git(
        b.workspace, "branch", "--show-current"
    )
    assert (a.workspace / "tracked.txt").read_text() == "committed"
    manager.cleanup(a)
    assert b.workspace.exists()
    assert (repo / "tracked.txt").read_text() == "dirty"
    manager.cleanup(b)


@pytest.mark.parametrize("task_id", ["../outside", "/absolute", "..", "a/b"])
def test_path_escape_rejected_without_writes(tmp_path, repository, task_id):
    repo, sha = repository
    manager = EnvironmentManager(tmp_path / "managed")
    with pytest.raises(ValueError):
        manager.prepare(native(), repo, task_id, sha)
    assert not (tmp_path / "managed").exists()


def test_forged_handle_or_marker_cannot_delete_source(tmp_path, repository):
    repo, sha = repository
    manager = EnvironmentManager(tmp_path / "managed")
    handle = manager.prepare(native(), repo, "task", sha)
    with pytest.raises(ValueError):
        manager.cleanup(replace(handle, workspace=repo))
    marker = handle.workspace.parent / "owner.json"
    original = marker.read_text()
    marker.write_text("{}")
    with pytest.raises(ValueError):
        manager.cleanup(handle)
    assert repo.exists()
    marker.write_text(original)
    manager.cleanup(handle)


def test_workspace_symlink_cannot_delete_user_path(tmp_path, repository):
    repo, sha = repository
    manager = EnvironmentManager(tmp_path / "managed")
    handle = manager.prepare(native(), repo, "task", sha)
    moved = handle.workspace.with_name("old")
    handle.workspace.rename(moved)
    handle.workspace.symlink_to(repo, target_is_directory=True)
    with pytest.raises(ValueError):
        manager.cleanup(handle)
    assert (repo / "tracked.txt").exists()
    handle.workspace.unlink()
    moved.rename(handle.workspace)
    manager.cleanup(handle)


class LocalResource:
    required_leases = ["host-port:5432", "installation:postgres"]

    def __init__(self):
        self.prepared = []
        self.cleaned = []

    def inspect(self, spec):
        return []

    def prepare(self, handle):
        self.prepared.append(handle.id)
        return {"fixture": "offline-not-live"}

    def cleanup(self, handle, metadata):
        self.cleaned.append((handle.id, metadata))


def test_unknown_cloud_resource_blocks_and_shared_installation_requires_leases(
    tmp_path, repository
):
    repo, sha = repository
    manager = EnvironmentManager(tmp_path / "managed")
    spec = native(test_resources=["aws:test-account"])
    assert "unregistered" in " ".join(manager.inspect(spec))
    with pytest.raises(EnvironmentBlocked):
        manager.prepare(spec, repo, "cloud", sha)
    adapter = LocalResource()
    manager.register_resource("local-postgres", adapter)
    spec = native(test_resources=["local-postgres"])
    assert "host-port:5432" in " ".join(manager.inspect(spec))
    spec = spec.model_copy(update={"exclusive_resources": adapter.required_leases})
    handle = manager.prepare(spec, repo, "local", sha)
    manager.cleanup(handle)
    assert adapter.prepared == [handle.id]
    assert adapter.cleaned == [(handle.id, {"fixture": "offline-not-live"})]


class SimulatedDockerTransport:
    """Offline command recorder: does not certify Docker compatibility."""

    def __init__(self):
        self.calls = []
        self.owner = ""
        self.execution_result = None

    def __call__(self, argv, cwd, timeout_seconds, env=None, input_text=None, cancel_event=None):
        self.calls.append(argv)
        stdout = ""
        if argv[:2] == ["docker", "create"]:
            self.owner = argv[argv.index("--label") + 1].split("=", 1)[1]
            stdout = "fixture-container\n"
        elif argv[:2] == ["docker", "inspect"]:
            stdout = self.owner + "\n"
        elif argv[:2] == ["docker", "exec"] and self.execution_result:
            return self.execution_result
        return ProcessResult(argv, 0, stdout, "", 0.01)


def test_docker_simulated_lifecycle_uses_configured_budgets_and_private_mount(tmp_path, repository):
    repo, sha = repository
    transport = SimulatedDockerTransport()
    manager = EnvironmentManager(
        tmp_path / "managed", transport=transport, executable_lookup=lambda _: "/fixture/docker"
    )
    spec = EnvironmentSpec(
        name="docker",
        execution="docker",
        workspace="clone",
        image="python:3.13",
        resources=Resources(memory_mb=7168, cpu=2.5),
    )
    handle = manager.prepare(spec, repo, "docker", sha)
    result = manager.execute(handle, ["python", "-V"], 3)
    assert result.returncode == 0
    manager.cleanup(handle)
    create = next(c for c in transport.calls if c[:2] == ["docker", "create"])
    assert create[create.index("--memory") + 1] == "7168m"
    assert create[create.index("--cpus") + 1] == "2.5"
    assert create[create.index("--network") + 1] == "none"
    assert create[create.index("--mount") + 1] == f"type=bind,src={handle.workspace},dst=/workspace"
    assert "--privileged" not in create
    assert "/var/run/docker.sock" not in " ".join(create)
    assert str(Path.home()) not in " ".join(create)
    assert any(c[:2] == ["docker", "start"] for c in transport.calls)
    assert any(c[:2] == ["docker", "exec"] for c in transport.calls)
    assert any(c[:2] == ["docker", "rm"] for c in transport.calls)


def test_docker_timeout_stops_container_descendants_simulated(tmp_path, repository):
    repo, sha = repository
    transport = SimulatedDockerTransport()
    manager = EnvironmentManager(
        tmp_path / "managed", transport=transport, executable_lookup=lambda _: "/fixture/docker"
    )
    spec = EnvironmentSpec(
        name="docker", execution="docker", workspace="clone", image="python:3.13"
    )
    handle = manager.prepare(spec, repo, "docker", sha)
    transport.execution_result = ProcessResult(["fixture"], -9, "", "", 0.1, timed_out=True)
    assert manager.execute(handle, ["sleep", "60"], 0.1).timed_out
    assert ["docker", "kill", "fixture-container"] in transport.calls
    with pytest.raises(EnvironmentBlocked):
        manager.execute(handle, ["true"], 3)
    manager.cleanup(handle)


def test_docker_missing_image_daemon_and_unverified_adapters_block(tmp_path):
    manager = EnvironmentManager(tmp_path, executable_lookup=lambda _: None)
    spec = EnvironmentSpec(name="docker", execution="docker", workspace="clone")
    assert "image" in " ".join(manager.inspect(spec))
    assert "unavailable" in " ".join(manager.inspect(spec))
    for provider in ["sbx", "openhands"]:
        spec = EnvironmentSpec(name=provider, execution=provider, workspace="clone")
        assert manager.inspect(spec)


def test_resolver_rejects_missing_name_and_budget_overrun():
    spec = native(resources=Resources(memory_mb=2048, cpu=2.0))
    config = ProjectConfig(
        name="fixture", design_path="design.md", environments=[spec], cpu_budget=1.0
    )
    task = TaskSpec(
        id="t",
        title="t",
        description="t",
        owned_paths=["src"],
        acceptance=["works"],
        environment="native",
        base_sha="a" * 40,
    )
    with pytest.raises(EnvironmentBlocked, match="cpu"):
        resolve_environment(config, task)
    config = config.model_copy(update={"cpu_budget": 3.0})
    assert resolve_environment(config, task) == spec
    with pytest.raises(EnvironmentBlocked, match="missing"):
        resolve_environment(config, task.model_copy(update={"environment": "missing"}))


class SimulatedSandboxTransport:
    """Offline sbx transport; no live compatibility claim."""

    def __init__(self, forwarding="false"):
        self.forwarding = forwarding
        self.calls = []

    def __call__(self, argv, cwd, timeout_seconds, env=None, input_text=None, cancel_event=None):
        self.calls.append(argv)
        stdout = self.forwarding if argv[:3] == ["sbx", "settings", "get"] else ""
        return ProcessResult(argv, 0, stdout, "", 0.01)


def test_sandbox_simulated_lifecycle_probes_ssh_and_uses_pinned_template(tmp_path, repository):
    repo, sha = repository
    transport = SimulatedSandboxTransport()
    manager = EnvironmentManager(
        tmp_path / "managed",
        transport=transport,
        executable_lookup=lambda _: "/fixture/sbx",
        sandbox_configuration={
            "compatibility_verified": True,
            "github_credentials_absent": True,
            "private_network": True,
        },
    )
    spec = EnvironmentSpec(
        name="sbx", execution="sbx", workspace="clone", image="pinned-image@sha256:abc"
    )
    handle = manager.prepare(spec, repo, "sandbox", sha)
    assert manager.execute(handle, ["python", "-V"], 3).returncode == 0
    manager.cleanup(handle)
    assert ["sbx", "settings", "get", "ssh.agentForwardingEnabled"] in transport.calls
    create = next(c for c in transport.calls if c[:2] == ["sbx", "create"])
    assert create[create.index("--template") + 1] == spec.image
    assert create[-2:] == ["shell", str(handle.workspace)]
    assert [
        "sbx",
        "exec",
        "-i",
        "-w",
        str(handle.workspace),
        f"devctl-{handle.id}",
        "python",
        "-V",
    ] in transport.calls
    assert ["sbx", "rm", "--force", f"devctl-{handle.id}"] in transport.calls


def test_sandbox_enabled_ssh_forwarding_blocks_even_when_config_says_disabled(tmp_path):
    transport = SimulatedSandboxTransport(forwarding="true")
    manager = EnvironmentManager(
        tmp_path,
        transport=transport,
        executable_lookup=lambda _: "/fixture/sbx",
        sandbox_configuration={
            "compatibility_verified": True,
            "ssh_agent_forwarding": False,
            "github_credentials_absent": True,
            "private_network": True,
        },
    )
    spec = EnvironmentSpec(name="sbx", execution="sbx", workspace="clone")
    assert "forwarding" in " ".join(manager.inspect(spec))
    assert any(c[:3] == ["sbx", "settings", "get"] for c in transport.calls)


def test_worktree_preparation_does_not_execute_repository_smudge_filters(tmp_path, repository):
    repo, _ = repository
    sentinel = tmp_path / "filter-ran"
    (repo / ".gitattributes").write_text("tracked.txt filter=candidate\n")
    git(repo, "add", ".gitattributes")
    git(repo, "commit", "-m", "declare filter")
    sha = git(repo, "rev-parse", "HEAD")
    git(
        repo,
        "config",
        "filter.candidate.smudge",
        f"{sys.executable} -c \"open('{sentinel}','w').write('unsafe')\" ",
    )
    manager = EnvironmentManager(tmp_path / "managed")
    handle = manager.prepare(
        native().model_copy(update={"workspace": "worktree"}), repo, "filter", sha
    )
    try:
        assert not sentinel.exists()
        assert (handle.workspace / "tracked.txt").read_text() == "committed"
    finally:
        manager.cleanup(handle)


def test_uncertain_docker_creation_retains_ownership_until_reconciliation(tmp_path, repository):
    repo, sha = repository
    transport = SimulatedDockerTransport()
    original = transport.__call__

    def lost(argv, cwd, timeout_seconds, env=None, input_text=None, cancel_event=None):
        if argv[:2] in [["docker", "create"], ["docker", "inspect"]]:
            raise OSError("connection lost; remote effect unknown")
        return original(argv, cwd, timeout_seconds, env, input_text, cancel_event)

    manager = EnvironmentManager(
        tmp_path / "managed", transport=lost, executable_lookup=lambda _: "/fixture/docker"
    )
    spec = EnvironmentSpec(
        name="docker", execution="docker", workspace="clone", image="python:3.13"
    )
    with pytest.raises(OSError):
        manager.prepare(spec, repo, "uncertain", sha)
    owners = list((tmp_path / "managed").glob("*/owner.json"))
    assert len(owners) == 1
    import json

    record = json.loads(owners[0].read_text())
    assert record["metadata"]["container"] == f"devctl-{record['id']}"
    assert (owners[0].parent / "workspace").exists()


def test_explicit_recovery_validates_persisted_handle_before_cleanup(tmp_path, repository):
    repo, sha = repository
    first = EnvironmentManager(tmp_path / "managed")
    handle = first.prepare(native(), repo, "recovery", sha)
    restarted = EnvironmentManager(tmp_path / "managed")
    with pytest.raises(ValueError):
        restarted.recover(replace(handle, workspace=repo))
    restarted.recover(handle)
    restarted.cleanup(handle)
    assert not handle.workspace.exists()
    assert repo.exists()


def test_cleanup_retry_does_not_repeat_successful_resource_effect(tmp_path, repository):
    repo, sha = repository

    class FlakyResource(LocalResource):
        required_leases = []

        def cleanup(self, handle, metadata):
            if not hasattr(self, "failed"):
                self.failed = True
                raise OSError("temporary cleanup failure")
            super().cleanup(handle, metadata)

    good = LocalResource()
    good.required_leases = []
    flaky = FlakyResource()
    manager = EnvironmentManager(tmp_path / "managed")
    manager.register_resource("flaky", flaky)
    manager.register_resource("good", good)
    handle = manager.prepare(native(test_resources=["flaky", "good"]), repo, "resources", sha)
    with pytest.raises(OSError):
        manager.cleanup(handle)
    restarted = EnvironmentManager(tmp_path / "managed")
    restarted.register_resource("flaky", flaky)
    restarted.register_resource("good", good)
    restarted.recover(handle)
    restarted.cleanup(handle)
    assert len(good.cleaned) == 1
    assert len(flaky.cleaned) == 1


def test_docker_image_cannot_be_interpreted_as_extra_flags(tmp_path):
    manager = EnvironmentManager(tmp_path, executable_lookup=lambda _: None)
    spec = EnvironmentSpec(
        name="docker", execution="docker", workspace="clone", image="--privileged"
    )
    assert "image" in " ".join(manager.inspect(spec))
