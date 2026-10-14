"""Install the wheel built from the source archive and check the rapid-ship entry point."""

import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path


def built(root: Path, pattern: str) -> Path:
    matches = list((root / "dist").glob(pattern))
    if len(matches) != 1:
        raise ValueError(f"Expected one dist/{pattern}; run uv build --clear first")
    return matches[0]


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    built(root, "rapid_ship-*.tar.gz")
    # uv build makes the wheel from the source archive, so a file the archive omits
    # is missing from this installation too.
    wheel = built(root, "rapid_ship-*.whl")
    with tempfile.TemporaryDirectory(prefix="rapid-ship-distribution-") as temporary:
        environment = Path(temporary).resolve() / "venv"
        python = environment / "bin/python"
        subprocess.run(
            ["uv", "venv", "--quiet", "--python", sys.executable, str(environment)], check=True
        )
        subprocess.run(
            ["uv", "pip", "install", "--quiet", "--python", str(python), str(wheel)], check=True
        )
        result = subprocess.run(
            [str(environment / "bin/rapid-ship"), "--version"],
            cwd=temporary,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
    if result.stdout != f"rapid-ship {version}\n":
        raise ValueError(f"Installed rapid-ship reported {result.stdout!r}, expected {version}")
    print(f"Installed wheel from the source archive reports rapid-ship {version}.")


if __name__ == "__main__":
    main()
