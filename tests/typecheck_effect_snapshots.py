"""Static consumer contracts checked by mypy; these functions are not executed."""

from typing import Any, assert_type

from rapid_ship.storage import EffectSnapshot, EffectStatus, Store


def effect_snapshots(store: Store) -> None:
    assert_type(store.begin_effect("effect", "create_pr", {}), EffectSnapshot)
    assert_type(store.get_effect("effect"), EffectSnapshot)

    effect = store.get_effect("effect")
    assert_type(effect["key"], str)
    assert_type(effect["kind"], str)
    assert_type(effect["payload"], dict[str, Any])
    assert_type(effect["status"], EffectStatus)
    assert_type(effect["result"], dict[str, Any] | None)
    assert_type(effect["note"], str)
    assert_type(effect["created_at"], float)
    assert_type(effect["updated_at"], float)
