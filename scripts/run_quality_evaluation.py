from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.evaluation import load_evaluation_cases, score_evaluation_answer


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the configured assistant benchmark")
    parser.add_argument("--base-url", default="http://127.0.0.1:8181")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--language")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    cases = load_evaluation_cases(ROOT / "evaluations" / "golden_questions.jsonl")
    if args.language:
        cases = [case for case in cases if case["language"] == args.language]
    if args.limit:
        cases = cases[: args.limit]
    if not cases:
        raise SystemExit("No evaluation cases matched the selected filters.")

    output_dir = ROOT / "artifacts" / "evaluations"
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    output_path = output_dir / f"quality-{stamp}.jsonl"
    results = []

    with httpx.Client(base_url=args.base_url, timeout=420) as client:
        login = client.post(
            "/api/login/demo", json={"email": args.email, "display_name": args.name}
        )
        login.raise_for_status()
        user = login.json()["user"]
        if not user.get("onboarding_complete"):
            raise SystemExit("The evaluation account must complete onboarding in the browser first.")

        for index, case in enumerate(cases, 1):
            response = client.post(
                "/api/chat",
                json={"message": case["prompt"], "language": case["language"]},
            )
            response.raise_for_status()
            payload = response.json()
            score = score_evaluation_answer(case, payload["answer"])
            result = {
                **score,
                "department": case["department"],
                "language": case["language"],
                "prompt": case["prompt"],
                "answer": payload["answer"],
                "model": payload["model"],
                "quality": payload.get("quality", {}),
                "source_count": len(payload.get("sources", [])),
            }
            results.append(result)
            print(
                f"[{index}/{len(cases)}] {case['id']}: "
                f"{score['overall_score']} ({'PASS' if score['passed'] else 'FAIL'})"
            )

    output_path.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in results) + "\n",
        encoding="utf-8",
    )
    passed = sum(1 for item in results if item["passed"])
    average = round(sum(item["overall_score"] for item in results) / len(results))
    print(f"Summary: {passed}/{len(results)} passed; average score {average}.")
    print(f"Results: {output_path}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
