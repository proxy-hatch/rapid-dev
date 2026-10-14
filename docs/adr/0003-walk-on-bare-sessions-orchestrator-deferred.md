---
status: accepted
---

# Walk runs on bare sessions; rapid-orchestrator is deferred

In Walk the owner starts and oversees Sessions by hand, and all state lives in Linear and GitHub. rapid-ship is therefore a Kit, skills and a devctl, with no daemon, container runtime or local database. rapid-orchestrator is deferred.

Flight is planned without an orchestrator process as well. The flow between gates may be driven by a model following a written procedure. Code and GitHub settings decide what merges, what may start, and when the project returns to Walk. The [Flight research note](../trials/2026-10-13-flight-without-orchestrator.md) lists the eight deterministic pieces this needs. Their design is settled when a project reaches Pre-flight. rapid-orchestrator returns only if those pieces prove insufficient; its context is kept in [the archive](../archive/orchestrator/README.md).

Deferring closes no option. A [survey](../trials/2026-10-13-orchestrator-landscape.md) found no existing orchestrator worth adopting, and a [trial](../trials/2026-10-13-login-carry.md) showed that one subscription sign-in per Provider can serve several containers.

## Considered options

- **Build rapid-orchestrator first**, as its own thin core on plain Docker. Rejected for now: weeks of work that Walk does not need, in an area where the Harnesses' own capabilities are advancing.
- **Adopt or fork an existing orchestrator.** Rejected: see the survey. The closest candidates run interactive terminal sessions, let the agent commit and push, or prefer API keys.
- **A workflow-script layer over Sessions.** Rejected: it would trail each Harness's own subagents and background sessions.

## Consequences

- Nothing exceeds five supervised Workers until a Flight execution path exists.
- In Walk, Sessions run on the owner's machine under the owner's sign-ins. Confinement is whatever the Harness provides.
- Pre-flight can report readiness but cannot promote a project until that path exists.
- Flight is a lease that a scheduled metrics job renews. If the job does not run, the lease expires and the project is back in Walk.
