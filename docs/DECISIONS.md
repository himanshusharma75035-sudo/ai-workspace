# Architecture Decision Log

This file records the decisions already reflected in the prototype. New material decisions should be added with a date, reason, and consequence.

## D-001: Self-hosted, open model policy

The prototype uses open-weight models through Ollama. This gives the organization control over hosting and model routing. It also makes model evaluation, patching, licensing review, capacity planning, and GPU operations the organization's responsibility.

## D-002: Orchestrator instead of one fixed model

Requests pass through intent detection, planning, routing, execution, and verification. This supports visible multi-model work and lets the organization trade off quality, speed, and cost per task. The orchestrator must remain understandable and observable; routing should not become an invisible black box.

## D-003: Separate knowledge database per team

Each team has a separate SQLite knowledge index, plus a public index. Isolation reduces accidental cross-team retrieval and matches the prototype's team-based user creation. It does not remove the need for server-side authorization tests.

## D-004: Hybrid retrieval with sources

Company answers use semantic and keyword retrieval, with source cards returned to the employee. This improves precision for names, products, and exact phrases while keeping answers traceable. A model response without adequate evidence must say that the available knowledge is insufficient.

## D-005: SQLite for the exploratory pilot

SQLite keeps the 50-60-user prototype easy to operate. It is not an irreversible production choice. Concurrency, backups, reporting, high availability, and multiple application instances should be reassessed before a broad launch.

## D-006: WebSocket orchestration progress

The same chat shows planning and model activity through `/api/chat/stream`. This makes the multi-model idea demonstrable and helps users understand that a complex request has been divided into work steps.

## D-007: Browser-based speech-to-text

Voice input uses browser speech recognition for the prototype. This is quick to demonstrate but varies by browser, platform, language, and network service. A production decision must evaluate an approved self-hosted speech model if browser behavior or data handling is unacceptable.

## D-008: Employee-selected interface language

The prototype includes English, Hindi, Hinglish, and additional Indian languages. The selected language affects interface text and response instructions. Translation quality must be tested with native speakers before production use.

## D-009: Confirmation before external actions

Email, ticket, and live-system actions require an explicit confirmation step. The prototype simulates external execution. Real connectors require narrow credentials, target allowlists, idempotency keys, timeout/retry behavior, and auditable results.

## D-010: Private network binding

The application and Ollama bind to loopback by default. Users connect through a controlled tunnel or Nginx. This prevents an unfinished prototype from becoming directly exposed on the server network.

## D-011: Clean open-source distribution

The repository includes source, scripts, tests, configuration templates and documentation. It excludes real `.env` values, runtime databases, uploaded content, local environments, model blobs, dependency caches, screenshots, process state and logs. These items are sensitive, machine-specific, reproducible or unsuitable for public source control.

## D-012: Quality must be measurable

Answer changes are evaluated against versioned golden questions, source-citation requirements, safe-refusal behavior, employee feedback, and observed latency. Deterministic scoring provides a repeatable regression signal; department owners and native speakers remain responsible for judging business correctness and language naturalness.
