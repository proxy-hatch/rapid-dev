"""Real SQLite and disposable native workspaces with simulated agent responses."""

import threading

import pytest
from test_controller import FixtureRunner, task
from test_controller import project as project

from rapid_ship.execution.controller import Controller
from rapid_ship.execution.environments import EnvironmentBlocked, EnvironmentManager
from rapid_ship.storage import Store


class RecordingManager(EnvironmentManager):
    def __init__(self, directory):
        super().__init__(directory)
        self.prepared = []
        self.cleaned = []

    def prepare(self, *args, **kwargs):
        handle = super().prepare(*args, **kwargs)
        self.prepared.append(handle)
        return handle

    def cleanup(self, handle):
        super().cleanup(handle)
        self.cleaned.append(handle.id)


@pytest.fixture
def leased_project(project):
    root, config, base, state = project
    spec = config.environments[0].model_copy(update={"exclusive_resources": ["fixture:shared"]})
    return root, config.model_copy(update={"environments": [spec]}), base, state


@pytest.fixture
def heartbeats(monkeypatch):
    """Observe actual lease renewal and its thread without replacing SQLite behavior."""
    observed = threading.Event()
    threads = set()
    original = Store.heartbeat

    def heartbeat(store, *args, **kwargs):
        thread = threading.current_thread()
        try:
            return original(store, *args, **kwargs)
        finally:
            if thread.daemon:
                threads.add(thread)
                observed.set()

    monkeypatch.setattr(Store, "heartbeat", heartbeat)
    return observed, threads


def assert_no_evidence(state, events):
    assert not any(event["kind"] == "evidence" for event in events)
    assert not list((state / "receipts").glob("*.json"))


def assert_cleaned(manager):
    assert manager.prepared
    assert set(manager.cleaned) == {handle.id for handle in manager.prepared}
    assert all(not handle.workspace.exists() for handle in manager.prepared)
    assert manager.owned_handles() == []


def assert_heartbeat_stopped(heartbeats):
    observed, threads = heartbeats
    assert observed.is_set(), "The attempt must exercise its background lease renewal"
    assert threads
    assert all(not thread.is_alive() for thread in threads)


@pytest.mark.parametrize("cancellation_source", ["supervisor", "attempt-file"])
def test_cancellation_reaches_runner_cleans_workspace_and_releases_lease(
    leased_project, heartbeats, cancellation_source
):
    root, config, base, state = leased_project
    manager = RecordingManager(state / "workspaces")
    cancelled = threading.Event()

    class CancelledRunner:
        def run(self, execute, prompt, **kwargs):
            assert kwargs["role"] == "worker"
            if cancellation_source == "supervisor":
                controller.cancel_event.set()
            else:
                with Store(state / "workflow.db") as store:
                    attempt = store.get_task("a")["attempt_id"]
                (state / "cancel").mkdir()
                (state / "cancel" / attempt).touch()
            if kwargs["cancel_event"].wait(5):
                cancelled.set()
            raise EnvironmentBlocked("Simulated worker interrupted")

    controller = Controller(
        root,
        config,
        state,
        manager_factory=lambda directory: manager,
        runner_factory=lambda name, model: CancelledRunner(),
        lease_seconds=3,
    )
    rows = controller.run([task(base)])

    assert cancelled.is_set(), "Cancellation must reach the runner before it returns"
    assert rows[0]["state"] == "cancelled"
    assert rows[0]["note"] == "Cancellation requested"
    assert_cleaned(manager)
    with Store(state / "workflow.db") as store:
        assert store.connection.execute("SELECT count(*) FROM resources").fetchone()[0] == 0
        assert_no_evidence(state, store.events())
    assert_heartbeat_stopped(heartbeats)


def test_recovered_lease_cancels_runner_but_retains_reservations_for_reconciliation(
    leased_project, heartbeats
):
    root, config, base, state = leased_project
    manager = RecordingManager(state / "workspaces")
    cancelled = threading.Event()

    class ExpiredRunner:
        def run(self, execute, prompt, **kwargs):
            assert kwargs["role"] == "worker"
            with Store(state / "workflow.db") as store:
                expiry = store.get_task("a")["lease_expires_at"]
            # A later supervisor recovers the expired attempt through the public store API.
            with Store(state / "workflow.db", clock=lambda: expiry + 1) as store:
                assert store.recover_expired() == ["a"]
            if kwargs["cancel_event"].wait(5):
                cancelled.set()
            raise EnvironmentBlocked("Simulated worker lost ownership")

    rows = Controller(
        root,
        config,
        state,
        manager_factory=lambda directory: manager,
        runner_factory=lambda name, model: ExpiredRunner(),
        lease_seconds=3,
    ).run([task(base)])

    assert cancelled.is_set(), "A lost lease must cancel the running agent"
    assert rows[0]["state"] == "blocked"
    assert rows[0]["reconciliation_required"]
    assert "lease expired" in rows[0]["note"]
    assert_cleaned(manager)
    with Store(state / "workflow.db") as store:
        lease = store.connection.execute("SELECT * FROM resources").fetchone()
        assert lease["attempt_id"] == rows[0]["attempt_id"]
        assert lease["owner"] == rows[0]["owner"]
        assert not any(event["kind"] == "task_transition" for event in store.events())
        assert_no_evidence(state, store.events())
    assert_heartbeat_stopped(heartbeats)


