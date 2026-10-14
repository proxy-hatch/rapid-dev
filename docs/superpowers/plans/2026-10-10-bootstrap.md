# rapid-ship Implementation Plan

Historical bootstrap record. Paths and commands below describe that checkpoint; use the [current architecture and development commands](../../../ARCHITECTURE.md#develop-the-framework) for ongoing changes.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Deliver the first tested, installable framework with deterministic onboarding, durable orchestration, composable environments, CLI agents, evidence gates and explicit GitHub operations.

**Architecture:** A Python package exposes `devctl`. Pydantic validates devctl’s own input and storage formats; SQLite records state and effects. External command execution and GitHub transport are injected at boundaries for deterministic tests; production operations remain gated by explicit project policy and validated capabilities.

Managed projects can use any language. The stack below is for devctl itself.

**Tech Stack:** Python >=3.12 (development 3.13), Pydantic 2, standard-library SQLite/subprocess/argparse, uv, pytest, Ruff, mypy.

**Spec:** `docs/superpowers/specs/2026-10-10-framework.md`, deleted on 2026-10-14 and replaced by the [rapid-ship design](../specs/2026-10-14-rapid-ship-design.md). Read the old spec from git history.

## Global Constraints

- No candidate command execution in a credential-bearing broker context.
- Read-only doctor; initialization preserves existing files.
- No implicit environment fallback or automatic human approval.
- Environment composition is workspace + execution + test resources.
- No blind retry of uncertain external operations.
- Tests must distinguish simulated services from live verification.
- Avoid new runtime dependencies beyond Pydantic.
- Package modules live in `src/agentic_engineering/`; tests in `tests/`.
- Every implementation branch has an independent review before integration.

## Review Focus

1. Path traversal and symlinks across workspace/config/artifact boundaries.
2. Process death after an external effect but before its local result was recorded.
3. Expired lease owners attempting to publish or release another attempt's resources.
4. Reusing evidence after head, base, recipe, policy or environment changes.
5. Treating a worktree, fake provider, unavailable CLI or unsigned approval as sufficient isolation/authority.

## Task 1: Contracts and validation

**Files:** `src/agentic_engineering/__init__.py`, `models.py`, `tests/test_models.py`.

**Produces:** Frozen strict Pydantic models exported by `models.py`: `Resources(memory_mb=2048,cpu=1.0)`, `EnvironmentSpec`, `ProjectConfig`, `TaskSpec`, `EvidenceBinding`, `CheckResult`, `ReviewFinding`, `ReviewDecision`, `TaskEvidence`. Literal state and status values use strings. Canonical `digest(value: BaseModel|dict[str,object]) -> str` is SHA256 of sorted compact JSON. `validate_task_graph(tasks: list[TaskSpec]) -> None`; `paths_overlap(left: list[str],right: list[str]) -> bool` rejects ancestor/descendant overlaps, treats a wildcard conservatively, and is case-sensitive.

**Contract fields:**

- `EnvironmentSpec`: `name`, `workspace` (`clone`/`worktree`), `execution` (`native`/`docker`/`sbx`/`openhands`), `image: str|None`, `resources: Resources`, `private_network: bool=True`, `exclusive_resources: list[str]`, `test_resources: list[str]`, `allow_native: bool=False`, `verified: bool=False`. `native` with `private_network=True` is unsatisfied, not silently accepted. Test-resource strings name resources registered in project configuration; they are not credentials.
- `ProjectConfig`: `schema_version: Literal[1]=1`, `name`, `design_path`, `profile="custom"`, `repository: str|None`, `default_branch="main"`, `max_parallel=1`, `memory_budget_mb=4096`, `cpu_budget=4.0`, `max_repair_rounds=2`, `environments: list[EnvironmentSpec]`, `checks: dict[str,list[str]]`, `worker_runner="codex"`, `reviewer_runner="claude"`. Configuration grants no merge/release authority itself.
- `TaskSpec`: `id`, `title`, `description`, `depends_on: list[str]`, `owned_paths: list[str]`, `acceptance: list[str]`, `environment: str`, `base_sha: str`, `timeout_seconds=1800`, `runner: str|None`, `checks: list[str]`. Paths are nonempty safe relative paths (no dotdot, absolute, NUL); task IDs are safe path components.
- `EvidenceBinding`: `task_id`, `attempt_id`, `head_sha`, `base_sha`, `policy_digest`, `recipe_digest`, `environment_digest`, `controller_version`.
- `CheckResult`: `name`, `argv: list[str]`, `exit_code`, `duration_seconds`, `stdout`, `stderr`.
- `ReviewFinding`: `severity` (`critical`/`important`/`minor`), `message`, `path: str|None`, `line: int|None`.
- `ReviewDecision`: `binding: EvidenceBinding`, `verdict` (`approve`/`changes_requested`/`blocked`), `findings: list[ReviewFinding]`, `reviewer_runner`, `independent: bool`, `summary`.
- `TaskEvidence`: `binding`, `checks: list[CheckResult]`, `review: ReviewDecision|None`, `live: bool=False`, `artifact_paths: list[str]`.

- [x] Write and run failing validation tests, including unsafe paths, unknown fields, cycles, missing dependencies, duplicate IDs, invalid resources, empty acceptance, deterministic digest and path ownership conflicts.
- [x] Implement the models and helpers; fail early on invalid user input.
- [x] Run `uv run pytest tests/test_models.py`, `uv run ruff check .`, `uv run mypy src`; commit only owned files.

```python
def test_cycle_is_rejected():
    a = task(id="a", depends_on=["b"])
    b = task(id="b", depends_on=["a"])
    with pytest.raises(ValueError, match="cycle"):
        validate_task_graph([a, b])
```

## Task 2: Durable workflow store

**Files:** `storage.py`, `tests/test_storage.py`.

**Consumes:** TaskSpec and EvidenceBinding. **Produces:** `Store(path: Path, clock: Callable[[],float]=time.time)` with `add_tasks(list[TaskSpec])`, `tasks() -> list[dict[str,Any]]`, `get_task(id) -> dict[str,Any]`, `claim(task_id, owner, ttl_seconds=60) -> str` (attempt ID), `heartbeat(attempt_id,owner,ttl_seconds=60)`, `transition(task_id,state,attempt_id=None,owner=None,note="")`, `acquire_resources(attempt_id,owner,names,ttl_seconds=60)`, `release_resources(attempt_id,owner)`, `record_event(kind,payload)`, `events()`, `begin_effect(key,kind,payload) -> dict[str,Any]`, `finish_effect(key,result)`, `mark_effect_uncertain(key,note)`, `get_effect(key)`, `close()`. Context manager support.

States: pending, running, verifying, reviewing, needs_repair, approved, merged, released, blocked, failed, cancelled. Valid path: pending->running->verifying->reviewing->approved->merged->released; reviewing->needs_repair->running; running/verifying/reviewing->blocked/failed/cancelled; blocked->pending only explicit resume. Claims require dependencies approved/merged/released; active ownership conflicts block claims. State changes in active attempts require current unexpired owner. Resource acquisition is atomic across names. Duplicate task IDs with identical specs are idempotent; changed specs error. Effects are pending/completed/uncertain; begin on existing key verifies kind/payload equality and never resets uncertain/completed records.

- [x] Test real temporary SQLite databases using two connections: one task claim wins, overlapping paths block, expired owners cannot write, resources are all-or-nothing, restart preserves events, and uncertain effects survive retries.
- [x] Implement WAL, foreign keys, transactional transitions and event append. Schema migration uses a version and rejects newer schemas.
- [x] Run the task tests and full available suite; commit only owned files.

```python
def test_uncertain_effect_is_not_restarted(tmp_path):
    with Store(tmp_path / "state.db") as store:
        store.begin_effect("pr:a", "create_pr", {"head": "a"})
        store.mark_effect_uncertain("pr:a", "connection lost")
        assert store.begin_effect("pr:a", "create_pr", {"head": "a"})["status"] == "uncertain"
```

## Task 3: Environment providers and process supervision

**Files:** `environments.py`, `process.py`, `tests/test_environments.py`, `tests/test_process.py`.

**Consumes:** EnvironmentSpec, Resources, TaskSpec. **Produces:** `ProcessResult(argv,returncode,stdout,stderr,duration_seconds,timed_out=False)`; `run_process(argv: list[str],cwd: Path,timeout_seconds: float,env: dict[str,str]|None=None,input_text: str|None=None,cancel_event: threading.Event|None=None) -> ProcessResult`; `EnvironmentManager(root: Path)` with `inspect(spec) -> list[str]` blockers, `prepare(spec,source:Path,task_id:str,base_sha:str) -> EnvironmentHandle`, `execute(handle,argv,timeout_seconds,input_text=None,cancel_event=None) -> ProcessResult`, `cleanup(handle)`. EnvironmentHandle records ID, spec, workspace path, provider ID, preparation metadata. `resolve_environment(config,task) -> EnvironmentSpec` enforces resource and named environment requirements.

Workspace clones must be independent (no hardlinks/shared Git directories); worktrees must use unique branches/paths and preserve dirty parent changes. Never delete pre-existing paths; cleanup only framework-owned paths after validating identity. Native requires allow_native and cannot promise private networking. Docker uses a private container with only task workspace mount, no privileged mode/socket/home, configurable CPU/memory, no inherited secret env, and image required. sbx and OpenHands inspect availability and configuration, blocking unsupported/unverified execution rather than pretending compatibility. Docker lifecycle must actually execute through `docker` argv; external commands are injectable for unit tests. Test resources are provisioned only through registered adapters; unknown resources block.

- [x] Test independent Git clone contents, dirty parent preservation, path escape rejection, fixed shared host resource declarations, configurable resources, and native isolation mismatch.
- [x] Test real subprocess stdin/output, timeout, cancellation and grandchild process termination. Retain bounded output; no shell=True.
- [x] Implement providers with explicit unsupported capability errors; no silent native fallback.
- [x] Run targeted tests plus available full suite; commit only owned files.

```python
def test_native_cannot_satisfy_private_network(tmp_path):
    spec = EnvironmentSpec(name="native", execution="native", workspace="clone", allow_native=True)
    assert "private_network" in " ".join(EnvironmentManager(tmp_path).inspect(spec))
```

## Task 4: Onboarding, profiles and project skills

**Files:** `configuration.py`, `profiles.py`, `skills/`, `tests/test_configuration.py`, `tests/test_profiles.py`.

**Consumes:** ProjectConfig and EnvironmentSpec. **Produces:** `init_project(root:Path,name:str,design_path:str,profile:str="python-cli") -> dict[str,Any]`, `load_config(root)->ProjectConfig`, `save_config(root,config)`, `doctor(root)->dict[str,Any]`, `interview_next(root)->dict[str,Any]`, `answer_question(root,question_id,value)->dict[str,Any]`, `scaffold_feature(root,name)->list[str]`. Canonical tracked config `.devctl/project.json`; gitignored runtime `.devctl/state/`; interview `.devctl/interview.json`. Doctor does not create directories or files. Initialization creates only absent framework files and records incomplete decisions rather than marking placeholders ready. Existing invalid configuration must error, not be replaced.

Questions cover repository, worker/reviewer runner, selected execution environment, resource budgets, test resources, checks and release target. Framework defaults choose native with allow_native=False/private_network=False until explicitly answered; never infer authorization from installed tools. Design path must exist within project and be nonempty. Package profile files and skill resources in wheel. Generate a short AGENTS fragment without replacing existing AGENTS.md. Golden scaffolding uses a safe name and refuses overwrites; scaffold one CLI feature with a testable function and tests.

- [x] Test interrupted/repeated init preserves bytes, doctor produces no writes, invalid answers don't advance interview, valid answers persist, missing design blocks readiness, and unsafe scaffold names fail.
- [x] Implement one-question-at-a-time state with answer provenance and deterministic next question; profile ownership manifest makes upgrade boundaries explicit.
- [x] Test package resources and one generated feature's actual behaviour; commit only owned files.

```python
def test_doctor_does_not_create_project(tmp_path):
    result = doctor(tmp_path)
    assert not result["ready"]
    assert list(tmp_path.iterdir()) == []
```

## Task 5: Runners, evidence and scheduler integration

**Files:** `runners.py`, `evidence.py`, `controller.py`, task-specific tests.

**Consumes:** Models, Store, EnvironmentManager and process API. **Produces:** codex/claude argument adapters, JSONL event parsing, explicit native-session handling; `validate_evidence(evidence,expected,required_checks)->list[str]`; an orchestration Controller that creates attempts, acquires resource reservations, runs worker, computes Git diff and head, verifies named checks, builds independent reviewer prompt, validates structured review, bounds repair loops, and persists evidence/state. Never directly spawn a host runner when the environment adapter is selected. Recheck binding after review. The reviewer cannot mutate the worker workspace; use independent clone/read-only permissions as provider allows. Unknown runner output is blocked, not an approval.

- [x] Test actual fixture CLI subprocesses for success, malformed output, nonzero exit, timeout, interruption and resume by explicit session ID.
- [x] Test stale base/policy/environment evidence and missing checks; test approvals with important findings fail.
- [x] Test two disjoint tasks and a dependency using actual temporary Git repos and native provider explicitly approved for tests; tests label fixtures as simulated and cannot promote live capabilities.
- [x] Integrate progress events, heartbeat and cancellation. Record partial artifacts before marking failure.

## Task 6: Policy, trials and GitHub effect broker

**Files:** `policy.py`, `github.py`, `trials.py`, broker tests.

**Produces:** explicit capability grant records bound to recipe/environment/policy; trial recording and promotion validation; immutable governing policy snapshots; GitHub read/PR/merge/release adapter using subprocess `gh` without passing credentials in argv. Mutations require grant + fresh evidence + server protections. Broker receives candidate artifacts, not shell commands. Use clean Git repositories with hooks disabled for pushing. Stable operation IDs reconcile PR lookup by exact repo/head/base and recorded marker, merge by expected head and merged commit, releases by tag and artifact digest. Uncertain outcomes are not automatically repeated.

- [x] Test stale evidence, unverified environment, simulated trial, missing human signoff, policy weakening and unavailable GitHub protection block effects.
- [x] Test a fake GitHub transport that performs an operation then loses the response; reconciliation finds the prior object and doesn't duplicate it.
- [x] Test strict/app-bound check inspection, expected head mismatch, serialized merge and release digest mismatch.
- [x] Provide live read-only preflight and explicit operations; no user account or GitHub App provisioning is fabricated.

## Task 7: CLI, documentation, CI and end-to-end acceptance

**Files:** `cli.py`, `__main__.py`, `README.md`, `devctl`, `.github/workflows/ci.yml`, `tests/test_cli.py`, examples.

- [x] Implement argparse commands from the spec, JSON output and clear blocked/invalid/failure exit codes. Expose supported operations only; unavailable backend operations return actionable blockers.
- [x] Exercise a clean install's init->interview->doctor->decompose->run->evidence flow using a labelled fixture agent; no network or genuine credentials in the test.
- [x] Add profiles and provider documentation, trust boundary explanation, quickstart, and examples for fixed-port isolation and AWS-resource declarations.
- [x] Run `uv run pytest`, `uv run ruff check .`, `uv run mypy src`, `uv build`; install wheel into clean environment and run CLI smoke tests.
- [x] Run an independent security/correctness review, fix actionable findings, and create a draft integration PR with verified results. Do not automatically grant live autonomy, upgrade the controller, or publish the first production release before human trials.

## Execution record

Use the per-plan SDD ledger for task status, commits, review outcomes and rulings. Independent tasks may run in separate worktrees concurrently; owned files and interface contracts prevent shared edits. Integration stays serial.


## Bootstrap validation status (2026-10-10)

Implementation and independent review are complete through commit `21762cd`. The macOS source suite passes 398 tests; Ruff, strict mypy and distribution builds pass. The full CLI flow uses explicitly simulated agents and sealed evidence. Clean-wheel installation and the installed simulated workflow pass. GitHub CI passes on Linux with Python 3.12 and 3.13. Live trials and GitHub authority remain separate rollout gates, as required by the spec. See `docs/bootstrap-validation.md` for evidence and limitations.

The private repository's branch-protection preflight returns HTTP 403 on the current account plan. No visibility change, authority grant, installed controller upgrade or production release has been made. OpenHands and AWS resource implementations remain unavailable until trusted adapters are supplied.


## User corrections: metrics, language support and writing

New projects use the neutral `custom` profile and start with one task. Python is an explicit preset. Every installation collects controller measurements, syncs PR and Actions data through `metrics sync-github`, and accepts external metrics through `metrics import`; see `docs/metrics.md` for the format and calculations. Shared writing instructions now reach project agents and controller prompts. Existing project files and saved results remain compatible.
