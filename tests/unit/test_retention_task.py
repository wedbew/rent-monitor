from rm_worker.app import app
from rm_worker.tasks import retention  # noqa: F401  (registers the task)


def test_retention_sweep_is_registered_as_a_nightly_periodic_task() -> None:
    assert "retention_sweep" in app.tasks
    entries = [p for p in app.periodic_registry.periodic_tasks.values() if p.task.name == "retention_sweep"]
    assert len(entries) == 1
    assert entries[0].cron == "17 3 * * *"
    assert entries[0].task.queue == "ops"
