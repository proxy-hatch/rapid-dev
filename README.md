# rapid-dev

Build with coding agents, measure their work, and keep control of delivery.

Bring an approved design. **rapid-dev** helps you split it into small tasks, run agents in separate environments, check their work, and review changes through GitHub. Projects can use any programming language.

## From design to delivery

1. **Set up** your tools, agents, environments, and checks through a short interview.
2. **Slice** the work into small tasks with clear ownership.
3. **Trial** a few changes and review the results yourself.
4. **Harden** repeated corrections into checks.
5. **Run** independent tasks in parallel as quality measurements support it.

Start with one task at a time. Add agents when the results justify it.

## Try the preview

The implementation is in [draft PR #1](https://github.com/proxy-hatch/rapid-dev/pull/1). It includes the `devctl` CLI, Docker environments, Codex/Claude adapters, checks, review, recovery, and quality metrics. Unattended delivery is disabled pending live trials and a connected approval service.

Requires Python 3.12+, Git, and [uv](https://docs.astral.sh/uv/) on a POSIX host:

```sh
git clone --branch codex/bootstrap-framework https://github.com/proxy-hatch/rapid-dev.git
cd rapid-dev
uv sync --locked
uv run devctl --help
```

Continue with [project setup](https://github.com/proxy-hatch/rapid-dev/blob/codex/bootstrap-framework/docs/usage.md), [quality metrics](https://github.com/proxy-hatch/rapid-dev/blob/codex/bootstrap-framework/docs/metrics.md), or [environment support](https://github.com/proxy-hatch/rapid-dev/blob/codex/bootstrap-framework/docs/environments.md).

Want to help? Try it on a small project, share what gets in your way, or open a focused PR. Keep the code, docs, and conversations simple.
