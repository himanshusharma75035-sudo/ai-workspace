# Prototype Runbook

## Daily local start

1. Open the project root in Antigravity.
2. Start Ollama with `scripts/start_ollama_windows.ps1` in one terminal.
3. Start the application with `scripts/run_windows.ps1` in a second terminal.
4. Open `http://127.0.0.1:8181`.
5. Confirm `http://127.0.0.1:8181/api/health` reports a healthy application and model connection.

## Daily local stop

Stop each foreground process with `Ctrl+C`. Do not kill unrelated Python or Ollama processes by process name.

## Pre-demo checklist

- Run `scripts/test_windows.ps1`.
- Check the selected models appear in Ollama.
- Test English, Hindi, and Hinglish prompts.
- Test the language selector and confirm navigation, helper text, and answers change language.
- Grant microphone permission and test voice input.
- Ask a company question and confirm relevant source cards are readable.
- Ask a complex multi-step task and confirm the model/work progress appears in the chat.
- Test one simulated external action and its confirmation gate.
- Confirm the demo account has only the intended team access.
- Keep a typed fallback prompt ready in case browser speech recognition is unavailable.

## Knowledge refresh

Public the organization website content can be re-ingested with:

```powershell
.\.venv\Scripts\python.exe scripts\ingest_websites.py
```

Rebuild stored embeddings after changing the embedding model:

```powershell
.\scripts\rebuild_embeddings_windows.ps1
```

Review source approval, content ownership, and team assignment before ingesting internal documents.

## Backup and recovery

The important mutable content is under `data/` and the local `.env` contains configuration secrets. Before a deployment or schema migration:

1. Stop application writes.
2. Use SQLite's backup API or `.backup` command for each database; do not copy an actively written database as if it were an ordinary file.
3. Store backups in an access-controlled location outside the repository.
4. Test that the backup opens and returns `ok` from `PRAGMA integrity_check`.
5. Back up uploaded source files if they are required for re-indexing.

Never commit live databases, uploads, or `.env`.

## RAG server boundary

Keep each deployment inside its dedicated project directory. The application binds to `127.0.0.1` by default and should be exposed only through an approved secure tunnel or reverse proxy. Contributors must not deploy to an the organization environment; maintainers require separate authorization.

## RAG service operations

The owner-only **System control** page shows validated status for the FastAPI application and project-local Ollama. Web actions require both the owner session and the separate `SERVICE_CONTROL_KEY`. The key is entered for each action, is cleared from the form immediately and is never stored by the browser.

The web page cannot start itself after the application is stopped. Use SSH for recovery:

```bash
cd /path/to/ai-workspace
./scripts/status.sh
./scripts/start_all.sh
```

All project-local commands are:

```bash
./scripts/start_all.sh       # start model server and application
./scripts/stop_all.sh        # stop application and model server
./scripts/restart_app.sh     # restart only the web application
./scripts/restart_all.sh     # restart both services
./scripts/status.sh          # show validated managed-process status
```

The scripts read PID files under `run/` and verify both the process command and `/proc/<pid>/cwd` before stopping anything. If a PID belongs to another process, the script refuses the action. Do not bypass this check or use broad process-name kill commands.

To enable the web controls on the RAG host, keep a random value of at least 32 characters in `SERVICE_CONTROL_KEY` and set `ENABLE_SERVICE_CONTROLS=true` in the project `.env`. Keep `.env` mode `600` and never paste the key into chat, logs, screenshots or source code.

## Deployment checklist

- Run all automated and browser checks against the exact candidate build.
- Take verified SQLite backups.
- Confirm `.env` values and model availability without printing secrets.
- Keep application and Ollama bound to private interfaces unless Nginx is fully configured.
- Configure Nginx TLS, authentication boundary, request size, rate limits, timeouts, and access logs.
- Use a dedicated non-root service account.
- Record the deployed revision or file manifest and rollback location.
- Smoke-test health, login, retrieval, chat streaming, language selection, and action confirmations.
- Test System control status and one safe restart, then confirm the application recovers on `127.0.0.1:8181`.

## Troubleshooting order

1. Check `/api/health`.
2. Check whether port 8181 is listening.
3. Check Ollama on port 11445.
4. Confirm required models are installed.
5. Check the application console for an exception.
6. Run tests to separate environment failures from code failures.
7. Check database integrity before changing or deleting any data.
8. Run `./scripts/status.sh`; if the application is stopped, recover with `./scripts/start_all.sh` from the project folder.
