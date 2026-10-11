"""The Procrastinate application object, used as `procrastinate --app=rm_worker.app.app`.

Tasks are registered by later tickets (audit, batch, ops queues). Importing this module opens no connection.
"""

import procrastinate
from rm_core.settings import get_settings

app = procrastinate.App(
    connector=procrastinate.PsycopgConnector(conninfo=get_settings().procrastinate_dsn),
    import_paths=["rm_worker.tasks.retention"],
)
