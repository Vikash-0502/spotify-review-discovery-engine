"""Analysis summary report."""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func

from models.database import get_session_factory, init_db
from models.schema import Insight, Quote, Review, Theme
from analysis.vector_store import count_embeddings
from utils.config import PROJECT_ROOT
from utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AnalysisStats:
    reviews_analyzed: int = 0
    sentiment_labeled: int = 0
    embeddings_saved: int = 0
    themes_created: int = 0
    insights_created: int = 0
    quotes_created: int = 0
    outliers: int = 0
    sentiment_breakdown: dict[str, int] = field(default_factory=dict)
    top_themes: list[dict] = field(default_factory=list)


def build_analysis_report(stats: AnalysisStats) -> dict:
    init_db()
    session = get_session_factory()()
    try:
        total_reviews = session.query(Review).count()
        with_sentiment = session.query(Review).filter(Review.sentiment.isnot(None)).count()
        with_embeddings = count_embeddings()
        theme_count = session.query(Theme).count()
        insight_count = session.query(Insight).count()
        quote_count = session.query(Quote).count()

        sentiment_rows = session.query(Review.sentiment, func.count()).group_by(Review.sentiment).all()
        sentiment_breakdown = {row[0] or "unknown": row[1] for row in sentiment_rows}

        top_themes = (
            session.query(Theme.name, Theme.review_count, Theme.overall_sentiment)
            .order_by(Theme.review_count.desc())
            .limit(10)
            .all()
        )
    finally:
        session.close()

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reviews_analyzed": stats.reviews_analyzed,
        "sentiment_labeled_this_run": stats.sentiment_labeled,
        "embeddings_saved_this_run": stats.embeddings_saved,
        "themes_created_this_run": stats.themes_created,
        "insights_created_this_run": stats.insights_created,
        "quotes_created_this_run": stats.quotes_created,
        "outlier_reviews": stats.outliers,
        "totals": {
            "reviews": total_reviews,
            "with_sentiment": with_sentiment,
            "with_embeddings": with_embeddings,
            "themes": theme_count,
            "insights": insight_count,
            "quotes": quote_count,
        },
        "sentiment_breakdown": sentiment_breakdown,
        "top_themes": [
            {"name": name, "review_count": count, "sentiment": sentiment}
            for name, count, sentiment in top_themes
        ],
        "exit_criteria": {
            "all_reviews_have_sentiment": with_sentiment == total_reviews and total_reviews > 0,
            "themes_generated": theme_count > 0,
            "insights_with_evidence": insight_count > 0 and quote_count > 0,
            "search_index_ready": with_embeddings == total_reviews and total_reviews > 0,
        },
    }


def save_analysis_report(stats: AnalysisStats) -> tuple[Path, Path]:
    report = build_analysis_report(stats)
    out_dir = PROJECT_ROOT / "data"
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "analysis_report.json"
    md_path = out_dir / "analysis_report.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# Analysis Report",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Reviews analyzed:** {report['totals']['reviews']}",
        f"**Themes discovered:** {report['totals']['themes']}",
        f"**Insights generated:** {report['totals']['insights']}",
        "",
        "## Sentiment Breakdown",
        "",
        "| Sentiment | Count |",
        "|---|---|",
    ]
    for sentiment, count in sorted(report["sentiment_breakdown"].items()):
        lines.append(f"| {sentiment} | {count} |")

    lines.extend(["", "## Top Themes", ""])
    for theme in report["top_themes"]:
        lines.append(f"- **{theme['name']}** — {theme['review_count']} reviews ({theme['sentiment']})")

    lines.extend(["", "## Exit Criteria", ""])
    for key, passed in report["exit_criteria"].items():
        lines.append(f"- {key.replace('_', ' ')}: {'PASS' if passed else 'FAIL'}")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Analysis report saved to %s and %s", json_path, md_path)
    return json_path, md_path
