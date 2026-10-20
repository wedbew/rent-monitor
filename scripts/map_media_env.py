"""Fill empty MEDIA_* settings in the private .env from the existing verified R2 connection (RM-453).

Run: uv run python scripts/map_media_env.py [--env-file .env]
Maps CLOUDFLARE_S3_API -> MEDIA_S3_ENDPOINT, R2_ACCESS_KEY_ID/R2_SECRET_ACCESS_KEY -> MEDIA_ACCESS_KEY_ID/
MEDIA_SECRET_ACCESS_KEY and sets MEDIA_BUCKET=rent-monitor (owner decision 2026-10-21). Never overwrites a
non-empty MEDIA_* value and never prints a value: only setting names and what happened to them.
"""

import argparse
import sys
from pathlib import Path

from dotenv import dotenv_values

MAPPING = {
    "MEDIA_S3_ENDPOINT": "CLOUDFLARE_S3_API",
    "MEDIA_ACCESS_KEY_ID": "R2_ACCESS_KEY_ID",
    "MEDIA_SECRET_ACCESS_KEY": "R2_SECRET_ACCESS_KEY",
}
BUCKET = "rent-monitor"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=".env")
    path = Path(parser.parse_args().env_file)
    values = {k: v for k, v in dotenv_values(path, interpolate=False).items() if v}
    additions: list[str] = []
    for target, source in {**MAPPING, "MEDIA_BUCKET": ""}.items():
        if values.get(target):
            print(f"kept     {target} (already set)")
            continue
        value = BUCKET if target == "MEDIA_BUCKET" else values.get(source, "")
        if not value:
            print(f"missing  {target}: source {source} is empty or absent")
            continue
        additions.append(f"{target}={value}")
        print(f"mapped   {target}" + (f" from {source}" if source else ""))
    if additions:
        text = path.read_text() if path.exists() else ""
        # An empty `MEDIA_X=` line may already exist; the later assignment wins in dotenv, so append.
        path.write_text(
            text + ("" if text.endswith("\n") or not text else "\n") + "\n".join(additions) + "\n"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
