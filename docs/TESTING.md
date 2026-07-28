# Testing Guide

## Standard command

From PowerShell in the project root:

```powershell
.\scripts\test_windows.ps1
```

The script runs Ruff, the Python suite and both browser JavaScript syntax checks when Node.js is installed.

## Current automated coverage

The suite covers core prototype behavior including sessions, team access, retrieval, orchestration, language preferences, chat behavior, conversation isolation, feedback, editable profiles, dashboard metrics, the quality benchmark, documents, administration, action confirmation and information-disclosure boundaries.

## Golden-question benchmark

Start the application, use an already-onboarded demo account, and run:

```powershell
.\.venv\Scripts\python.exe scripts\run_quality_evaluation.py --email your.name@company.example --name "Your Name"
```

The initial 12 cases are in `evaluations/golden_questions.jsonl`. Results are written to the ignored `artifacts/evaluations/` directory. Treat the score as a regression signal and review failures manually; it does not replace department-owner or native-speaker assessment.

## Required checks by change type

- Backend behavior: run `python -m pytest -q` and add or update a focused test.
- Frontend JavaScript: run `node --check app/static/app.js` plus a browser check.
- Retrieval or model routing: test known prompts, evidence selection, unavailable-model fallback, and insufficient-evidence behavior.
- Permissions: test both allowed and denied users for every affected endpoint and knowledge team.
- Database schema: test migration from a copy of existing data and verify backup/rollback.
- Actions: test confirmation, duplicate submission, failure, retry, and audit recording.
- Language changes: check interface text, prompt language, answers, and fallback behavior with a native-speaker review.

## Browser acceptance checklist

- Login and onboarding work at normal desktop size.
- A user can type and submit a message.
- Microphone permission and speech-to-text work in a supported browser.
- The language selector updates the whole assistant experience.
- A company question returns a useful answer with readable sources.
- A complex request displays planned work and multiple model statuses in the same chat.
- Failure of one model produces an understandable fallback or error.
- Team-restricted content is not visible to an unauthorized account.
- External actions remain simulated until confirmation and real-connector approval.
- Layout remains usable at a narrow mobile viewport.

## Database integrity check

The following Python snippet performs a read-only integrity check on every transferred SQLite database:

```powershell
@'
import sqlite3
from pathlib import Path

for path in Path("data").rglob("*.db"):
    with sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True) as db:
        result = db.execute("PRAGMA integrity_check").fetchone()[0]
    print(path, result)
'@ | .\.venv\Scripts\python.exe -
```

Every result must be `ok`.
