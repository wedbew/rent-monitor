"""Write the API's OpenAPI schema to `docs/openapi.json`: sorted keys, no secrets, no database needed.

Run `uv run python scripts/gen_openapi.py` after adding or changing a route. A test fails when the committed
file and the app disagree, so the frontend's generated client cannot drift from the backend (Phase 2).
"""

import json
import sys
from pathlib import Path
from typing import Any

from rm_api.app import create_app
from rm_core.settings import Settings

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "docs" / "openapi.json"


def build_schema() -> dict[str, Any]:
    """The schema from a throwaway app; `Settings` is explicit so the real environment never leaks in."""
    app = create_app(Settings(app_env="test", database_url="", procrastinate_dsn="", sentry_dsn=""))
    return app.openapi()


def render(schema: dict[str, Any]) -> str:
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> int:
    SCHEMA_PATH.write_text(render(build_schema()), encoding="utf-8")
    print(f"wrote {SCHEMA_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
