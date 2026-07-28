from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def load_evaluation_cases(path: Path) -> list[dict[str, Any]]:
    cases = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        try:
            case = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON on line {line_number}: {exc}") from exc
        required = {"id", "department", "language", "prompt", "expected_any"}
        missing = required - set(case)
        if missing:
            raise ValueError(f"Case {case.get('id', line_number)} is missing: {sorted(missing)}")
        cases.append(case)
    return cases


def score_evaluation_answer(case: dict[str, Any], answer: str) -> dict[str, Any]:
    normalized = " ".join(answer.casefold().split())
    expected = [str(term).casefold() for term in case.get("expected_any", [])]
    term_hits = [term for term in expected if term in normalized]
    citations = sorted(set(re.findall(r"\[S(\d+)\]", answer)))
    minimum_citations = int(case.get("minimum_citations", 0))
    term_score = len(term_hits) / len(expected) if expected else 1.0
    citation_score = min(len(citations) / minimum_citations, 1.0) if minimum_citations else 1.0
    refusal_expected = bool(case.get("expect_insufficient_evidence", False))
    refusal_markers = (
        "approved knowledge",
        "approved information",
        "स्वीकृत जानकारी",
        "approved knowledge nahi mila",
    )
    refusal_detected = any(marker.casefold() in normalized for marker in refusal_markers)
    refusal_score = 1.0 if refusal_detected == refusal_expected else 0.0
    overall = round((term_score * 0.55 + citation_score * 0.30 + refusal_score * 0.15) * 100)
    return {
        "case_id": case["id"],
        "overall_score": overall,
        "term_score": round(term_score * 100),
        "citation_score": round(citation_score * 100),
        "refusal_score": round(refusal_score * 100),
        "matched_terms": term_hits,
        "citations": citations,
        "passed": overall >= int(case.get("pass_score", 75)),
    }

