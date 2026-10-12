"""Test-session setup shared by every test."""

import os
from collections.abc import Callable

import pytest
from google_helpers import GoogleKeys, build_keys, sign_token
from rm_core.settings import Settings

# Docker Desktop on macOS exposes its socket under ~/.docker/run, which the Testcontainers reaper container
# cannot mount ("operation not supported"). The canonical path works there and is the Linux default.
os.environ.setdefault("TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE", "/var/run/docker.sock")

# `Settings` reads `.env` from the working directory; the owner's real file holds live keys (Resend,
# Stripe...).
# Tests must be hermetic and must never be able to print those values (a failing assertion shows reprs), so
# the env
# file is switched off here, at import, before any module (e.g. `rm_worker.app`) can load it. Tests that
# need a value
# pass it explicitly or use `monkeypatch.setenv`.
Settings.model_config["env_file"] = None


@pytest.fixture(scope="session")
def google_keys() -> GoogleKeys:
    return build_keys()


@pytest.fixture(scope="session")
def make_google_token(google_keys: GoogleKeys) -> Callable[..., str]:
    def make(**kwargs: object) -> str:
        return sign_token(google_keys, **kwargs)  # type: ignore[arg-type]

    return make
