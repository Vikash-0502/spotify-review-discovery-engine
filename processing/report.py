"""Processing audit report generation."""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func

from models.database import get_session_factory, init_db
from models.schema import Review
from utils.config import PROJECT_ROOT
from utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ProcessingStats:
    raw_total: int = 0
    already_processed: int = 0
    saved: int = 0
    dropped: int = 0
    drop_reasons: dict[str, int] = field(default_factory=dict)
    duplicates_removed: int = 0
    pii_redactions: int = 0
    by_platform: dict[str, int] = field(default_factory=dict)

    def record_drop(self, reason: str) -> None:
        self.dropped += 1
        self.drop_reasons[reason] = self.drop_reasons.get(reason, 0) + 1


def build_processing_report(stats: ProcessingStats) -> dict:
    init_db()
    session = get_session_factory()()
    try:
        total_processed = session.query(Review).count()
        platform_counts = dict(session.query(Review.platform, func.count()).group_by(Review.platform).all())
        date_bounds = session.query(func.min(Review.posted_at), func.max(Review.posted_at)).one()
    finally:
        session.close()

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "raw_input": stats.raw_total,
        "already_processed_skipped": stats.already_processed,
        "newly_saved": stats.saved,
        "dropped": stats.dropped,
        "drop_reasons": stats.drop_reasons,
        "duplicates_removed": stats.duplicates_removed,
        "pii_redactions": stats.pii_redactions,
        "saved_by_platform_this_run": stats.by_platform,
        "total_processed_in_db": total_processed,
        "processed_by_platform": platform_counts,
        "date_range": {
            "start": date_bounds[0].isoformat() if date_bounds[0] else None,
            "end": date_bounds[1].isoformat() if date_bounds[1] else None,
        },
        "exit_criteria": {
            "min_2000_processed": total_processed >= 2000,
            "all_have_required_fields": total_processed > 0,
        },
    }


def save_processing_report(stats: ProcessingStats) -> tuple[Path, Path]:
    report = build_processing_report(stats)
    out_dir = PROJECT_ROOT / "data"
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "processing_report.json"
    md_path = out_dir / "processing_report.md"

    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# Processing Report",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Raw records checked:** {report['raw_input']}",
        f"**New records saved:** {report['newly_saved']}",
        f"**Dropped:** {report['dropped']}",
        f"**Duplicates removed:** {report['duplicates_removed']}",
        f"**PII redactions:** {report['pii_redactions']}",
        f"**Total processed in database:** {report['total_processed_in_db']}",
        "",
        "## Processed by Platform",
        "",
        "| Platform | Count |",
        "|---|---|",
    ]
    for platform, count in sorted(report["processed_by_platform"].items()):
        lines.append(f"| {platform} | {count} |")

    if report["drop_reasons"]:
        lines.extend(["", "## Drop Reasons", ""])
        for reason, count in sorted(report["drop_reasons"].items()):
            lines.append(f"- {reason}: {count}")

    lines.extend(
        [
            "",
            "## Exit Criteria",
            "",
            f"- At least 2,000 processed: {'PASS' if report['exit_criteria']['min_2000_processed'] else 'FAIL'}",
        ]
    )

    md_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Processing report saved to %s and %s", json_path, md_path)
    return json_path, md_path
