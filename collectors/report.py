"""Generate collection summary report from database."""

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func

from collectors.base import SourceStats, count_raw_by_platform
from models.database import get_session_factory, init_db
from models.schema import RawReview
from utils.config import PROJECT_ROOT
from utils.logging import get_logger

logger = get_logger(__name__)


def _format_date(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%d")


def build_report(run_stats: list[SourceStats]) -> dict:
    init_db()
    session = get_session_factory()()
    try:
        total = session.query(RawReview).count()
        by_platform = count_raw_by_platform(session)

        date_bounds = session.query(
            func.min(RawReview.collected_at),
            func.max(RawReview.collected_at),
        ).one()

        sources_used = len([p for p, c in by_platform.items() if c > 0])
    finally:
        session.close()

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_records": total,
        "sources_used": sources_used,
        "by_platform": by_platform,
        "collection_window": {
            "start": date_bounds[0].isoformat() if date_bounds[0] else None,
            "end": date_bounds[1].isoformat() if date_bounds[1] else None,
        },
        "run_details": [
            {
                **asdict(s),
                "date_start": _format_date(s.date_start),
                "date_end": _format_date(s.date_end),
            }
            for s in run_stats
        ],
        "exit_criteria": {
            "min_2000_records": total >= 2000,
            "min_3_sources": sources_used >= 3,
        },
    }


def save_report(report: dict) -> tuple[Path, Path]:
    out_dir = PROJECT_ROOT / "data"
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "collection_report.json"
    md_path = out_dir / "collection_report.md"

    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# Collection Report",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Total records:** {report['total_records']}",
        f"**Sources used:** {report['sources_used']}",
        "",
        "## Records by Platform",
        "",
        "| Platform | Count |",
        "|---|---|",
    ]
    for platform, count in sorted(report["by_platform"].items()):
        lines.append(f"| {platform} | {count} |")

    lines.extend(
        [
            "",
            "## Exit Criteria",
            "",
            f"- Minimum 2,000 records: {'PASS' if report['exit_criteria']['min_2000_records'] else 'FAIL'}",
            f"- At least 3 sources: {'PASS' if report['exit_criteria']['min_3_sources'] else 'FAIL'}",
            "",
            "## This Run",
            "",
        ]
    )

    for detail in report["run_details"]:
        lines.append(f"### {detail['platform']}")
        lines.append(f"- Fetched: {detail['fetched']}")
        lines.append(f"- Matched keywords: {detail['matched']}")
        lines.append(f"- Saved: {detail['saved']}")
        lines.append(f"- Duplicates skipped: {detail['skipped_duplicates']}")
        if detail.get("date_start"):
            lines.append(f"- Date range: {detail['date_start']} → {detail['date_end']}")
        if detail.get("errors"):
            lines.append(f"- Errors: {', '.join(detail['errors'])}")
        lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Report saved to %s and %s", json_path, md_path)
    return json_path, md_path
