# Repository maintenance scripts

- [check.py](check.py) runs the Python/repository CI suite, including navigation, static checks, tests and installation/build smoke checks. It tests current source in a temporary copy and leaves installed controllers unchanged.
- [check_repository.py](check_repository.py) validates local Markdown link destinations in maintained `AGENTS.md` files and relative skill aliases. Git excludes ignored state; new untracked guides count. Remote URLs and heading anchors are not checked.
- [build_controller.py](build_controller.py) builds a wheel and installs the checkout's `.controller` environment.
- [smoke_controller.py](smoke_controller.py) exercises that installed wheel and a temporary generated project without provider access.
- [smoke_distribution.py](smoke_distribution.py) extracts the built source archive into a temporary directory and reuses the installer and controller smoke there.
- The repository [devctl](../devctl) wrapper invokes setup; generated project wrappers come from [templates](../rapid_ship/templates/).

Preserve installer locking, rollback, symlink rejection, and installation at the final path; virtualenv entry points contain absolute paths.
Replacing an existing installation requires the installer's explicit rebuild option and stopped controller sessions.
Keep the smoke script's import check: it must exercise the installed package, not the source checkout.

For installation or wrapper changes, run `uv run pytest tests/test_controller_setup.py tests/test_project_wrapper.py` from the repository root.
For copied skill changes, also run `uv run pytest tests/test_skill_discovery.py`.
For validation changes, run `uv run pytest tests/test_check.py tests/test_repository_navigation.py`.
The shared validation sequence is defined in [check.py](check.py); [CI](../.github/workflows/ci.yml) calls it for each supported Python version.
The mypy stage uses the file list in [pyproject.toml](../pyproject.toml), including static consumer contracts. Keep this list shared with `uv run mypy`.
Run `uv run python scripts/check.py` for the full Python/repository suite. The website retains its separate `npm --prefix website run build` check.
After `uv build`, run `uv run python scripts/smoke_distribution.py` to check source-archive installation without replacing a checkout's controller.
