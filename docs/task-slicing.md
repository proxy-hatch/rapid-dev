# From design to small tasks

> **Historical:** describes the controller removed on 2026-10-14. See the [rapid-ship design](superpowers/specs/2026-10-14-rapid-ship-design.md).

rapid-ship owns the translation from an approved design into epics, optional stories and executable tasks in Linear. Ideation stays outside the workflow. The installed skill guides planning today; `devctl decompose` validates and registers the resulting task JSON. It does not generate a plan or sync Linear automatically.

## What a worker gets

Assign one leaf task with one checkable outcome, normally one PR. Keep the code, its tests and necessary documentation together. A task is small enough when a reviewer can explain its purpose and verify it without waiting for a later task to make it correct. File counts, lines changed and one-function assignments are poor substitutes for that judgment.

Use this short assignment:

| Field | Content |
|---|---|
| Outcome | One observable behavior and its approved design reference |
| Scope | Owned files/modules, relevant interfaces and explicit exclusions |
| Dependencies | Required tasks and exact commits already in the selected base |
| Acceptance | Success, failure and relevant boundary cases |
| Execution | Harness/model, environment, named checks, time/retry budget |
| Delivery | One change with check results; stop for material unresolved design or required scope expansion |

Give the worker the relevant design sections and source context. Give the stronger reviewer the wider design, task plan, exact diff and verification results. Epics organize outcomes; stories are useful when an epic has distinct user journeys. Neither is a coding assignment.

## Plan and check coverage

Use the [engineering clarification skill](engineering-skills.md) first when the design leaves material implementation questions. Read existing answers before asking; do not question the project's purpose or motivation. Use `GLOSSARY.md` for useful shared terms and short ADRs for consequential decisions. Neither document is required when it adds no value. Development may reveal new unknowns; pause affected tasks and continue independent work.

1. Map each approved requirement to an epic and its tasks. Mark deferred work explicitly so it cannot disappear between planning and delivery.
2. Assign each shared interface to one task. Record dependencies where code or a decision is needed; do not serialize unrelated work merely because it shares an epic.
3. Have a project-aware reviewer check coverage, assumptions, task size, dependency order and overlapping ownership. A material unresolved design decision blocks affected tasks. Resolve routine implementation choices using project conventions; do not invent authentication, authorization, public interfaces or data semantics.
4. Save the reviewed plan and task JSON using the current schema. Keep epic/story links and requirement references in the plan and task descriptions. Planning does not register tasks.

Save unresolved decisions with the affected task IDs in the plan. Keep blocked tasks and their dependents out of the executable JSON. Add them only after the decision and plan review.

The planning reviewer reads the saved plan directly. The current controller review prompt supplies the design, task, diff, changed source and check results; it does not automatically include the wider task plan or select relevant unchanged source. Put essential interface and dependency context in the task description until that context selection is implemented.

Linear holds projects, optional milestones, parent/leaf issues and blocking relationships. One leaf issue normally produces one GitHub PR. Do not mirror tasks into GitHub Issues. An issue's closed state does not prove that its dependency commit is in another task's base. See [Linear integration](linear.md) for the proposed mapping and status ownership.

For example, an approved account-creation design might produce:

| Task | Includes | Depends on |
|---|---|---|
| Reject duplicate stored emails | Constraint, migration and persistence tests | — |
| Return the specified duplicate-email response | API mapping and request tests | Storage task |
| Display that response | Client behavior and component tests | API task |

Do not turn this into separate “write code” and “write its tests” PRs. Unrelated work can proceed alongside the chain.

## Choose how to execute

For supervised sessions, give the worker its reviewed task and leave it unregistered. The [Getting started walkthrough](getting-started.md#5-implement-with-the-worker) demonstrates this path.

For controller execution, first verify the configured environment. Then `./devctl decompose --tasks tasks.json` validates **and registers** tasks in controller state. It is not a read-only planning check. Follow the [readiness and registration steps](usage.md#run-through-devctl) before running it.

Registration has no design-decision gate. Supply only reviewed, ready tasks and every required dependency. Reuse unchanged specifications for tasks already registered. Removing a task from JSON does not cancel stored work.

## Independent PRs and stacks

Use independent PRs targeting the project branch by default. Integrate dependency commits before dispatching dependent tasks; `devctl resume` can explicitly update an inactive task's base. Current devctl does not manage stacks.

The [GitHub tutorial](https://docs.github.com/en/copilot/tutorials/stack-ai-generated-code-in-pull-requests) is useful when a task needs code still under review: each PR targets the preceding branch, keeping its diff focused. [Native stacks](https://docs.github.com/en/pull-requests/get-started/about-stacked-prs) require one repository and form a linear chain. A plan with multiple independent dependencies is not automatically one stack.

A future stack adapter must:

- Track layer order and exact head/base commits; serialize changes to shared stack branches.
- Fix the owning layer, rebase descendants and obtain fresh checks/review for changed commit bindings. Conflicts pause affected descendants.
- Authorize every lower layer included in a bottom-up merge. Merging a higher PR can also merge those below it.
- Persist the asynchronous operation ID and reconcile final PR state after interruption. Acceptance or queue admission is not a completed merge.

GitHub's [stack API](https://docs.github.com/en/pull-requests/reference/stacked-pull-requests-apis-and-webhooks) requires asynchronous merging; devctl's current broker uses the synchronous endpoint. Installing `gh-stack` cannot bridge that gap. Verify behavior in a compatibility trial before enabling unattended stack operations.
