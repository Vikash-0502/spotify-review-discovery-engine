"""Theme discovery using BERTopic."""

from dataclasses import dataclass

import numpy as np
from bertopic import BERTopic
from hdbscan import HDBSCAN
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.feature_extraction import _stop_words as sklearn_stop

from utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ThemeCluster:
    topic_id: int
    name: str
    keywords: list[str]
    review_indices: list[int]
    probabilities: list[float]


def discover_themes(
    documents: list[str],
    embeddings: np.ndarray,
    min_topic_size: int = 15,
) -> tuple[list[ThemeCluster], BERTopic]:
    logger.info("Running BERTopic on %s documents", len(documents))

    cluster_model = HDBSCAN(
        min_cluster_size=min_topic_size,
        metric="euclidean",
        cluster_selection_method="eom",
        prediction_data=True,
    )

    topic_model = BERTopic(
        hdbscan_model=cluster_model,
        min_topic_size=min_topic_size,
        verbose=False,
        calculate_probabilities=True,
        # Use a vectorizer with English stop words and a few project-specific tokens
        vectorizer_model=CountVectorizer(
            stop_words=list(sklearn_stop.ENGLISH_STOP_WORDS.union(
                {
                    # common pronouns / filler tokens that appeared as themes
                    "spotify",
                    "user",
                    "users",
                    "app",
                    "please",
                }
            )),
            ngram_range=(1, 2),
            min_df=5,
        ),
    )

    topics, probs = topic_model.fit_transform(documents, embeddings)

    clusters: list[ThemeCluster] = []
    unique_topics = sorted(set(topics))
    topic_info = topic_model.get_topic_info()

    for topic_id in unique_topics:
        if topic_id == -1:
            continue

        indices = [i for i, t in enumerate(topics) if t == topic_id]
        if not indices:
            continue

        row = topic_info[topic_info["Topic"] == topic_id]
        name = str(row["Name"].iloc[0]) if not row.empty else f"Topic {topic_id}"
        name = name.replace("_", " ").strip()
        if name.lower().startswith(str(topic_id)):
            words = topic_model.get_topic(topic_id) or []
            name = ", ".join(word for word, _ in words[:4]) or name

        # filter out stopwords/short tokens from topic keywords
        raw_keywords = [word for word, _ in (topic_model.get_topic(topic_id) or [])[:16]]
        stopset = set(sklearn_stop.ENGLISH_STOP_WORDS)
        extra_stop = {"spotify", "user", "users", "app", "please"}
        keywords = [w for w in raw_keywords if w and len(w) > 2 and w.lower() not in stopset | extra_stop][:8]
        topic_probs = []
        for idx in indices:
            if probs is not None and len(probs) > idx:
                prob_row = probs[idx]
                if hasattr(prob_row, "__len__") and len(prob_row) > topic_id:
                    topic_probs.append(float(prob_row[topic_id]))
                else:
                    topic_probs.append(1.0)
            else:
                topic_probs.append(1.0)

        clusters.append(
            ThemeCluster(
                topic_id=topic_id,
                name=name[:255],
                keywords=keywords,
                review_indices=indices,
                probabilities=topic_probs,
            )
        )

    logger.info("Discovered %s themes (excluding outliers)", len(clusters))
    return clusters, topic_model
