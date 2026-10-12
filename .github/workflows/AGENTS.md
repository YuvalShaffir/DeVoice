# .github/workflows/

- `ci.yml` — on push/PR to `main`: `uv sync --dev`, pre-commit hooks, tests.
- `workflow.yml` — "Build": runs tests with coverage, then SonarQube scan (reads `coverage/lcov.info`).
