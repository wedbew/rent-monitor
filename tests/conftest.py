"""Test-session setup shared by every test."""

import os

# Docker Desktop on macOS exposes its socket under ~/.docker/run, which the Testcontainers reaper container cannot
# mount ("operation not supported"). The canonical path works there and is the default on Linux, so use it everywhere.
os.environ.setdefault("TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE", "/var/run/docker.sock")
