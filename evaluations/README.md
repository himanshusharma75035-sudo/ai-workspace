# Answer Quality Evaluation

`golden_questions.jsonl` is the initial repeatable benchmark for the CEO prototype. It intentionally starts with public the organization knowledge, multilingual behavior, drafting, automation controls, capability limits, and safe refusal.

Each line contains:

- a stable case ID;
- department and selected language;
- the employee prompt;
- expected terms used for deterministic scoring;
- minimum source citations;
- whether an insufficient-evidence answer is expected;
- the minimum passing score.

Run the application and then execute:

```powershell
.\.venv\Scripts\python.exe scripts\run_quality_evaluation.py --email your.name@company.example --name "Your Name"
```

The account must already be onboarded. Results are written beneath `artifacts/evaluations/`. Running the benchmark creates test conversations and feedback-neutral assistant messages in that account.

This deterministic score is a regression signal, not a substitute for human review. Department owners should add 30–50 approved cases for their team and native speakers should assess language naturalness.

