# OpenSource AI Workspace

> A multilingual, department-aware AI workspace that coordinates self-hosted models and approved knowledge while keeping people in control.

[![CI](https://github.com/himanshusharma75035-sudo/ai-workspace/actions/workflows/ci.yml/badge.svg)](https://github.com/himanshusharma75035-sudo/ai-workspace/actions/workflows/ci.yml)
[![MIT License](https://img.shields.io/badge/license-MIT-0b8060.svg)](LICENSE)
[![GitHub issues](https://img.shields.io/github/issues/himanshusharma75035-sudo/ai-workspace)](https://github.com/himanshusharma75035-sudo/ai-workspace/issues)
![OpenSource AI Workspace overview](docs/assets/project-overview.svg)

## Overview

OpenSource AI Workspace explores a simple idea: employees should not need technical skills to benefit from AI. A person can speak or type in a familiar language, while an orchestrator checks access, finds approved knowledge, divides complex work and coordinates the appropriate local AI models or tools.

The repository is an exploratory reference implementation. It demonstrates multilingual interaction, visible model orchestration, department-aware retrieval and confirmation-gated actions without claiming production readiness.

## Features

- English, Hindi, Hinglish and 11 additional Indian-language selections.
- Browser speech-to-text using the selected language locale.
- Self-hosted model execution through Ollama.
- Hybrid keyword and semantic retrieval with citations.
- Separate public and department knowledge stores.
- Visible execution stages for larger requests.
- Conversation history, editable employee context and answer feedback.
- Confirmation-gated action simulations and audit events.
- Owner quality dashboard and guarded Linux service controls.

## How it works

![Multi-model orchestration flow](docs/assets/orchestration-flow.svg)

1. An employee signs in, selects a language and speaks or types a request.
2. The orchestrator identifies the intent, access scope and required work.
3. Approved knowledge and specialised model roles work on separate steps.
4. The verifier checks evidence, completeness and action safety.
5. One joined response is returned with sources and visible progress.

## Tech stack

| Layer | Technology |
|---|---|
| API and orchestration | Python 3.12, FastAPI, WebSockets |
| Browser experience | HTML, CSS and vanilla JavaScript |
| Local models | Ollama, Qwen and EmbeddingGemma |
| Retrieval | SQLite FTS plus semantic embeddings |
| Data | Team-separated SQLite databases and local uploads |
| Quality | Pytest, Ruff and versioned golden questions |

## Getting started

### Prerequisites

- Python 3.11 or 3.12
- Ollama
- Node.js for JavaScript syntax checks

### Local setup

```bash
git clone https://github.com/himanshusharma75035-sudo/ai-workspace.git
cd ai-workspace
python -m venv .venv
```

On Windows PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup_windows.ps1
.\scripts\start_ollama_windows.ps1
```

In a second PowerShell window:

```powershell
.\scripts\pull_models_windows.ps1
.\scripts\run_windows.ps1
```

Open [http://127.0.0.1:8181](http://127.0.0.1:8181). FastAPI exposes interactive API documentation at [http://127.0.0.1:8181/docs](http://127.0.0.1:8181/docs).

See the [Windows setup guide](docs/SETUP_WINDOWS.md) and [runbook](docs/RUNBOOK.md) for details.

### Configuration

Copy `.env.example` to `.env` and configure the installation without changing source code:

| Variable | Purpose |
|---|---|
| `ORGANIZATION_NAME` | Organization name used by prompts and the interface |
| `ASSISTANT_NAME` | Display name of the AI workspace |
| `ALLOWED_EMAIL_DOMAIN` | Domain accepted by the demonstration login |
| `SESSION_SECRET` | Unique local session-signing secret |
| `KNOWLEDGE_SOURCES_JSON` | JSON list of approved public website titles and URLs |
| `OLLAMA_*_MODEL` | Configured planning, answer and embedding model names |

An empty `KNOWLEDGE_SOURCES_JSON` disables website ingestion. Department documents can still be added through the controlled upload flow.

### Docker Compose

Copy the safe configuration template and set unique secret values before starting:

```bash
cp .env.example .env
docker compose up --build
```

The Compose configuration runs the application and Ollama with persistent local volumes. Download the configured models into the Ollama container before expecting model-backed answers.

## Development checks

```bash
python -m pip install -r requirements-dev.txt
ruff check app scripts tests
python -m pytest -q
node --check app/static/app.js
node --check app/static/enhancements.js
```

## Documentation

- [Project context](docs/PROJECT_CONTEXT.md)
- [Branding and organization configuration](docs/BRANDING_AND_CONFIGURATION.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Data and models](docs/DATA_AND_MODELS.md)
- [Design decisions](docs/DECISIONS.md)
- [Testing](docs/TESTING.md)
- [Operations runbook](docs/RUNBOOK.md)
- [Roadmap](ROADMAP.md)
- [Security policy](SECURITY.md)

## Contributing

Contributions are welcome. Start with [CONTRIBUTING.md](CONTRIBUTING.md), follow the [Code of Conduct](CODE_OF_CONDUCT.md), and open a feature or bug branch from `dev`. Please report vulnerabilities through the private process described in [SECURITY.md](SECURITY.md), not a public issue.

## Project status

This is an exploratory prototype. Demo authentication, simulated actions and local process controls are intentionally not production security controls. Review the [roadmap](ROADMAP.md) and [security policy](SECURITY.md) before using the project beyond local evaluation.

## License and trademarks

The source code is available under the [MIT License](LICENSE). The license does not grant permission to use the organization names, logos or trademarks to imply endorsement.
