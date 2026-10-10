# Composable environments

Each `EnvironmentSpec` names three independent choices: source workspace, execution provider, and test-resource adapters. Declaring a choice is not evidence that it is available or compatible. Technical inspection can permit a supervised compatibility trial; `verified` alone never grants autonomy.

## Provider support

| Choice | Implemented behavior and limits |
| --- | --- |
| Independent clone | Separate Git metadata and disposable source tree. Used for nonnative execution. |
| Worktree | Source isolation with shared Git metadata; currently native execution only. Does not isolate credentials, processes, ports, or host files. |
| Native | Requires `allow_native: true` and `private_network: false`. Process group timeout/cancellation and a clean HOME/environment reduce accidental inheritance; host filesystem access remains available. No unattended grants. |
| Docker | Explicit image and reachable Docker CLI/daemon required. Managed container, resource limits, dropped capabilities, no-new-privileges, PID limit, workspace mount, and owned cleanup. `private_network: true` uses network `none`; false uses bridge networking. No host-port publication is configured. |
| Docker Sandboxes (`sbx`) | Shell adapter exists, but blocks unless CLI, disabled SSH forwarding, absent GitHub credential bindings, configuration/CLI compatibility, and requested private networking are explicitly verified. The current host has no verified installation/configuration. |
| OpenHands | Contract value only; inspection always blocks because no compatible execution adapter is configured. |

Choose and pin the container image through project setup. A tag is accepted as configuration, but a reproducible approved recipe should use an immutable digest. Include the exact agent CLI, Git, runtime, check tools, and a separately configured model authentication backend. The framework does not install them in a worker automatically or inherit host model login state. Network-none Docker cannot reach an ordinary remote inference service; network-capable configurations require their own compatibility and authority review.

Docker's observed allocation was 4,180,443,136 bytes on this host; it is adjustable. Project defaults are 4096 MB, 4 CPUs, and two concurrent tasks. The scheduler admits work against configured budgets and exclusive leases. It does not interpret those defaults as a universal two-agent or 4 GB ceiling; allow capacity for simultaneous worker/check/reviewer environments when setting actual provider limits.

## Ports and shared resources

Separate namespaces can use the same fixed **internal** port concurrently. A fixed **host** port or a global installation requires a declared exclusive lease. The framework does not infer port requirements from commands or publish Docker ports from `EnvironmentSpec`.

[Example environment contracts](../examples/environments.json) include native execution with the `host-port:8000` exclusive lease, a Docker internal-port namespace, and a declared AWS adapter. The JSON validates as contracts; provider inspection can still block unavailable images, unregistered resources, or unsatisfied capabilities. The Redis image illustrates provider composition only and contains no coding-agent toolchain. Internal port 8000 is a service convention in the example, not a port field on the model.

`EnvironmentManager.register_resource(name, provider)` registers trusted `ResourceProvider` integrations with `inspect`, `prepare`, `cleanup`, and `required_leases`. An adapter needing a host/global resource must require the matching lease. For uncertain cleanup, an optional `reconcile_cleanup` returns `completed`, `not-applied`, or `unknown`; absent/unknown reconciliation blocks retries. Adapters must verify ownership even when preparation produced an uncertain result.

AWS account/stack names in `test_resources` only identify explicitly registered adapters. There is no bundled AWS account creation, IAM policy, authentication, stack provisioning, or account lifecycle implementation. The example's `aws-test-stack` adapter must be supplied by trusted host wiring; the CLI has no resource-registration flag. Its `aws-account:dedicated-test` lease serializes account-wide operations without embedding an account number or credentials. Account lifecycle and ephemeral stack cleanup remain distinct responsibilities of that adapter.

## Ownership and recovery

Managed workspaces have durable ownership markers and provider identities. Preparation records identity before effects; cancellation/timeout stops execution, and cleanup checks ownership before removing resources. Artifacts and receipt keys stay in controller state outside worker mounts. If a process dies during preparation or cleanup, the controller retains uncertain state. `status`, then `resume TASK --attempt EXACT_ID`, can recover known owned handles; unidentified or uncertain effects require operator reconciliation. No fallback to native or retry of an unknown cleanup is automatic.

## Observed compatibility evidence

On 2026-10-10, a real provider smoke check used Docker 29.4.0 and two temporary `redis:8.6.5-alpine` containers pinned to `sha256:b12fbdf40b8da199f90f7610ea0b181eae21d1ad76c20ef30a60ec3e4ff0dfd4`. Each had an independent clone workspace, network `none`, a 64 MB/0.25 CPU limit, and an internal service on port 8000. Both returned `PONG` concurrently and framework cleanup succeeded. No host port was published or unrelated container modified.

That evidence verifies this provider composition and cleanup smoke only. It includes no live coding-agent/model trial, GitHub operation, AWS provision, human sign-off, or autonomy grant (`human_signoff: false`, `autonomy_granted: false`). It does not prove another image, CLI authentication path, sandbox version, or cloud adapter is compatible.
