![rapid-ship — Ship more. Supervise less.](asset/public/banner.jpeg)

[![devctl check](https://github.com/proxy-hatch/rapid-ship/actions/workflows/devctl-check.yml/badge.svg?branch=main)](https://github.com/proxy-hatch/rapid-ship/actions/workflows/devctl-check.yml)

**Hand more of your delivery to coding agents, and keep the evidence that the work is right.**

rapid-ship does for a team of coding agents what senior engineers do for a team of people: it helps define the architecture, breaks delivery into tasks, and sets and holds the code-quality bar. The Harness you work in, such as Claude Code, Codex CLI or Antigravity CLI, runs the agents.

rapid-ship installs a Kit into your repository: a project CLI called devctl, an AGENTS.md tree, guardrail settings, a CI workflow and a set of skills. GitHub decides what merges. Tasks live in whichever issue tracker your Harness can reach. You choose the Mode. In Walk you approve every agent PR. In Flight the Lead, your lead agent, merges a change itself once its checks and review pass. It still brings you every change to the Protected set, such as CI, guardrails, agent instructions and settings, and any other kind of change you name. Flight lasts until you change the Mode.

## Status

rapid-ship is being rebuilt. [Spec 1](docs/superpowers/specs/2026-10-14-kit-and-setup-design.md) is built in six plans, and plans 1 to 3 work today: `rapid-ship init` vendors the Kit into a repository, `status` compares the repository with the Kit, `sync` proposes Kit updates as a PR, and `./devctl check` runs the checks in the pre-commit hook and in CI. No release is tagged yet; [Architecture](ARCHITECTURE.md) says how to run `rapid-ship` from a checkout. Plans 4 to 6 add `devctl doctor`, the optional Agent identity, Kit standards, the Harness guardrails and the setup skills. [Spec 2](docs/superpowers/specs/2026-10-16-delivery-skills-design.md) adds the delivery skills, and [Spec 3](docs/superpowers/specs/2026-10-16-metrics-and-gardening-design.md) the metrics and gardening.

*Dog-fooding:* this repository is built with its own Kit, and tracks its own tasks in Linear.

The earlier version, a local controller also named devctl, was removed on 2026-10-14. Its code is kept at the git tag [`archive/controller-2026-10`](https://github.com/proxy-hatch/rapid-ship/tree/archive/controller-2026-10), and its guides remain on this site, marked historical.

## Read more

- [rapid-ship design](docs/superpowers/specs/2026-10-14-rapid-ship-design.md): the problem, where rapid-ship stops and your Harness takes over, and how the code-quality bar is held.
- [Spec 1: Kit and Setup](docs/superpowers/specs/2026-10-14-kit-and-setup-design.md): what is built first, in [six plans](docs/superpowers/plans/2026-10-14-kit-and-setup.md).
- [Architecture](ARCHITECTURE.md): what this repository holds today and how to develop it.

## Credits

Our engineering workflows adapt [Matt Pocock's skills](https://github.com/mattpocock/skills/), with [Ponytail](https://github.com/DietrichGebert/ponytail) by Dietrich Gebert. Thank you for sharing them. [Skill sources and credits](docs/credits.md).
