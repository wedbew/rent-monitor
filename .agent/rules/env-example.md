# Rule: keep `.env.example` in sync with the code

`.env.example` is committed and holds **names, safe local defaults and a comment saying where each value comes from**. It never
holds a real secret. Agents may read and edit it (the real `.env`, `.env.local`, `.env.production`... stay unreadable).

- Add or rename a setting in `rm_core/settings.py` (or read an env var anywhere) → update `.env.example` in the same PR, plus
  blueprint §4.2 and README *How to run* if the name is mandatory (`rules/architecture.md`).
- Every line: `NAME=default-or-empty  # where to get it`. Values only we can supply are marked `needs you` and also get a row
  in `docs/BLOCKERS.md` (`rules/blockers.md`).
- Defaults must work for local development (Docker Postgres, no external accounts), so the app starts with an untouched copy.
- Never paste a real key, DSN, token or password, not even as an example. Use empty values or obvious placeholders.
- Do not read `.env`; ask the owner to confirm a value exists if you must know.
