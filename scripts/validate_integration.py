#!/usr/bin/env python3
"""Phase 9 end-to-end integration and privacy validation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import requests  # noqa: E402

from analysis.question_mapper import RESEARCH_QUESTIONS  # noqa: E402
from models.database import get_session_factory, init_db  # noqa: E402
from utils.config import get_settings  # noqa: E402
from utils.logging import setup_logging  # noqa: E402
from validation.privacy_audit import audit_api_forbidden_keys, audit_api_payload, audit_database  # noqa: E402


class CheckResult:
    def __init__(self, name: str, passed: bool, detail: str = ""):
        self.name = name
        self.passed = passed
        self.detail = detail


def _api_base() -> str:
    settings = get_settings()
    host = "127.0.0.1" if settings.api_host == "0.0.0.0" else settings.api_host
    return f"http://{host}:{settings.api_port}"


def _get_json(path: str, *, params: dict | None = None, timeout: float = 10.0) -> tuple[int, dict | list | None]:
    response = requests.get(f"{_api_base()}{path}", params=params or {}, timeout=timeout)
    try:
        payload = response.json()
    except Exception:
        payload = None
    return response.status_code, payload


def check_api_health() -> CheckResult:
    try:
        status, payload = _get_json("/health", timeout=3.0)
    except Exception as exc:
        return CheckResult("API health", False, f"API unreachable: {exc}")
    if status == 200 and isinstance(payload, dict) and payload.get("status") == "ok":
        return CheckResult("API health", True, "Backend is online")
    return CheckResult("API health", False, f"Unexpected health response: {status} {payload}")


def check_pipeline_data() -> CheckResult:
    status, payload = _get_json("/api/stats")
    if status != 200 or not isinstance(payload, dict):
        return CheckResult("Pipeline data", False, f"/api/stats failed: {status}")
    total = int(payload.get("total_reviews") or 0)
    if total <= 0:
        return CheckResult(
            "Pipeline data",
            False,
            "No processed reviews found. Run collection → processing → analysis first.",
        )
    return CheckResult("Pipeline data", True, f"{total:,} reviews available")


def check_research_questions() -> CheckResult:
    status, payload = _get_json("/api/questions")
    if status != 200 or not isinstance(payload, dict):
        return CheckResult("Research questions", False, f"/api/questions failed: {status}")

    answers = payload.get("answers") or []
    if len(answers) != len(RESEARCH_QUESTIONS):
        return CheckResult(
            "Research questions",
            False,
            f"Expected {len(RESEARCH_QUESTIONS)} answers, got {len(answers)}",
        )

    missing = []
    for answer in answers:
        for field in ("question", "answer_summary", "criticality_rating", "supporting_review_count"):
            if field not in answer:
                missing.append(field)
    if missing:
        return CheckResult("Research questions", False, f"Missing fields: {sorted(set(missing))}")

    return CheckResult(
        "Research questions",
        True,
        f"All {len(RESEARCH_QUESTIONS)} research questions answered with evidence fields",
    )


def check_search_and_chat() -> list[CheckResult]:
    results: list[CheckResult] = []

    status, payload = _get_json("/api/search", params={"q": "recommendations", "limit": 5})
    if status != 200 or not isinstance(payload, dict) or "results" not in payload:
        results.append(CheckResult("Search", False, f"/api/search failed: {status}"))
    else:
        results.append(CheckResult("Search", True, f"{payload.get('total_matches', 0)} matches for 'recommendations'"))

    status, payload = _get_json(
        "/api/chat",
        params={"q": "Why do users struggle to discover new music?"},
        timeout=30.0,
    )
    if status != 200 or not isinstance(payload, dict):
        results.append(CheckResult("Chat", False, f"/api/chat failed: {status}"))
    else:
        refused = payload.get("refused")
        based_on = payload.get("based_on_review_count", 0)
        detail = "refused (no matching reviews)" if refused else f"grounded answer based on {based_on} reviews"
        results.append(CheckResult("Chat", True, detail))

    return results


def check_dashboard_endpoints() -> list[CheckResult]:
    endpoints = [
        ("/api/metrics", "Metrics"),
        ("/api/themes?limit=5", "Themes"),
        ("/api/sentiment", "Sentiment"),
        ("/api/pain-points", "Unmet needs"),
        ("/api/segments", "Segments"),
        ("/api/quotes", "Quotes"),
        ("/api/weekly-pulse/latest", "Weekly pulse"),
        ("/api/pipeline/status", "Pipeline status"),
    ]
    results: list[CheckResult] = []
    for path, label in endpoints:
        status, payload = _get_json(path)
        if status != 200:
            results.append(CheckResult(label, False, f"{path} returned {status}"))
            continue
        if path.endswith("/weekly-pulse/latest") and payload is None:
            results.append(CheckResult(label, True, "No pulse generated yet (endpoint OK)"))
        else:
            results.append(CheckResult(label, True, "Endpoint OK"))
    return results


def check_api_privacy() -> CheckResult:
    paths = [
        "/api/questions",
        "/api/search?q=shuffle&limit=3",
        "/api/themes?limit=3",
        "/api/quotes",
    ]
    forbidden = 0
    handle_hits = 0
    for path in paths:
        status, payload = _get_json(path)
        if status != 200:
            continue
        key_report = audit_api_forbidden_keys(payload, surface=path)
        forbidden += len(key_report.findings)
        content_report = audit_api_payload(payload, surface=path)
        handle_hits += len(content_report.findings)
    if forbidden:
        return CheckResult("API privacy", False, f"{forbidden} forbidden reviewer keys in API payloads")
    if handle_hits:
        return CheckResult(
            "API privacy",
            True,
            f"No forbidden keys; {handle_hits} residual @handle mention(s) in quote text — run scripts/remediate_content_pii.py",
        )
    return CheckResult("API privacy", True, "No forbidden keys or PII patterns in sampled API responses")


def check_database_privacy(*, sample_limit: int | None) -> CheckResult:
    init_db()
    session = get_session_factory()()
    try:
        report = audit_database(session, sample_limit=sample_limit)
    finally:
        session.close()

    critical = [f for f in report.findings if f.field == "anonymized_author" or "email" in f.issue or "phone" in f.issue]
    handle_only = len(report.findings) - len(critical)
    if critical:
        detail = f"{len(critical)} critical finding(s); run scripts/remediate_content_pii.py for @handle cleanup"
        return CheckResult("Database privacy", False, detail)
    if handle_only:
        return CheckResult(
            "Database privacy",
            True,
            f"No critical PII; {handle_only} residual @handle mention(s) — run scripts/remediate_content_pii.py",
        )
    return CheckResult("Database privacy", True, "No PII or reviewer-identifying fields detected")


def run_validation(*, require_api: bool, privacy_sample_limit: int | None) -> int:
    checks: list[CheckResult] = []

    checks.append(check_database_privacy(sample_limit=privacy_sample_limit))

    if require_api:
        health = check_api_health()
        checks.append(health)
        if not health.passed:
            for check in checks:
                symbol = "PASS" if check.passed else "FAIL"
                print(f"[{symbol}] {check.name}: {check.detail}")
            print("\nStart the API with: .venv\\Scripts\\python -m uvicorn api.main:app --reload")
            return 1

        checks.extend(
            [
                check_pipeline_data(),
                check_research_questions(),
                *check_search_and_chat(),
                *check_dashboard_endpoints(),
                check_api_privacy(),
            ]
        )

    print("\n=== Phase 9 Integration Validation ===\n")
    failed = 0
    for check in checks:
        symbol = "PASS" if check.passed else "FAIL"
        print(f"[{symbol}] {check.name}: {check.detail}")
        if not check.passed:
            failed += 1

    print(f"\nSummary: {len(checks) - failed}/{len(checks)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    setup_logging()
    parser = argparse.ArgumentParser(description="Validate end-to-end integration and privacy")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Run database privacy audit only (no live API required)",
    )
    parser.add_argument(
        "--privacy-sample",
        type=int,
        default=0,
        help="Limit DB rows scanned for privacy (0 = full scan)",
    )
    args = parser.parse_args()
    sample_limit = None if args.privacy_sample <= 0 else args.privacy_sample
    sys.exit(run_validation(require_api=not args.offline, privacy_sample_limit=sample_limit))
