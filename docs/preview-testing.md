# Test the preview

Use `main` as the single preview entry point. Merged code is available for functional testing; it does not enable unattended delivery.

## Build and install

From the rapid-ship checkout:

```sh
uv sync --locked
uv run pytest -q
uv build
preview_dir=$(mktemp -d "${TMPDIR:-/tmp}/rapid-ship-preview.XXXXXX")
uv venv --python 3.13 "$preview_dir/controller"
uv pip install --python "$preview_dir/controller/bin/python" \
  dist/rapid_ship-0.1.0-py3-none-any.whl
export DEVCTL_CONTROLLER="$preview_dir/controller/bin/devctl"
"$DEVCTL_CONTROLLER" --version
```

This keeps the installed controller outside the project it will change. The temporary directory is yours to inspect and remove afterward.

## Try setup

```sh
mkdir "$preview_dir/project"
git -C "$preview_dir/project" init -q
printf '# Approved design\n\nBuild a command that prints hello.\n' > "$preview_dir/project/design.md"
cd "$preview_dir/project"
"$DEVCTL_CONTROLLER" init --name hello --design design.md
./devctl interview
./devctl doctor --json
./devctl status
./devctl metrics
```

The interview should return one unanswered setup question. Answer through `./devctl interview --answer ID --value JSON`. Do not invent credentials or provider support to make the doctor pass. Until setup is complete, doctor exits `2` and lists blockers; that is expected. An empty metrics report must show missing evidence rather than perfect quality.

Inspect `.devctl/project.json`, `.devctl/AGENTS.md`, `./devctl`, and both skills under `.agents/skills/`. Running the same `init` command again should preserve existing settings and edited skills while adding any missing bundled skill.

For a real task, continue with [project setup](usage.md). Expect live execution to require an actual harness, model access and verified environment. AstraBox integration and automatic model/account handoff are not wired into the preview. `trial`, `harden`, PR mutation and release commands deliberately remain blocked without trusted delivery authorization.

## Report friction

In the test project, ask your coding agent:

> Use rapid-ship-improve: setup made me repeat an environment choice. Reproduce it and submit a small framework PR if the problem is shared across projects.

The skill should distinguish a project setting from a framework bug, check for existing work, and use a separate framework checkout. A diagnosis without a published PR must say so. It must not change the running controller, weaken checks just to pass, or upload raw project logs.
