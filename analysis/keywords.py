"""Local keyword extraction using embedding similarity (zero-cost).

Creates candidate n-grams from cluster documents, embeds each candidate using
the project's embedding model, then ranks candidates by cosine similarity to
the cluster centroid embedding. This avoids external LLMs and works offline.
"""
from typing import List
import logging

import numpy as np
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.feature_extraction import _stop_words as sklearn_stop

from analysis.embeddings import encode_texts, cosine_similarity

logger = logging.getLogger(__name__)


def extract_keywords_from_vectors(
    documents: List[str],
    member_embeddings: np.ndarray,
    top_k: int = 8,
    ngram_range=(1, 2),
    max_candidates: int = 256,
) -> List[str]:
    """Return top-k candidate keywords/phrases for a cluster.

    - `documents`: list of texts belonging to the cluster (representative reviews)
    - `member_embeddings`: array shape (n_members, dim) of review embeddings
    """
    if not documents or member_embeddings is None or len(member_embeddings) == 0:
        return []

    try:
        stopset = set(sklearn_stop.ENGLISH_STOP_WORDS)
        vect = CountVectorizer(stop_words=list(stopset), ngram_range=ngram_range)
        X = vect.fit_transform(documents)
        candidates = np.array(vect.get_feature_names_out())

        # If too many candidates, pick the top by document frequency
        freqs = np.asarray(X.sum(axis=0)).ravel()
        order = np.argsort(-freqs)
        if len(order) == 0:
            return []
        chosen_idx = order[: max_candidates]
        chosen_candidates = candidates[chosen_idx].tolist()

        # Embed candidates using the same encoder (batch)
        candidate_embeddings = encode_texts(chosen_candidates, batch_size=64)

        # centroid of cluster
        centroid = np.mean(member_embeddings, axis=0)

        # compute cosine similarities
        sims = [cosine_similarity(centroid, ce) for ce in candidate_embeddings]
        sims = np.asarray(sims)

        # pick top_k by similarity, filter short tokens
        ranking = np.argsort(-sims)
        keywords = []
        for idx in ranking:
            kw = chosen_candidates[int(idx)]
            if not kw or len(kw) <= 2:
                continue
            # skip pure stopwords
            if kw.lower() in stopset:
                continue
            keywords.append(kw)
            if len(keywords) >= top_k:
                break

        return keywords
    except Exception:
        logger.exception("Local keyword extraction failed")
        return []
