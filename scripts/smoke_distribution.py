"""Build and exercise an installed controller from the source distribution."""

import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    archives = list((root / "dist").glob("rapid_ship-*.tar.gz"))
    if len(archives) != 1:
        raise ValueError("Expected one rapid-ship source archive; run uv build first")
    with tempfile.TemporaryDirectory(prefix="rapid-ship-distribution-") as temporary:
        work = Path(temporary).resolve()
        with tarfile.open(archives[0]) as archive:
            archive.extractall(work, filter="data")
        sources = list(work.iterdir())
        if len(sources) != 1 or not sources[0].is_dir():
            raise ValueError("Expected one top-level directory in the source archive")
        source = sources[0]
        subprocess.run([sys.executable, str(source / "devctl"), "setup"], cwd=source, check=True)
        subprocess.run(
            [str(source / ".controller/bin/python"), str(source / "scripts/smoke_controller.py")],
            cwd=source,
            check=True,
        )
    print("Source archive, rebuilt wheel, and installed-controller smoke passed.")


if __name__ == "__main__":
    main()
