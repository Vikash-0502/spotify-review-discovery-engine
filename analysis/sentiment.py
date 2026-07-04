"""Sentiment classification using Hugging Face transformers."""

from utils.config import get_settings
from utils.logging import get_logger

logger = get_logger(__name__)

LABEL_MAP = {
    "negative": "negative",
    "neutral": "neutral",
    "positive": "positive",
    "label_0": "negative",
    "label_1": "neutral",
    "label_2": "positive",
}


def _get_pipeline():
    from transformers import pipeline

    settings = get_settings()
    logger.info("Loading sentiment model: %s", settings.sentiment_model)
    return pipeline(
        "sentiment-analysis",
        model=settings.sentiment_model,
        truncation=True,
        max_length=512,
        device=-1,
    )


def classify_sentiments(texts: list[str], batch_size: int = 32) -> list[str]:
    if not texts:
        return []

    pipe = _get_pipeline()
    results = pipe(texts, batch_size=batch_size)
    labels = []
    for result in results:
        raw = result["label"].lower()
        labels.append(LABEL_MAP.get(raw, "neutral"))
    return labels
