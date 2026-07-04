"""Main NLP analysis pipeline."""

import numpy as np

from analysis.embeddings import encode_texts
from analysis.insights import (
    build_insight_summary,
    classify_theme_insights,
    dominant_sentiment,
    opportunity_score,
    select_representative_quotes,
    theme_confidence,
)
from analysis.llm import summarize_theme, classify_review_segment, extract_keywords_with_llm
from analysis.keywords import extract_keywords_from_vectors
from analysis.preprocessing import is_english, is_noise, preprocess_text
from analysis.report import AnalysisStats
from analysis.sentiment import classify_sentiments
from analysis.themes import discover_themes
from analysis.vector_store import get_embeddings_for_reviews, upsert_review_embeddings
from models.database import get_session_factory, init_db
from models.schema import Insight, Quote, Review, ReviewTheme, Theme
from utils.config import get_settings
from utils.logging import get_logger

logger = get_logger(__name__)


def _clear_theme_results(session) -> None:
    session.query(Quote).delete()
    session.query(Insight).delete()
    session.query(ReviewTheme).delete()
    session.query(Theme).delete()


def _load_or_build_embeddings(session, reviews: list[Review], settings) -> tuple[np.ndarray, int]:
    review_ids = [review.id for review in reviews]
    existing_vectors = get_embeddings_for_reviews(review_ids)

    if len(existing_vectors) == len(reviews):
        return existing_vectors, 0

    logger.info("Chroma index missing some embeddings; rebuilding collection entries for current reviews.")
    texts = [review.content for review in reviews]
    vectors = encode_texts(texts)
    metadatas = [
        {
            "platform": review.platform,
            "posted_at": review.posted_at.isoformat(),
            "sentiment": review.sentiment or "",
        }
        for review in reviews
    ]
    saved = upsert_review_embeddings(
        review_ids=review_ids,
        texts=texts,
        embeddings=vectors,
        metadatas=metadatas,
    )
    return vectors, saved


def run_analysis(force_themes: bool = False, min_topic_size: int = 15) -> AnalysisStats:
    init_db()
    settings = get_settings()
    stats = AnalysisStats()
    session = get_session_factory()()

    try:
        reviews = session.query(Review).order_by(Review.posted_at.desc()).all()

        needs_sentiment = session.query(Review).filter(Review.sentiment.is_(None)).all()
        if needs_sentiment:
            labels = classify_sentiments([r.content for r in needs_sentiment])
            for review, label in zip(needs_sentiment, labels):
                review.sentiment = label
            stats.sentiment_labeled = len(needs_sentiment)
            session.commit()

        all_vectors, stats.embeddings_saved = _load_or_build_embeddings(session, reviews, settings)
        if stats.embeddings_saved:
            session.commit()

        usable = []
        for review in reviews:
            text = preprocess_text(review.content)
            if is_noise(text) or not is_english(text):
                continue
            usable.append(review)

        stats.reviews_analyzed = len(usable)
        logger.info("Analyzing %s usable reviews (of %s total)", len(usable), len(reviews))

        for review in usable:
            label = review.sentiment or "neutral"
            stats.sentiment_breakdown[label] = stats.sentiment_breakdown.get(label, 0) + 1

        review_id_to_index = {r.id: i for i, r in enumerate(reviews)}
        usable_indices = [review_id_to_index[r.id] for r in usable]
        vectors = all_vectors[usable_indices]

        theme_exists = session.query(Theme).count() > 0
        if theme_exists and not force_themes:
            logger.info("Themes already exist — skipping (use --force-themes to regenerate)")
            assigned = session.query(ReviewTheme.review_id).distinct().count()
            stats.outliers = len(usable) - assigned
            return stats

        if theme_exists and force_themes:
            _clear_theme_results(session)
            session.commit()

        documents = [r.content for r in usable]
        review_ids = [r.id for r in usable]
        clusters, _ = discover_themes(documents, vectors, min_topic_size=min_topic_size)
        review_map = {r.id: r for r in usable}

        for cluster in clusters:
            member_reviews = [review_map[review_ids[i]] for i in cluster.review_indices]
            sentiments = [r.sentiment or "neutral" for r in member_reviews]
            platforms = [r.platform for r in member_reviews]
            overall = dominant_sentiment(sentiments)
            posted_dates = [r.posted_at for r in member_reviews]

            # Allow LLM to refine or replace the topic keywords for better theme naming
            # First, try zero-cost local extractor using cluster embeddings
            try:
                member_embs = vectors[cluster.review_indices]
            except Exception:
                member_embs = None

            local_keywords = extract_keywords_from_vectors([r.content for r in member_reviews], member_embs, top_k=8)

            # Next, try LLM extractor if available (Groq/Claude). Prefer LLM output when present.
            llm_keywords = extract_keywords_with_llm([r.content for r in member_reviews], existing_keywords=cluster.keywords)

            chosen_keywords = llm_keywords or local_keywords or cluster.keywords

            theme = Theme(
                name=cluster.name,
                description=f"Keywords: {', '.join(chosen_keywords[:6])}",
                review_count=len(member_reviews),
                overall_sentiment=overall,
                confidence_score=theme_confidence(cluster.probabilities),
                date_range_start=min(posted_dates),
                date_range_end=max(posted_dates),
                top_keywords=chosen_keywords,
            )
            session.add(theme)
            session.flush()

            for idx, prob in zip(cluster.review_indices, cluster.probabilities):
                session.add(
                    ReviewTheme(
                        review_id=review_ids[idx],
                        theme_id=theme.id,
                        membership_score=prob,
                    )
                )

            member_dicts = [
                {"id": r.id, "content": r.content, "sentiment": r.sentiment, "platform": r.platform}
                for r in member_reviews
            ]
            for q in select_representative_quotes(member_dicts):
                session.add(
                    Quote(
                        review_id=q["id"],
                        theme_id=theme.id,
                        excerpt=q["excerpt"],
                        source_platform=q["platform"],
                        is_representative=True,
                    )
                )
                stats.quotes_created += 1

            # --- Use LLM (Claude) or heuristic to generate human-readable theme name and summary
            reps = [q["excerpt"] for q in select_representative_quotes(member_dicts, max_quotes=4)]
            llm_out = summarize_theme(theme.top_keywords, reps)
            if llm_out:
                theme.readable_name = llm_out.get("theme_name") or theme.name
                theme.summary = llm_out.get("summary")
                theme.root_cause = llm_out.get("root_cause")
            else:
                theme.readable_name = theme.name
                theme.summary = None
                theme.root_cause = None

            # --- Classify member reviews into user segments
            for r in member_reviews:
                seg = classify_review_segment(r.content)
                r.user_segment = seg

            for category in classify_theme_insights(cluster.name, cluster.keywords, platforms):
                session.add(
                    Insight(
                        theme_id=theme.id,
                        category=category,
                        summary=build_insight_summary(
                            category, cluster.name, len(member_reviews), overall, platforms
                        ),
                        supporting_review_count=len(member_reviews),
                        opportunity_score=opportunity_score(len(member_reviews), overall),
                    )
                )
                stats.insights_created += 1

            stats.themes_created += 1
            stats.top_themes.append(
                {
                    "name": cluster.name,
                    "readable_name": theme.readable_name,
                    "summary": theme.summary,
                    "review_count": len(member_reviews),
                    "sentiment": overall,
                }
            )

        assigned = session.query(ReviewTheme.review_id).distinct().count()
        stats.outliers = len(usable) - assigned
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    logger.info(
        "Analysis done — themes=%s insights=%s quotes=%s",
        stats.themes_created,
        stats.insights_created,
        stats.quotes_created,
    )
    return stats
