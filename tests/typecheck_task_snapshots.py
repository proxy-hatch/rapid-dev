"""Static consumer contracts checked by mypy; these functions are not executed."""

from typing import Any, assert_type

from rapid_ship.execution.controller import Controller
from rapid_ship.models import TaskSpec
from rapid_ship.storage import Store, TaskSnapshot, TaskState


def task_snapshots(store: Store, controller: Controller, specs: list[TaskSpec]) -> None:
    assert_type(store.get_task("task"), TaskSnapshot)
    assert_type(store.tasks(), list[TaskSnapshot])
    assert_type(controller.run(specs), list[TaskSnapshot])

    task = store.get_task("task")
    assert_type(task["id"], str)
    assert_type(task["spec"], dict[str, Any])
    assert_type(task["state"], TaskState)
    assert_type(task["attempt_id"], str | None)
    assert_type(task["owner"], str | None)
    assert_type(task["lease_expires_at"], float | None)
    assert_type(task["generation"], int)
    assert_type(task["note"], str)
    assert_type(task["reconciliation_required"], bool)
