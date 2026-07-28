# Instructions for Coding Agents

This file defines the safety and quality rules for automated work in this repository.

## Mission

Build a trustworthy multilingual employee assistant that lets non-technical employees speak or write naturally, coordinates suitable AI helpers, uses only permitted knowledge and keeps people in control of external actions.

## Workspace boundary

- Treat this repository root as the complete work scope.
- Do not modify system services, reverse proxies, other projects or external databases as an incidental step.
- Contributors must not access or deploy to a specific organization's environment. Maintainer deployments require separate, explicit authorization.
- Preserve unrelated changes and inspect a file before editing it.

## Secrets and sensitive data

- Never commit `.env`, passwords, app passwords, session secrets, authentication tokens or private keys.
- Use `.env.example` for documented placeholders only.
- `data/` may contain conversations, audit events or uploaded documents and must never be committed.
- Never expose one department's data to another department.

## White-label requirement

- Never hard-code a company, assistant, email-domain or public knowledge-source identity.
- Use `ORGANIZATION_NAME`, `ASSISTANT_NAME`, `ORGANIZATION_INITIAL`, `ORGANIZATION_ALIASES`, `ALLOWED_EMAIL_DOMAIN` and `KNOWLEDGE_SOURCES_JSON` through `app/config.py`.
- New interface copy that needs an identity must consume the branding payload returned by `/api/session`.
- Keep example defaults neutral and safe for a public repository.

## Current product truths

- Authentication is a demonstration email-domain flow, not production SSO or 2FA.
- External actions are simulated and require confirmation.
- Speech-to-text is provided by the browser; the application does not store audio.
- The selected language controls both interface copy and answer language.
- Progress must reflect work that actually ran; never invent model activity.
- Default model roles use Qwen through Ollama, while EmbeddingGemma performs semantic retrieval.
- RAG service controls are owner-only, disabled by default and limited to validated project-local processes.

## Code map

- `app/main.py`: FastAPI routes, sessions, streaming, uploads and admin endpoints.
- `app/orchestrator.py`: intent routing, language rules, model calls, planning and answer validation.
- `app/knowledge.py`: document chunking, SQLite FTS, embeddings and hybrid ranking.
- `app/database.py`: users, conversations, actions, feedback and audit events.
- `app/service_control.py`: guarded Linux process status and lifecycle actions.
- `app/static/`: browser UI, speech recognition, localization and execution visualization.
- `tests/test_core.py`: regression contracts for routing, grounding, language and orchestration.

## Required workflow

1. Read `docs/PROJECT_CONTEXT.md` and the relevant source before changing behavior.
2. Make the smallest coherent change and add regression coverage for behavior changes.
3. Run `python -m pytest -q`, `ruff check app scripts tests`, `node --check app/static/app.js` and `node --check app/static/enhancements.js`.
4. Verify real browser interaction for UI changes.
5. Maintainers follow local verification → approved RAG deployment verification → GitHub publication.
6. Report what was tested and any remaining limitation.

## Change-specific rules

- When adding a language, update backend support, prompts, frontend localization and tests together.
- Keep model progress aligned with the components that truly executed.
- Enforce department access before retrieval, not only in the interface.
- Preserve existing data and provide forward migrations for database changes.
- Keep external actions sandboxed until authorization, idempotency, audit evidence and explicit confirmation are implemented.
- Never weaken source validation merely to make an answer pass.

## Definition of done

A change is complete only when requested behavior works, relevant checks pass, sensitive data remains protected and documentation matches the real system.
