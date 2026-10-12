# Configuration examples

- [task-contract.json](task-contract.json) shows a task input; its base commit placeholder must be replaced before use.
- [environments.json](environments.json) contrasts native, isolated Docker, and declared external resource configurations.
- [models.py](../rapid_ship/models.py) defines accepted fields and validation; [test_models.py](../tests/test_models.py) exercises them.

Keep examples consistent with the schema and the linked [task](../docs/task-slicing.md) or [environment](../docs/environments.md) guide.
Keep qualification fields false until actual evidence establishes readiness; example configuration is not qualification evidence.
Use explicit placeholders where users must supply project-specific values.
When changing schema-related examples, run `uv run pytest tests/test_models.py` from the repository root and check the example JSON parses.
