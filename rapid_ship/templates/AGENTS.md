# Project wrapper template

[devctl](devctl) is copied into initialized projects and marked executable. The repository-root `devctl` bootstraps the framework controller; it is a different entry point.

Keep this template runnable before project dependencies are installed. Preserve argument forwarding, exit status, explicit controller selection, version checks and the local framework backlink.

For changes, run `uv run pytest tests/test_project_wrapper.py tests/test_configuration.py` from the repository root. Then run the installed-wheel smoke check to verify the packaged template produces a usable project wrapper.
