# Environment setup

Each environment combines a source workspace, a place to run code, and optional test resources. Setup checks availability and compatibility; a `verified` field alone never permits unattended delivery.

## Choose where code runs

| Choice | Support and limits |
| --- | --- |
| Clone | Separate Git metadata and disposable source. Required for isolated execution providers. |
| Worktree | Separate source with shared Git metadata. Currently native only; does not isolate files, credentials, processes, or ports. |
| Native | Requires `allow_native: true` and `private_network: false`. Uses a clean HOME and stops the process group on timeout/cancel, but retains host filesystem access. No unattended delivery. |
| Docker | Requires an explicit image and working daemon. Mounts the workspace, limits resources and PIDs, drops capabilities, forbids privilege escalation, and checks ownership during cleanup. Private mode uses network `none`; otherwise bridge networking. No host ports are published. |
| Docker Sandboxes (`sbx`) | Blocks until its CLI/settings are verified, SSH forwarding is disabled, GitHub credentials are absent, and requested networking works. No verified installation on the current host. |
| OpenHands | No execution adapter yet; setup blocks. |

Pin an image by digest for repeatable runs. Include the agent CLI, Git, runtime, check tools, and separate model authentication. Workers do not inherit host logins or install these tools automatically. Docker with network `none` cannot reach remote model services. Test the actual image and authentication path before approving it.

Memory, CPU, and concurrency are configurable. Project defaults are 4096 MB, 4 CPUs, and one task. Docker's observed allocation on this host was about 4 GB; it can be increased. Set budgets for the environments and services that will run together. Defaults are not machine limits, and quality metrics never increase concurrency automatically.

## Ports and test resources

Separate containers can share an internal port. A fixed host port, global installation, or account-wide operation needs an exclusive reservation, declared in `exclusive_resources`. The scheduler will not run conflicting tasks together. It does not infer these requirements from shell commands.

[Examples](../examples/environments.json) show native execution reserving `host-port:8000`, Docker using an internal port, and an AWS test resource. Valid JSON does not prove these environments can run: missing images or adapters still block setup. The Redis image demonstrates port isolation and contains no coding-agent toolchain.

Trusted host code registers resource adapters with `EnvironmentManager.register_resource(name, provider)`. Each adapter implements `inspect`, `prepare`, `cleanup`, and `required_leases`. For uncertain cleanup, `reconcile_cleanup` may return `completed`, `not-applied`, or `unknown`; absent or unknown results block retries. Adapters must verify ownership before removal, including after incomplete preparation.

AWS resources need a separately registered adapter. The framework does not create accounts, IAM policies, credentials, or stacks. The example's `aws-account:dedicated-test` reservation prevents overlapping account-wide operations; the adapter must handle account access, stack creation, and cleanup. The CLI has no resource-registration flag.

## Recover interrupted work

The controller records resource identity before preparation and checks ownership before cleanup. Check/review records and signing keys remain outside worker mounts. Uncertain preparation or cleanup retains its reservation.

Read `status`, then use `resume TASK --attempt EXACT_ID` to recover known resources. Unknown effects or ownership failures require operator investigation. There is no automatic fallback to native execution or blind cleanup retry.

## Docker smoke test

On 2026-10-10, Docker 29.4.0 ran two temporary `redis:8.6.5-alpine` containers pinned to `sha256:b12fbdf40b8da199f90f7610ea0b181eae21d1ad76c20ef30a60ec3e4ff0dfd4`. Each used a separate clone, network `none`, 64 MB, 0.25 CPU, and internal port 8000. Both returned `PONG` concurrently; framework cleanup succeeded. No host port was published or unrelated container changed.

This verified that setup and cleanup only. It did not test a live coding agent, model authentication, GitHub, or AWS, and granted no unattended permissions. Other images and adapters need their own checks.
