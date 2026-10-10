"""Composable source, execution, and explicitly registered test-resource providers."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

from .models import EnvironmentSpec, ProjectConfig, TaskSpec
from .process import ProcessResult, run_process


class EnvironmentBlocked(RuntimeError):
    """The requested environment cannot satisfy declared requirements."""


class ResourceCleanupNotApplied(OSError):
    """A trusted resource adapter established cleanup caused no external effect."""


@dataclass(frozen=True)
class EnvironmentHandle:
    id: str
    spec: EnvironmentSpec
    workspace: Path
    provider_id: str
    metadata: dict[str, object]


class CommandTransport(Protocol):
    def __call__(
        self,
        argv: list[str],
        cwd: Path,
        timeout_seconds: float,
        env: dict[str, str] | None = None,
        input_text: str | None = None,
        cancel_event: threading.Event | None = None,
    ) -> ProcessResult: ...


class ResourceProvider(Protocol):
    """Named provider; fixed host/global resources declare required lease names.

    The controller must acquire spec.exclusive_resources before preparation.
    Registration is explicit authority to provision the named test resource;
    unknown cloud account/stack names are never interpreted automatically.
    Cleanup receives {"preparation": "uncertain"} after a lost preparation
    response; adapters must reconcile by handle.id or raise a blocker, never
    claim cleanup succeeded without confirming resource ownership/outcome.
    Cleanup intent is durable before every effect. After an unknown outcome,
    an adapter's optional reconcile_cleanup(handle, metadata) must return
    'completed', 'not-applied', or 'unknown' using the stable handle.id and actual
    resource state. Missing/unknown reconciliation blocks retries. A known
    before-effect failure may raise ResourceCleanupNotApplied to permit retry.
    """

    required_leases: list[str]

    def inspect(self, spec: EnvironmentSpec) -> list[str]: ...
    def prepare(self, handle: EnvironmentHandle) -> dict[str, object]: ...
    def cleanup(self, handle: EnvironmentHandle, metadata: dict[str, object]) -> None: ...


def resolve_environment(config: ProjectConfig, task: TaskSpec) -> EnvironmentSpec:
    matches = [spec for spec in config.environments if spec.name == task.environment]
    if len(matches) != 1:
        raise EnvironmentBlocked(f"environment {task.environment!r} is missing or ambiguous")
    spec = matches[0]
    blockers: list[str] = []
    if spec.resources.memory_mb > config.memory_budget_mb:
        blockers.append("memory requirement exceeds configured memory budget")
    if spec.resources.cpu > config.cpu_budget:
        blockers.append("cpu requirement exceeds configured cpu budget")
    if spec.execution == "native":
        if not spec.allow_native:
            blockers.append("native requires explicit allow_native grant")
        if spec.private_network:
            blockers.append("native cannot satisfy private_network")
    if blockers:
        raise EnvironmentBlocked("; ".join(blockers))
    return spec


class EnvironmentManager:
    """Own disposable workspaces and execute only the selected provider.

    inspect is read-only and describes technical blockers. spec.verified is a
    separate trial/policy fact: an unverified provider may be provisioned for a
    human-supervised compatibility trial, but cannot thereby acquire autonomy.
    Native grants permit host filesystem access; HOME and environment isolation
    avoid accidental credential inheritance, not malicious host filesystem use.
    """

    def __init__(
        self,
        root: Path,
        *,
        transport: CommandTransport = run_process,
        executable_lookup: Callable[[str], str | None] = shutil.which,
        sandbox_configuration: dict[str, object] | None = None,
    ) -> None:
        if root.is_symlink():
            raise ValueError("managed root must not be a symlink")
        self.root = root.resolve()
        self.transport = transport
        self.executable_lookup = executable_lookup
        self.sandbox_configuration = dict(sandbox_configuration or {})
        self._resources: dict[str, ResourceProvider] = {}
        self._owned: dict[str, str] = {}
        self._observer: Callable[[EnvironmentHandle], None] | None = None
        self._stopped: set[str] = set()
        self._stop_requested: set[str] = set()
        self._cleanup_done: dict[str, set[str]] = {}

    def set_observer(self, callback: Callable[[EnvironmentHandle], None]) -> None:
        """Observe each persisted preparation identity before subsequent effects.

        Controller callbacks may durably bind the handle to its attempt. Their
        failures propagate, preventing the next preparation effect from running.
        """
        self._observer = callback

    @staticmethod
    def _handle_from_record(record: str) -> EnvironmentHandle:
        value = json.loads(record)
        return EnvironmentHandle(
            id=value["id"],
            spec=EnvironmentSpec.model_validate(value["spec"]),
            workspace=Path(value["workspace"]),
            provider_id=value["provider_id"],
            metadata=value["metadata"],
        )

    def owned_handles(self) -> list[EnvironmentHandle]:
        """Snapshot trusted retained handles, without inspecting candidate files.

        Decoding our in-memory records also detaches nested metadata/spec lists
        so callers cannot mutate the manager's expected ownership identities.
        """
        return [self._handle_from_record(record) for record in list(self._owned.values())]

    def register_resource(self, name: str, provider: ResourceProvider) -> None:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]*", name):
            raise ValueError("resource name must be a safe nonempty identifier")
        if name in self._resources:
            raise ValueError(f"resource provider {name!r} already registered")
        self._resources[name] = provider

    def inspect(self, spec: EnvironmentSpec) -> list[str]:
        blockers: list[str] = []
        if spec.workspace == "worktree" and spec.execution != "native":
            blockers.append(
                "worktree Git metadata points outside the mounted task workspace; "
                "nonnative execution requires an independent clone"
            )
        if spec.execution == "native":
            if not spec.allow_native:
                blockers.append("native execution requires explicit allow_native grant")
            if spec.private_network:
                blockers.append("native cannot satisfy private_network isolation")
        elif spec.execution == "docker":
            if not spec.image:
                blockers.append("docker requires an explicit image")
            elif spec.image.startswith("-") or any(c.isspace() for c in spec.image):
                blockers.append("docker image must be a reference, not a command option")
            if self.executable_lookup("docker") is None:
                blockers.append("docker CLI unavailable")
            else:
                try:
                    result = self.transport(
                        ["docker", "info", "--format", "{{json .ServerVersion}}"], Path.cwd(), 10
                    )
                    if result.returncode != 0 or result.timed_out or result.cancelled:
                        blockers.append("docker daemon unavailable: " + result.stderr.strip())
                except OSError as exc:
                    blockers.append(f"docker daemon unavailable: {exc}")
        elif spec.execution == "sbx":
            if self.executable_lookup("sbx") is None:
                blockers.append("sbx CLI unavailable")
            else:
                try:
                    setting = self.transport(
                        ["sbx", "settings", "get", "ssh.agentForwardingEnabled"],
                        Path.cwd(),
                        10,
                    )
                    if (
                        setting.returncode != 0
                        or setting.timed_out
                        or setting.cancelled
                        or setting.stdout.strip().lower() != "false"
                    ):
                        blockers.append("sbx SSH agent forwarding is enabled or unverified")
                except OSError as exc:
                    blockers.append(f"sbx SSH agent forwarding configuration unavailable: {exc}")
            if self.sandbox_configuration.get("github_credentials_absent") is not True:
                blockers.append(
                    "sbx forbidden GitHub credential bindings have not been checked; "
                    "model endpoint authentication alone is not broker authority"
                )
            if self.sandbox_configuration.get("compatibility_verified") is not True:
                blockers.append("sbx execution configuration/CLI compatibility unverified")
            if self.sandbox_configuration.get("agent", "shell") != "shell":
                blockers.append("sbx adapter supports the shell agent only")
            # Network policies differ by sbx version: do not infer compatibility.
            if (
                spec.private_network
                and self.sandbox_configuration.get("private_network") is not True
            ):
                blockers.append("sbx private_network capability unverified")
        elif spec.execution == "openhands":
            if self.executable_lookup("openhands") is None:
                blockers.append("OpenHands CLI unavailable")
            blockers.append(
                "OpenHands execution API/configuration compatibility unverified; "
                "no configured execution adapter"
            )
        else:
            blockers.append(f"unsupported execution provider {spec.execution!r}")
        for name in spec.test_resources:
            adapter = self._resources.get(name)
            if adapter is None:
                blockers.append(f"test resource {name!r} is unregistered")
                continue
            missing = set(adapter.required_leases) - set(spec.exclusive_resources)
            if missing:
                blockers.append(
                    f"test resource {name!r} requires exclusive_resources: "
                    + ", ".join(sorted(missing))
                )
            blockers.extend(adapter.inspect(spec))
        return blockers

    def _git(self, source: Path, *argv: str) -> ProcessResult:
        git_env = {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_NO_LAZY_FETCH": "1",
            "GIT_ALLOW_PROTOCOL": "file" if argv and argv[0] == "clone" else "",
            "GIT_SSH_COMMAND": "/usr/bin/false",
        }
        prefix = [
            "git",
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "protocol.allow=never",
            "-c",
            "protocol.file.allow=" + ("always" if argv and argv[0] == "clone" else "never"),
            "-c",
            "core.sshCommand=/usr/bin/false",
            "-C",
            str(source),
        ]
        # Worktrees share local Git configuration. Disable every configured
        # filter so source checkout cannot execute candidate smudge/process code
        # on the controller host before the execution provider is selected.
        filters = run_process(
            [
                *prefix,
                "config",
                "--name-only",
                "--get-regexp",
                r"^filter\..*\.(smudge|clean|process|required)$",
            ],
            source,
            10,
            env=git_env,
        )
        if filters.returncode not in {0, 1} or filters.timed_out or filters.cancelled:
            raise EnvironmentBlocked("cannot inspect repository Git filters safely")
        if "[output truncated]" in filters.stdout:
            raise EnvironmentBlocked("repository Git filter configuration exceeds safety bound")
        for key in filters.stdout.splitlines():
            if not re.fullmatch(r"filter\.[^\x00-\x20\x7f]+\.(smudge|clean|process|required)", key):
                raise EnvironmentBlocked("unsupported Git filter configuration key")
            prefix.extend(["-c", key + ("=false" if key.endswith(".required") else "=")])
        result = run_process([*prefix, *argv], source, 120, env=git_env)
        if result.returncode != 0 or result.timed_out or result.cancelled:
            raise EnvironmentBlocked("Git workspace preparation failed: " + result.stderr.strip())
        return result

    def _command(self, argv: list[str], cwd: Path) -> ProcessResult:
        result = self.transport(argv, cwd, 30)
        if result.returncode != 0 or result.timed_out or result.cancelled:
            raise EnvironmentBlocked(f"{argv[0]} provider command failed: {result.stderr.strip()}")
        return result

    @staticmethod
    def _record(handle: EnvironmentHandle) -> str:
        return json.dumps(
            {
                "id": handle.id,
                "workspace": str(handle.workspace),
                "provider_id": handle.provider_id,
                "spec": handle.spec.model_dump(mode="json"),
                "metadata": handle.metadata,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    def _remember(self, handle: EnvironmentHandle) -> None:
        record = self._record(handle)
        marker = handle.workspace.parent / "owner.json"
        if marker.is_symlink():
            raise ValueError("ownership marker must not be a symlink")
        fd, temporary = tempfile.mkstemp(prefix=".owner-", dir=marker.parent)
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write(record)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, marker)
        self._owned[handle.id] = record
        if self._observer is not None:
            self._observer(self._handle_from_record(record))

    def _validate(self, handle: EnvironmentHandle) -> None:
        record = self._record(handle)
        owner_dir = handle.workspace.parent
        if (
            self.root.is_symlink()
            or self.root.resolve() != self.root
            or owner_dir.parent != self.root
            or owner_dir.is_symlink()
            or owner_dir.resolve() != owner_dir
            or handle.workspace.name != "workspace"
            or handle.workspace.is_symlink()
            or handle.workspace.resolve() != handle.workspace
            or self._owned.get(handle.id) != record
        ):
            raise ValueError("environment ownership/path identity mismatch")
        marker = owner_dir / "owner.json"
        if marker.is_symlink() or not marker.is_file() or marker.read_text() != record:
            raise ValueError("environment ownership marker mismatch")

    def recover(self, handle: EnvironmentHandle) -> None:
        """Explicitly recover a handle from trusted durable controller state.

        Do not discover authority by scanning arbitrary workspace files. The
        supplied expected handle must match the persisted ownership record.
        Recovery performs no resource effects; uncertain cleanup stays blocked.
        """
        record = self._record(handle)
        previous = self._owned.get(handle.id)
        self._owned[handle.id] = record
        try:
            self._validate(handle)
            progress = handle.workspace.parent / "cleanup.json"
            if progress.is_symlink():
                raise ValueError("cleanup progress must not be a symlink")
            done: object = json.loads(progress.read_text()) if progress.exists() else []
            if not isinstance(done, list) or any(not isinstance(item, str) for item in done):
                raise ValueError("invalid persisted cleanup progress")
            self._cleanup_done[handle.id] = set(done)
            if "execution-stop-requested" in done:
                self._stop_requested.add(handle.id)
            if "execution-stopped" in done:
                self._stopped.add(handle.id)
        except BaseException:
            if previous is None:
                self._owned.pop(handle.id, None)
            else:
                self._owned[handle.id] = previous
            raise

    def _mark_done(self, handle: EnvironmentHandle, operation: str) -> None:
        done = self._cleanup_done.setdefault(handle.id, set())
        done.add(operation)
        self._persist_progress(handle)

    def _clear_done(self, handle: EnvironmentHandle, operation: str) -> None:
        self._cleanup_done.setdefault(handle.id, set()).discard(operation)
        self._persist_progress(handle)

    def _persist_progress(self, handle: EnvironmentHandle) -> None:
        done = self._cleanup_done.setdefault(handle.id, set())
        progress = handle.workspace.parent / "cleanup.json"
        if progress.is_symlink():
            raise ValueError("cleanup progress must not be a symlink")
        fd, temporary = tempfile.mkstemp(prefix=".cleanup-", dir=progress.parent)
        with os.fdopen(fd, "w") as output:
            json.dump(sorted(done), output)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, progress)

    def prepare(
        self,
        spec: EnvironmentSpec,
        source: Path,
        task_id: str,
        base_sha: str,
    ) -> EnvironmentHandle:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", task_id) or task_id in {".", ".."}:
            raise ValueError("task_id must be a safe path component")
        if not re.fullmatch(r"(?:[a-fA-F0-9]{40}|[a-fA-F0-9]{64})", base_sha):
            raise ValueError("base_sha must be a full Git object ID")
        blockers = self.inspect(spec)
        if blockers:
            raise EnvironmentBlocked("; ".join(blockers))
        source = source.resolve(strict=True)
        if not source.is_dir():
            raise ValueError("source must be a repository directory")
        self._git(source, "rev-parse", "--verify", f"{base_sha}^{{commit}}")
        if self.root.is_symlink() or self.root.resolve() != self.root:
            raise ValueError("managed root identity changed")
        self.root.mkdir(parents=True, exist_ok=True)
        owner_dir = Path(tempfile.mkdtemp(prefix=f"{task_id}-", dir=self.root))
        workspace = owner_dir / "workspace"
        identifier = uuid.uuid4().hex
        branch = f"codex/task-{task_id}-{identifier}"
        handle = EnvironmentHandle(
            identifier,
            spec,
            workspace,
            spec.execution,
            {"source": str(source), "branch": branch, "resources": {}},
        )
        self._remember(handle)
        try:
            if spec.workspace == "clone":
                self._git(
                    source,
                    "clone",
                    "--no-local",
                    "--no-hardlinks",
                    "--no-checkout",
                    "--",
                    str(source),
                    str(workspace),
                )
                self._git(workspace, "checkout", "-b", branch, base_sha)
            elif spec.workspace == "worktree":
                self._git(source, "worktree", "add", "-b", branch, str(workspace), base_sha)
            else:
                raise EnvironmentBlocked(f"unsupported workspace provider {spec.workspace!r}")
            (owner_dir / "home").mkdir(mode=0o700)
            if spec.execution == "docker":
                if "," in str(workspace):
                    raise EnvironmentBlocked("Docker bind mount path cannot contain commas")
                argv = [
                    "docker",
                    "create",
                    "--name",
                    f"devctl-{identifier}",
                    "--label",
                    f"devctl.owner={identifier}",
                    "--network",
                    "none" if spec.private_network else "bridge",
                    "--memory",
                    f"{spec.resources.memory_mb}m",
                    "--cpus",
                    str(spec.resources.cpu),
                    "--cap-drop",
                    "ALL",
                    "--security-opt",
                    "no-new-privileges",
                    "--pids-limit",
                    "256",
                    "--user",
                    f"{os.getuid()}:{os.getgid()}",
                    "--mount",
                    f"type=bind,src={workspace},dst=/workspace",
                    "--workdir",
                    "/workspace",
                    "--env",
                    "HOME=/tmp",
                    str(spec.image),
                    "sleep",
                    "infinity",
                ]
                handle = replace(
                    handle, metadata={**handle.metadata, "container": f"devctl-{identifier}"}
                )
                self._remember(handle)  # Persist identity before the external effect.
                container = self._command(argv, owner_dir).stdout.strip()
                if not re.fullmatch(r"[A-Za-z0-9_.-]+", container):
                    raise EnvironmentBlocked(
                        "Docker create did not return a valid container identity"
                    )
                handle = replace(handle, metadata={**handle.metadata, "container": container})
                self._remember(handle)
                self._command(["docker", "start", container], owner_dir)
            elif spec.execution == "sbx":
                sandbox = f"devctl-{identifier}"
                argv = [
                    "sbx",
                    "create",
                    "--name",
                    sandbox,
                    "--memory",
                    f"{spec.resources.memory_mb}m",
                    "--cpus",
                    str(spec.resources.cpu),
                    "--skills",
                    "off",
                ]
                if spec.image:
                    argv.extend(["--template", spec.image])
                argv.extend(["shell", str(workspace)])
                # Record the assigned owned identity before creation so a lost
                # command response never authorizes a duplicate resource.
                handle = replace(handle, metadata={**handle.metadata, "sandbox": sandbox})
                self._remember(handle)
                self._command(argv, owner_dir)
            resource_metadata: dict[str, object] = {}
            for name in spec.test_resources:
                resource_metadata[name] = {"preparation": "uncertain"}
                handle = replace(
                    handle, metadata={**handle.metadata, "resources": dict(resource_metadata)}
                )
                self._remember(handle)  # Resource identity precedes any provision effect.
                resource_metadata[name] = self._resources[name].prepare(handle)
                handle = replace(
                    handle, metadata={**handle.metadata, "resources": dict(resource_metadata)}
                )
                self._remember(handle)
            return handle
        except BaseException:
            # Keep evidence and ownership when cleanup cannot be proved safe.
            self.cleanup(handle)
            raise

    def execute(
        self,
        handle: EnvironmentHandle,
        argv: list[str],
        timeout_seconds: float,
        input_text: str | None = None,
        cancel_event: threading.Event | None = None,
    ) -> ProcessResult:
        self._validate(handle)
        if handle.id in self._stopped or handle.id in self._stop_requested:
            raise EnvironmentBlocked("execution environment stopped after cancellation/timeout")
        if not argv or any("\0" in arg for arg in argv):
            raise ValueError("nonempty safe argv required")
        if "native-execution-inflight" in self._cleanup_done.get(handle.id, set()):
            raise EnvironmentBlocked("native in-flight execution requires reconciliation")
        if handle.provider_id == "native":
            self._mark_done(handle, "native-execution-inflight")
            result = self.transport(
                argv,
                handle.workspace,
                timeout_seconds,
                env={
                    "HOME": str(handle.workspace.parent / "home"),
                    "GIT_CONFIG_NOSYSTEM": "1",
                    "GIT_CONFIG_GLOBAL": "/dev/null",
                },
                input_text=input_text,
                cancel_event=cancel_event,
            )
            # run_process returns only after killing/reaping its process group.
            # Exceptions or caller death preserve the durable unknown outcome.
            self._clear_done(handle, "native-execution-inflight")
            return result
        if handle.provider_id == "docker":
            container = str(handle.metadata["container"])
            command = [
                "docker",
                "exec",
                "-i",
                "--workdir",
                "/workspace",
                "--env",
                "HOME=/tmp",
                container,
                *argv,
            ]
        elif handle.provider_id == "sbx":
            command = [
                "sbx",
                "exec",
                "-i",
                "-w",
                str(handle.workspace),
                str(handle.metadata["sandbox"]),
                *argv,
            ]
        else:
            raise EnvironmentBlocked(f"unsupported execution provider {handle.provider_id!r}")
        result = self.transport(
            command,
            handle.workspace,
            timeout_seconds,
            input_text=input_text,
            cancel_event=cancel_event,
        )
        if result.timed_out or result.cancelled:
            self.stop(handle)
        return result

    def stop(self, handle: EnvironmentHandle) -> None:
        """Quiesce provider processes while preserving the candidate workspace.

        The controller calls this after synchronous execution, before host-side
        artifact copies. Uncertain stop outcomes are never recorded as confirmed
        and execution is fenced until operation-specific reconciliation succeeds.
        """
        self._validate(handle)
        if "native-execution-inflight" in self._cleanup_done.get(handle.id, set()):
            raise EnvironmentBlocked(
                "native in-flight execution requires reconciliation; "
                "quiescence cannot be inferred after caller death"
            )
        if handle.id in self._stopped:
            return
        uncertain = handle.id in self._stop_requested
        if handle.provider_id == "docker" and "container" in handle.metadata:
            container = str(handle.metadata["container"])
            owner = self._command(
                [
                    "docker",
                    "inspect",
                    "--format",
                    '{{index .Config.Labels "devctl.owner"}}',
                    container,
                ],
                handle.workspace.parent,
            ).stdout.strip()
            if owner != handle.id:
                raise ValueError("container ownership label mismatch")
            running = (
                self._command(
                    ["docker", "inspect", "--format", "{{.State.Running}}", container],
                    handle.workspace.parent,
                )
                .stdout.strip()
                .lower()
            )
            if running not in {"true", "false"}:
                raise EnvironmentBlocked("container running state is unverified")
            if running == "true":
                if uncertain:
                    raise EnvironmentBlocked("previous container stop needs reconciliation")
                self._stop_requested.add(handle.id)
                self._mark_done(handle, "execution-stop-requested")
                self._command(["docker", "kill", container], handle.workspace.parent)
        elif handle.provider_id == "sbx" and "sandbox" in handle.metadata:
            if uncertain:
                raise EnvironmentBlocked("previous sandbox stop needs reconciliation")
            self._stop_requested.add(handle.id)
            self._mark_done(handle, "execution-stop-requested")
            self._command(["sbx", "stop", str(handle.metadata["sandbox"])], handle.workspace.parent)
        elif handle.provider_id != "native":
            # A provider that was never created has no processes to stop.
            if "container" in handle.metadata or "sandbox" in handle.metadata:
                raise EnvironmentBlocked("provider has no compatible stop adapter")
        self._mark_done(handle, "execution-stopped")
        self._stopped.add(handle.id)

    def cleanup(self, handle: EnvironmentHandle) -> None:
        self._validate(handle)
        owner_dir = handle.workspace.parent
        self.stop(handle)
        done = self._cleanup_done.setdefault(handle.id, set())
        if "container" in handle.metadata and "container" not in done:
            container = str(handle.metadata["container"])
            inspection = self.transport(
                [
                    "docker",
                    "inspect",
                    "--format",
                    '{{index .Config.Labels "devctl.owner"}}',
                    container,
                ],
                owner_dir,
                30,
            )
            absent = (
                inspection.returncode == 1
                and not inspection.timed_out
                and not inspection.cancelled
                and not inspection.stdout.strip()
                and re.fullmatch(
                    r"(?:Error: |Error response from daemon: )?No such "
                    r"(?:object|container): " + re.escape(container),
                    inspection.stderr.strip(),
                    flags=re.IGNORECASE,
                )
                is not None
            )
            if absent and {"container-remove-requested", "container-ownership-confirmed"} <= done:
                self._mark_done(handle, "container")
            else:
                if inspection.returncode != 0 or inspection.timed_out or inspection.cancelled:
                    raise EnvironmentBlocked(
                        "container cleanup outcome needs reconciliation: "
                        + inspection.stderr.strip()
                    )
                if inspection.stdout.strip() != handle.id:
                    raise ValueError("container ownership label mismatch")
                self._mark_done(handle, "container-ownership-confirmed")
                self._mark_done(handle, "container-remove-requested")
                self._command(["docker", "rm", "--force", container], owner_dir)
                self._mark_done(handle, "container")
        if "sandbox" in handle.metadata and "sandbox" not in done:
            sandbox = str(handle.metadata["sandbox"])
            if sandbox != f"devctl-{handle.id}":
                raise ValueError("sandbox ownership identity mismatch")
            self._command(["sbx", "rm", "--force", sandbox], owner_dir)
            self._mark_done(handle, "sandbox")
        resources = handle.metadata["resources"]
        assert isinstance(resources, dict)
        for name, metadata in reversed(list(resources.items())):
            assert isinstance(metadata, dict)
            if f"resource:{name}" not in done:
                adapter = self._resources[name]
                intent = f"resource-cleanup-requested:{name}"
                if intent in done:
                    reconcile = getattr(adapter, "reconcile_cleanup", None)
                    status = reconcile(handle, metadata) if callable(reconcile) else "unknown"
                    if status == "completed":
                        self._mark_done(handle, f"resource:{name}")
                        continue
                    if status != "not-applied":
                        raise EnvironmentBlocked(f"resource {name!r} cleanup needs reconciliation")
                    self._clear_done(handle, intent)
                self._mark_done(handle, intent)
                try:
                    adapter.cleanup(handle, metadata)
                except ResourceCleanupNotApplied:
                    self._clear_done(handle, intent)
                    raise
                self._mark_done(handle, f"resource:{name}")
        if handle.spec.workspace == "worktree":
            source = Path(str(handle.metadata["source"]))
            branch = str(handle.metadata["branch"])
            if handle.workspace.exists():
                actual_branch = self._git(
                    handle.workspace, "branch", "--show-current"
                ).stdout.strip()
                if actual_branch != branch:
                    raise ValueError("worktree branch ownership changed")
                self._git(source, "worktree", "remove", "--force", str(handle.workspace))
            # Delete only the unique branch created by this handle.
            branches = self._git(source, "branch", "--list", branch).stdout.strip()
            if branches:
                self._git(source, "branch", "-D", branch)
        shutil.rmtree(owner_dir)
        del self._owned[handle.id]
        self._stopped.discard(handle.id)
        self._stop_requested.discard(handle.id)
        self._cleanup_done.pop(handle.id, None)
