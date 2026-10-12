# Controller installation scripts

- [build_controller.py](build_controller.py) builds a wheel and installs the checkout's `.controller` environment.
- [smoke_controller.py](smoke_controller.py) exercises that installed wheel and a temporary generated project without provider access.
- [smoke_distribution.py](smoke_distribution.py) extracts the built source archive into a temporary directory and reuses the installer and controller smoke there.
- The repository [devctl](../devctl) wrapper invokes setup; generated project wrappers come from [templates](../src/agentic_engineering/templates/).

Preserve installer locking, rollback, symlink rejection, and installation at the final path; virtualenv entry points contain absolute paths.
Replacing an existing installation requires the installer's explicit rebuild option and stopped controller sessions.
Keep the smoke script's import check: it must exercise the installed package, not the source checkout.

For installation or wrapper changes, run `uv run pytest tests/test_controller_setup.py tests/test_project_wrapper.py` from the repository root.
For copied skill changes, also run `uv run pytest tests/test_skill_discovery.py`.
The full installation smoke sequence is defined in [CI](../.github/workflows/ci.yml).
After `uv build`, run `uv run python scripts/smoke_distribution.py` to check source-archive installation without replacing a checkout's controller.
