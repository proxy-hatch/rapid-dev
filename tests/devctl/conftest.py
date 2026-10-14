"""Import this repository's vendored devctl.

`rapid-ship status --strict` keeps that copy equal to the templates.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "devctl"))
