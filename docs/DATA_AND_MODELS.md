# Data and Model Guide

## Repository contents

- Application source and tests
- Dependency manifests
- A safe `.env.example`

Runtime databases, indexes and uploads are deliberately absent from the repository. Create them locally or in an approved deployment environment.

## Deliberately excluded

- Real `.env` values and secrets
- Linux `.venv`
- `node_modules` and package caches
- Downloaded Ollama model blobs, approximately 4.7 GB on the source host
- Runtime logs, PID files, caches, and temporary home directories

These exclusions keep the source portable and reduce accidental secret or binary distribution.

## Database layout

- `data/control.db` contains application control data.
- `data/knowledge/public/knowledge.db` contains public company knowledge.
- `data/knowledge/<team>/knowledge.db` contains a team's indexed content.
- `data/uploads/` contains uploaded source material.

The team databases are a permission boundary only when the application checks the signed-in user's allowed teams before opening or querying them. Interface hiding alone is never sufficient.

## Default Ollama models

The safe environment template configures:

- `qwen3:4b` for primary responses
- `qwen3:1.7b` as a faster fallback or specialist
- `embeddinggemma` for embeddings

The current orchestrator also uses `qwen3:0.6b` for lightweight planning. Install all four with `scripts/pull_models_windows.ps1`.

## Public website sources

Website ingestion reads the `KNOWLEDGE_SOURCES_JSON` configuration value. Each item requires a `title` and a `url`. The source hosts become the ingestion allowlist, and an empty or omitted list disables website ingestion.

## Model evaluation criteria

Before replacing or promoting a model, compare it on:

- English, Hindi, Hinglish, and the enabled Indian languages
- the organization terminology and grounded question answering
- Drafting quality and instruction following
- Hallucination and citation faithfulness
- Tool/action parameter accuracy
- Latency, memory use, and concurrent-user behavior
- License and acceptable-use obligations
- Resistance to prompt injection in retrieved documents

Store evaluation prompts and expected outcomes as versioned test fixtures. Do not decide only from a few impressive chat examples.

## Re-indexing rule

Changing the embedding model makes stored embeddings incompatible. Update `.env`, install the new model, rebuild embeddings, and run retrieval regression tests before using the new index.

## Data lifecycle still to decide

Before production, the organization must define conversation retention, document retention, deletion requests, source ownership, PII handling, audit retention, backup retention, and who may approve each team knowledge source.
