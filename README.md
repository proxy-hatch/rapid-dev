![rapid-ship — Ship more. Supervise less.](asset/public/banner.jpeg)

[![devctl check](https://github.com/proxy-hatch/rapid-ship/actions/workflows/devctl-check.yml/badge.svg?branch=main)](https://github.com/proxy-hatch/rapid-ship/actions/workflows/devctl-check.yml)

**Hand more of your delivery to coding agents, and keep the evidence that the work is right.**

rapid-ship installs a Kit into your repository: a project CLI called devctl, an AGENTS.md tree, guardrail settings, a CI workflow and a set of skills. GitHub decides what merges and Linear holds the tasks. You start in Walk, where you approve every agent PR. Flight lets agents merge ordinary changes, and only while measured quality holds.

## Status

rapid-ship is being rebuilt, and nothing is usable yet: the package provides only `rapid-ship --version`. The earlier version, a local controller also named devctl, was removed on 2026-10-14. Its code is kept at the git tag [`archive/controller-2026-10`](https://github.com/proxy-hatch/rapid-ship/tree/archive/controller-2026-10), and its guides remain on this site, marked historical.

## Read more

- [rapid-ship design](docs/superpowers/specs/2026-10-14-rapid-ship-design.md): the problem, the path from Setup to Flight, and how trust is enforced.
- [Spec 1: Kit and Setup](docs/superpowers/specs/2026-10-14-kit-and-setup-design.md): what is built first, in [five plans](docs/superpowers/plans/2026-10-14-kit-and-setup.md).
- [Architecture](ARCHITECTURE.md): what this repository holds today and how to develop it.

## Credits

Our engineering workflows adapt [Matt Pocock's skills](https://github.com/mattpocock/skills/), with [Ponytail](https://github.com/DietrichGebert/ponytail) by Dietrich Gebert. Thank you for sharing them. [Skill sources and credits](docs/credits.md).
