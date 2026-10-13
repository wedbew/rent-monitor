"""Stand-in engine functions for the child-process tests: they hang, crash, balloon or lie on purpose.

Imported by the engine child through PYTHONPATH (`ChildEngine(target="engine_targets:hang")`).
Never imported by production code.
"""

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from deal_analyzer import FractionalOwnershipError


def _record_pid() -> None:
    pid_file = os.environ.get("ENGINE_PID_FILE")
    if pid_file:
        with Path(pid_file).open("a") as f:
            f.write(f"{os.getpid()}\n")


def hang(*_: Any, **__: Any) -> None:
    _record_pid()
    time.sleep(3600)


def hang_with_grandchild(*_: Any, **__: Any) -> None:
    _record_pid()
    grandchild = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(3600)"])
    with Path(os.environ["ENGINE_PID_FILE"]).open("a") as f:
        f.write(f"{grandchild.pid}\n")
    time.sleep(3600)


def balloon(*_: Any, **__: Any) -> None:
    hog = bytearray(8 * 1024 * 1024 * 1024)
    sys.stdout.write(str(len(hog)))


def crash(*_: Any, **__: Any) -> None:
    os._exit(9)


def garbage(*_: Any, **__: Any) -> None:
    sys.stdout.write("not json")
    sys.stdout.flush()
    os._exit(0)


def fractional(*_: Any, **__: Any) -> None:
    raise FractionalOwnershipError("ID1", ("udział",))
