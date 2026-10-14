"""The Procrastinate application object, used as `procrastinate --app=rm_worker.app.app`.

Tasks live in rm_worker.tasks.* (audit, batch, ops queues). Importing this module opens no connection.
"""

import procrastinate
from rm_core.observability import init_sentry
from rm_core.settings import get_settings

# Error tracking for the worker process too (off while SENTRY_DSN is empty; events are scrubbed, RM-149).
init_sentry(get_settings())

app = procrastinate.App(
    connector=procrastinate.PsycopgConnector(conninfo=get_settings().procrastinate_dsn),
    import_paths=[
        "rm_worker.tasks.retention",
        "rm_worker.tasks.ai_budget",
        "rm_worker.tasks.maintenance",
        "rm_worker.tasks.email",
        "rm_worker.tasks.audit",
        "rm_worker.tasks.reconcile",
        "rm_worker.tasks.billing",
        "rm_worker.tasks.batch",
    ],
)
