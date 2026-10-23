# scripts/

- `check_agent_docs.py` — pre-commit hook. Fails if a folder with tracked files lacks `AGENTS.md`, or the root lacks `AGENTS.md`/`ARCHITECTURE.md`/`CONTEXT.md`. Warns (exit 0) when files change without their folder's `AGENTS.md`.
