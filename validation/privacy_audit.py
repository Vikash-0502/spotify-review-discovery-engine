"""Privacy audit helpers for Phase 9 integration checks."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from sqlalchemy.orm import Session

from models.schema import Insight, Quote, Review, WeeklyPulse
from processing.pii_scanner import contains_pii, redact_pii
from validation.pii import find_pii, should_scan_text_field, validate_pii

ANONYMIZED_AUTHOR_RE = re.compile(r"^user_[a-f0-9]{8}$")
FORBIDDEN_RESPONSE_KEYS = {"author", "author_name", "username", "display_name", "profile_url"}


@dataclass
class PrivacyFinding:
    surface: str
    record_id: str
    field: str
    issue: str


@dataclass
class PrivacyAuditReport:
    passed: bool
    findings: list[PrivacyFinding] = field(default_factory=list)
    records_scanned: dict[str, int] = field(default_factory=dict)

    def add(self, surface: str, record_id: str, field: str, issue: str) -> None:
        self.findings.append(PrivacyFinding(surface, record_id, field, issue))
        self.passed = False


def _scan_text_fields(
    report: PrivacyAuditReport,
    *,
    surface: str,
    record_id: str,
    fields: Iterable[tuple[str, str]],
) -> None:
    for field_name, text in fields:
        if not text or not should_scan_text_field(field_name, text):
            continue
        if contains_pii(text):
            report.add(surface, record_id, field_name, "contains email, phone, handle, or credential URL pattern")


def audit_reviews(db: Session, *, sample_limit: int | None = None) -> PrivacyAuditReport:
    report = PrivacyAuditReport(passed=True, records_scanned={"reviews": 0})
    query = db.query(Review.id, Review.content, Review.anonymized_author)
    rows = query.all() if sample_limit is None else query.limit(sample_limit).all()

    for review_id, content, anonymized_author in rows:
        report.records_scanned["reviews"] += 1
        if anonymized_author and not ANONYMIZED_AUTHOR_RE.match(anonymized_author):
            report.add("reviews", review_id, "anonymized_author", "does not match user_<hash> format")
        _scan_text_fields(
            report,
            surface="reviews",
            record_id=review_id,
            fields=[("content", content or "")],
        )
    return report


def audit_quotes(db: Session, *, sample_limit: int | None = None) -> PrivacyAuditReport:
    report = PrivacyAuditReport(passed=True, records_scanned={"quotes": 0})
    query = db.query(Quote.id, Quote.excerpt)
    rows = query.all() if sample_limit is None else query.limit(sample_limit).all()

    for quote_id, excerpt in rows:
        report.records_scanned["quotes"] += 1
        _scan_text_fields(
            report,
            surface="quotes",
            record_id=quote_id,
            fields=[("excerpt", excerpt or "")],
        )
    return report


def audit_insights(db: Session, *, sample_limit: int | None = None) -> PrivacyAuditReport:
    report = PrivacyAuditReport(passed=True, records_scanned={"insights": 0})
    query = db.query(Insight.id, Insight.summary)
    rows = query.all() if sample_limit is None else query.limit(sample_limit).all()

    for insight_id, summary in rows:
        report.records_scanned["insights"] += 1
        _scan_text_fields(
            report,
            surface="insights",
            record_id=insight_id,
            fields=[("summary", summary or "")],
        )
    return report


def audit_weekly_pulses(db: Session, *, sample_limit: int | None = 5) -> PrivacyAuditReport:
    report = PrivacyAuditReport(passed=True, records_scanned={"weekly_pulses": 0})
    query = db.query(WeeklyPulse).order_by(WeeklyPulse.created_at.desc())
    pulses = query.all() if sample_limit is None else query.limit(sample_limit).all()

    for pulse in pulses:
        report.records_scanned["weekly_pulses"] += 1
        payload = {
            "headline": pulse.headline,
            "summary": pulse.summary,
            "top_themes": pulse.top_themes or [],
            "quotes": pulse.quotes or [],
            "actions": pulse.actions or [],
        }
        for error in validate_pii(payload):
            report.add("weekly_pulses", pulse.id, "pulse_body", error)
        if pulse.raw_response and contains_pii(pulse.raw_response):
            report.add("weekly_pulses", pulse.id, "raw_response", "contains email, phone, or credential URL pattern")
    return report


def merge_reports(*reports: PrivacyAuditReport) -> PrivacyAuditReport:
    merged = PrivacyAuditReport(passed=True)
    for report in reports:
        merged.findings.extend(report.findings)
        for key, count in report.records_scanned.items():
            merged.records_scanned[key] = merged.records_scanned.get(key, 0) + count
        if not report.passed:
            merged.passed = False
    return merged


def audit_database(db: Session, *, sample_limit: int | None = None) -> PrivacyAuditReport:
    return merge_reports(
        audit_reviews(db, sample_limit=sample_limit),
        audit_quotes(db, sample_limit=sample_limit),
        audit_insights(db, sample_limit=sample_limit),
        audit_weekly_pulses(db, sample_limit=sample_limit or 5),
    )


def audit_api_forbidden_keys(payload: Any, *, surface: str = "api") -> PrivacyAuditReport:
    """Ensure API payloads never expose reviewer-identifying field names."""
    report = PrivacyAuditReport(passed=True, records_scanned={"api_payload_nodes": 0})

    def walk(node: Any, path: str) -> None:
        report.records_scanned["api_payload_nodes"] += 1
        if isinstance(node, dict):
            for key, value in node.items():
                lowered = str(key).lower()
                if lowered in FORBIDDEN_RESPONSE_KEYS:
                    report.add(surface, path, lowered, "forbidden reviewer-identifying key exposed")
                walk(value, f"{path}.{key}")
        elif isinstance(node, list):
            for idx, item in enumerate(node):
                walk(item, f"{path}[{idx}]")

    walk(payload, surface)
    return report


def audit_api_payload(payload: Any, *, surface: str = "api") -> PrivacyAuditReport:
    report = PrivacyAuditReport(passed=True, records_scanned={"api_payload_nodes": 0})

    def walk(node: Any, path: str) -> None:
        report.records_scanned["api_payload_nodes"] += 1
        if isinstance(node, dict):
            for key, value in node.items():
                lowered = str(key).lower()
                if lowered in FORBIDDEN_RESPONSE_KEYS:
                    report.add(surface, path, lowered, "forbidden reviewer-identifying key exposed")
                walk(value, f"{path}.{key}")
        elif isinstance(node, list):
            for idx, item in enumerate(node):
                walk(item, f"{path}[{idx}]")
        elif isinstance(node, str):
            if not should_scan_text_field(path.rsplit(".", 1)[-1], node):
                return
            if contains_pii(node):
                report.add(surface, path, "value", "contains email, phone, handle, or credential URL pattern")

    walk(payload, surface)
    return report


def format_privacy_report(report: PrivacyAuditReport) -> str:
    lines = [
        "=== Privacy Audit ===",
        f"Status: {'PASSED' if report.passed else 'FAILED'}",
        "Records scanned:",
    ]
    for surface, count in sorted(report.records_scanned.items()):
        lines.append(f"  - {surface}: {count:,}")
    if report.findings:
        lines.append(f"Findings ({len(report.findings)}):")
        for finding in report.findings[:25]:
            lines.append(
                f"  - [{finding.surface}] {finding.record_id} · {finding.field}: {finding.issue}"
            )
        if len(report.findings) > 25:
            lines.append(f"  ... and {len(report.findings) - 25} more")
    else:
        lines.append("No PII or reviewer-identifying fields detected.")
    return "\n".join(lines)
