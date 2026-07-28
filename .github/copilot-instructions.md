# OpenSource AI Workspace contributor instructions

- Read `AGENTS.md` and `docs/PROJECT_CONTEXT.md` before changing behavior.
- Keep the prototype honest: demo authentication is not production authentication, and external actions remain simulated.
- Enforce department access before retrieval or conversation access.
- Never add `.env`, employee data, uploaded documents, databases, logs or model files.
- Add regression coverage for behavior changes and run the checks documented in `CONTRIBUTING.md`.
- Keep progress cards aligned with work that actually executed.
- Update documentation when configuration, behavior, API contracts or operations change.
