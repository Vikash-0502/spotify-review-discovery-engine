"""Keyword filters for discovery-related content."""

PRIMARY_KEYWORDS = [
    "discover weekly",
    "release radar",
    "daily mix",
    "daylist",
    "recommendation",
    "recommendations",
    "discover music",
    "music discovery",
    "find new music",
    "new music",
    "algorithm",
    "spotify algorithm",
    "smart shuffle",
    "song radio",
    "spotify radio",
    "made for you",
    "personalized",
    "for you",
]

SECONDARY_KEYWORDS = [
    "repetitive",
    "same songs",
    "same artist",
    "playlist",
    "skip",
    "genre",
    "explore",
    "bored",
    "shuffle",
    "suggestions",
    "discover",
    "feed",
    "home page",
    "spotify dj",
    "autoplay",
    "similar songs",
    "private session",
]

NEGATIVE_KEYWORDS = [
    "podcast",
    "audiobook",
    "payment",
    "billing",
    "login",
    "password",
    "offline",
    "download",
    "family plan",
    "advertisement",
]

SPOTIFY_SUBREDDITS = {"spotify", "truespotify", "spotifyplaylists"}


def is_discovery_related(text: str, *, spotify_source: bool = False) -> bool:
    """Return True if text matches discovery keyword rules."""
    if not text or len(text.strip()) < 20:
        return False

    text_lower = text.lower()
    primary_hits = sum(1 for kw in PRIMARY_KEYWORDS if kw in text_lower)
    secondary_hits = sum(1 for kw in SECONDARY_KEYWORDS if kw in text_lower)

    if primary_hits >= 1 or secondary_hits >= 2:
        return True

    # Spotify app store reviews: also accept clear recommendation/discovery wording
    if spotify_source and "spotify" in text_lower:
        if any(word in text_lower for word in ("recommend", "discover", "playlist", "algorithm", "shuffle")):
            return True

    return False


def passes_negative_filter(text: str) -> bool:
    """Return False if text is dominated by out-of-scope topics."""
    text_lower = text.lower()
    negative_hits = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text_lower)
    discovery_hits = sum(
        1 for kw in PRIMARY_KEYWORDS + SECONDARY_KEYWORDS if kw in text_lower
    )
    if negative_hits >= 2 and discovery_hits == 0:
        return False
    return True


def is_spotify_context(text: str, subreddit: str | None = None) -> bool:
    """Check if content is Spotify-related."""
    if subreddit and subreddit.lower().replace("r/", "") in SPOTIFY_SUBREDDITS:
        return True
    return "spotify" in text.lower()
