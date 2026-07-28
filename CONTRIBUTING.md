# Contributing to OpenSource AI Workspace

Thank you for considering a contribution. Documentation improvements, tests, accessibility fixes, language improvements and carefully scoped code changes are welcome.

## Before you begin

- Read [AGENTS.md](AGENTS.md), [docs/PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md) and the relevant technical document.
- Search existing issues before opening a new one.
- Never include real employee data, company documents, credentials, model blobs or runtime databases.
- Report security problems privately according to [SECURITY.md](SECURITY.md).

## Branching model

- `main`: stable public checkpoints.
- `dev`: integration branch for the next release.
- `feature/<short-name>`: new capability or improvement, branched from `dev`.
- `bugfix/<short-name>`: normal bug fix, branched from `dev`.
- `hotfix/<short-name>`: urgent stable fix, branched from `main` and merged back into `dev`.

Open normal pull requests against `dev`. Maintainers promote tested release candidates from `dev` to `main`.

## Development setup

```bash
python -m venv .venv
python -m pip install -r requirements-dev.txt
```

Use `.env.example` to create a local `.env` with new random secrets. Do not reuse example values outside local development.

## Code and commit style

- Prefer small, readable functions and explicit error handling.
- Add comments for security boundaries and non-obvious orchestration logic.
- Preserve access checks before retrieval and confirmation gates before actions.
- Use an imperative Conventional Commit prefix such as `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `security:`, `ci:` or `chore:`.
- Keep the first commit-message line at 72 characters or fewer.

## Required checks

```bash
ruff check app scripts tests
python -m pytest -q
node --check app/static/app.js
node --check app/static/enhancements.js
```

For interface changes, also exercise the real interaction in a supported browser and include screenshots when useful.

## Pull request checklist

- Explain the problem, approach and user impact.
- Link the relevant issue.
- Add or update tests for behavior changes.
- Update documentation when behavior, configuration or operations change.
- Confirm that no secret, personal data or internal document is present.
- Confirm that progress indicators reflect work that actually ran.

By participating, you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
