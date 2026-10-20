"""Grant or revoke an explicit account entitlement on an existing account (RM-438).

    docker compose -f deploy/compose.yml exec -T api python scripts/grant_entitlement.py grant \
        --email e2e-marcin@example.test --note "designated test account"
    ... revoke --email e2e-marcin@example.test

Runs inside the api container with the deployed settings. It never creates an account, never touches
credit, sessions or data, and repeating it changes nothing. Output: one JSON line with the outcome.

GDPR[personal-data]: takes an e-mail address on the command line; prints only the outcome.
"""

import argparse
import asyncio
import json
import sys

from rm_core.db.session import make_engine, make_sessionmaker
from rm_core.entitlement_grants import grant, revoke
from rm_core.settings import get_settings


async def main(args: argparse.Namespace) -> int:
    engine = make_engine(get_settings())
    try:
        async with make_sessionmaker(engine)() as session:
            if args.action == "grant":
                result = await grant(session, args.email, note=args.note)
            else:
                result = await revoke(session, args.email)
    finally:
        await engine.dispose()
    print(json.dumps({"outcome": result.outcome, "kind": "unlimited_reports"}))
    return 1 if result.outcome == "no_such_account" else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["grant", "revoke"])
    parser.add_argument("--email", required=True)
    parser.add_argument("--note", default="", help="why (no personal data)")
    sys.exit(asyncio.run(main(parser.parse_args())))
