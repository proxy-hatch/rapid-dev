"""Exercise setup's installed wheel and a new project's wrapper without provider access."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import agentic_engineering

root = Path(__file__).resolve().parents[1]
assert Path(agentic_engineering.__file__).is_relative_to(Path(sys.prefix))
controller = root / ".controller/bin/devctl"
environment = {key: value for key, value in os.environ.items() if key != "DEVCTL_CONTROLLER"}
with tempfile.TemporaryDirectory(prefix="rapid-ship-smoke-") as temporary:
    project = Path(temporary).resolve()
    (project / "design.md").write_text("Approved: a command prints hello.\n")
    result = subprocess.run(
        [
            str(controller),
            "--project",
            str(project),
            "init",
            "--name",
            "hello",
            "--design",
            "design.md",
        ],
        env=environment,
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(result.stdout)["next_question"]["id"] == "repository"
    link = json.loads((project / ".devctl/local.json").read_text())
    assert link == {"framework_root": str(root), "controller": str(controller)}
    for surface in (".agents", ".claude"):
        assert (project / surface / "skills/rapid-ship/references/run.md").is_file()
        assert (project / surface / "skills/rapid-ship-improve/SKILL.md").is_file()
    for command, expected in ((["--version"], 0), (["doctor", "--json"], 2), (["logs"], 0)):
        result = subprocess.run(
            ["./devctl", *command], cwd=project, env=environment, text=True, capture_output=True
        )
        assert result.returncode == expected, result.stderr + result.stdout
    assert not (project / ".devctl/state/workflow.db").exists()
print("Installed wheel, local backlink, project wrapper and both skill registrations passed.")
