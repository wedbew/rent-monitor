"""Names of background tasks the API defers by name (the API never imports the worker)."""

SEND_MAGIC_LINK_TASK = "rm_worker.tasks.email.send_magic_link"
OPS_QUEUE = "ops"
