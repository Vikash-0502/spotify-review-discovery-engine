"""Data collection modules for public review sources."""

from collectors.app_store import collect_app_store
from collectors.play_store import collect_play_store
from collectors.reddit_collector import collect_reddit
from collectors.spotify_community import collect_spotify_community

__all__ = [
    "collect_play_store",
    "collect_app_store",
    "collect_reddit",
    "collect_spotify_community",
]