def test_cleanup_failure_after_approval_retains_lease_and_cleans_other_environments(
    leased_project,
):
    root, config, base, state = leased_project

    class UncertainCleanup(RecordingManager):
        def cleanup(self, handle):
            if handle.id == self.prepared[-1].id:
                raise EnvironmentBlocked("Simulated cleanup acknowledgement lost")
            super().cleanup(handle)

    manager = UncertainCleanup(state / "workspaces")
    rows = Controller(
        root,
        config,
        state,
        manager_factory=lambda directory: manager,
        runner_factory=lambda name, model: FixtureRunner(),
    ).run([task(base)])

    assert rows[0]["state"] == "reviewing"
    assert len(manager.prepared) == 3
    uncertain = manager.prepared[-1]
    assert set(manager.cleaned) == {handle.id for handle in manager.prepared[:-1]}
    assert all(not handle.workspace.exists() for handle in manager.prepared[:-1])
    assert uncertain.workspace.exists()
    assert [handle.id for handle in manager.owned_handles()] == [uncertain.id]
    with Store(state / "workflow.db") as store:
        assert store.connection.execute("SELECT count(*) FROM resources").fetchone()[0] == 1
        events = store.events()
        failures = [event["payload"] for event in events if event["kind"] == "cleanup_uncertain"]
        assert [failure["handle_id"] for failure in failures] == [uncertain.id]
        assert len([event for event in events if event["kind"] == "environment_cleaned"]) == 2
        assert_no_evidence(state, events)


def test_cancellation_during_cleanup_overrides_completed_approval(leased_project):
    root, config, base, state = leased_project

    class CancelDuringCleanup(RecordingManager):
        def cleanup(self, handle):
            controller.cancel_event.set()
            super().cleanup(handle)

    manager = CancelDuringCleanup(state / "workspaces")
    controller = Controller(
        root,
        config,
        state,
        manager_factory=lambda directory: manager,
        runner_factory=lambda name, model: FixtureRunner(),
    )
    rows = controller.run([task(base)])

    assert rows[0]["state"] == "cancelled"
    assert len(manager.prepared) == 3
    assert_cleaned(manager)
    with Store(state / "workflow.db") as store:
        assert store.connection.execute("SELECT count(*) FROM resources").fetchone()[0] == 0
        assert_no_evidence(state, store.events())


@pytest.mark.parametrize("failure", [None, "write", "fence"])
def test_heartbeat_stops_after_finalization_even_when_lease_renewal_fails(
    leased_project, heartbeats, monkeypatch, failure
):
    root, config, base, state = leased_project
    manager = RecordingManager(state / "workspaces")
    observed, _threads = heartbeats

    class WaitingRunner(FixtureRunner):
        def run(self, execute, prompt, **kwargs):
            if kwargs["role"] == "worker":
                assert observed.wait(5), "Background heartbeat did not run"
            return super().run(execute, prompt, **kwargs)

    if failure:
        heartbeat = Store.heartbeat

        def fail_finalization(store, *args, **kwargs):
            if not threading.current_thread().daemon:
                if failure == "write":
                    raise RuntimeError("Simulated final lease write failure")
                # Lose ownership at the final fence, before the background pulse sees it.
                expiry = store.get_task("a")["lease_expires_at"]
                with Store(state / "workflow.db", clock=lambda: expiry + 1) as recovered:
                    assert recovered.recover_expired() == ["a"]
            return heartbeat(store, *args, **kwargs)

        monkeypatch.setattr(Store, "heartbeat", fail_finalization)

    controller = Controller(
        root,
        config,
        state,
        manager_factory=lambda directory: manager,
        runner_factory=lambda name, model: WaitingRunner(),
        lease_seconds=3,
    )
    if failure == "write":
        with pytest.raises(RuntimeError, match="Simulated final lease write failure"):
            controller.run([task(base)])
    elif failure == "fence":
        with pytest.raises(ValueError, match="attempt ownership is stale, inactive or expired"):
            controller.run([task(base)])
    else:
        assert controller.run([task(base)])[0]["state"] == "approved"

    assert_cleaned(manager)
    assert_heartbeat_stopped(heartbeats)
    with Store(state / "workflow.db") as store:
        if failure:
            row = store.get_task("a")
            assert row["state"] == ("reviewing" if failure == "write" else "blocked")
            assert row["reconciliation_required"] == (failure == "fence")
            assert store.connection.execute("SELECT count(*) FROM resources").fetchone()[0] == 1
            assert_no_evidence(state, store.events())
        else:
            assert store.connection.execute("SELECT count(*) FROM resources").fetchone()[0] == 0
            assert len([event for event in store.events() if event["kind"] == "evidence"]) == 1
