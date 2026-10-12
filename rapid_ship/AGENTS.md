# rapid_ship controller package

This root-level directory is the importable Python package. [pyproject.toml](../pyproject.toml) defines wheel selection and the `devctl` entry point.

## Choose the owning area

| Change | Guide |
| --- | --- |
| Project initialization, interview, model discovery and readiness | [Project](project/AGENTS.md) |
| Task attempts, harnesses, environments and session guidance | [Execution](execution/AGENTS.md) |
| Evidence, authority, GitHub writes and qualification | [Trust](trust/AGENTS.md) |
| Installed agent workflows and references | [Skills](skills/AGENTS.md) |
| Generated project command wrapper | [Templates](templates/AGENTS.md) |

Shared files remain here because multiple areas use them:

- [cli.py](cli.py) dispatches commands; [__main__.py](__main__.py) and the installed `devctl` entry point call the same `main`.
- [models.py](models.py) owns shared validated contracts. Keep domain-specific contracts in their owning area.
- [storage.py](storage.py) owns SQLite state and task transitions; [process.py](process.py) owns bounded process execution and environment filtering.
- [logs.py](logs.py) reads diagnostic state. [metrics.py](metrics.py) and [github_metrics.py](github_metrics.py) handle measurements and collection.

## Place a change

Keep domain behavior in its owning area and command argument handling in `cli.py`. Import the implementation module directly; package `__init__.py` files are markers, not alternate interfaces.

These directories organize responsibilities; they are not isolated runtime services or mechanically enforced import layers. Shared contracts must remain usable without importing the CLI. Preserve read-only paths and existing dependency directions when moving code.

Resources stay under this package: `importlib.resources.files("rapid_ship")` is the installed-wheel lookup root. For moves, check dynamic imports, monkeypatch targets and subprocess command strings as well as ordinary imports. Run the root checks and the [installed-wheel smoke check](../scripts/AGENTS.md).
