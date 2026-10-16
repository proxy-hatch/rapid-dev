# rapid_ship package

This root-level directory is the importable `rapid_ship` package behind the `rapid-ship` command. [pyproject.toml](../pyproject.toml) defines wheel selection and the `rapid-ship` entry point. The [plan index](../docs/superpowers/plans/2026-10-14-kit-and-setup.md) fixes the modules that later plans add here.

- [cli.py](cli.py) parses arguments. It supports only `--version`; plans 2 and 4 add the commands. [__main__.py](__main__.py) and the entry point call the same `main`.
- [files.py](files.py) atomically replaces a file. Callers own serialization and path validation. It is kept from the removed controller for the Kit writers and has no caller yet.
- [process.py](process.py) runs a bounded subprocess under process-group supervision. It has no caller yet; plan 3 moves it into devctl with the fixes that Spec 1's section 2 names.
- [skills](skills/AGENTS.md) holds the engineering skill used while working on this repository.

Import modules directly; `__init__.py` is a marker, not an alternate interface. Keep resources under this package: `importlib.resources.files("rapid_ship")` is the lookup root in an installed wheel. After packaging changes, run the root checks and the [distribution smoke](../scripts/AGENTS.md).
