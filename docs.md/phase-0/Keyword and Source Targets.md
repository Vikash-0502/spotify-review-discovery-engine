# Phase 0 — Keyword & Source Target List

**Date:** 2026-06-27  
**Purpose:** Task 0.4 — Define search keywords, subreddits, forum boards, and filters for discovery-focused data collection.

---

## Collection Filter Logic

A record is **in-scope** if its text matches ≥ 1 primary keyword OR ≥ 2 secondary keywords, AND relates to Spotify (explicit mention or collected from a Spotify-specific source).

---

## Primary Keywords (High Relevance)

These directly indicate music discovery or recommendation feedback:

| Keyword / Phrase | Rationale |
|---|---|
| `discover weekly` | Flagship discovery feature — high complaint volume |
| `release radar` | Secondary personalized discovery feed |
| `daily mix` | Personalized playlist feature |
| `daylist` | Mood/time-based discovery feature |
| `recommendation` | Core topic |
| `recommendations` | Plural variant |
| `discover music` | Explicit discovery intent |
| `music discovery` | Explicit discovery intent |
| `find new music` | User goal language |
| `new music` | Discovery-related |
| `algorithm` | Algorithm complaints |
| `spotify algorithm` | Direct algorithm reference |
| `smart shuffle` | Feature-specific complaints |
| `song radio` | Radio-based discovery |
| `spotify radio` | Radio-based discovery |
| `made for you` | Personalized section |
| `personalized` | Personalization feedback |
| `for you` | Feed section reference |

---

## Secondary Keywords (Supporting Relevance)

| Keyword / Phrase | Rationale |
|---|---|
| `repetitive` | Echo chamber / repetition complaints |
| `same songs` | Repetition complaints |
| `same artist` | Lack of variety |
| `playlist` | User-curated vs. algorithmic context |
| `skip` | Feedback loop failures |
| `genre` | Genre exploration issues |
| `explore` | Exploration intent |
| `bored` | Discovery fatigue |
| `shuffle` | Playback/discovery mode |
| `suggestions` | Recommendation synonyms |
| `discover` | Short-form discovery reference |
| `feed` | Home feed / recommendation feed |
| `home page` | Discovery entry point |
| `spotify dj` | AI DJ feature |
| `autoplay` | Passive discovery behavior |
| `similar songs` | Recommendation continuation |
| `private session` | Exploration anxiety workaround |

---

## Negative Keywords (Exclude or Deprioritize)

| Keyword | Reason |
|---|---|
| `podcast` | Out of scope unless tied to music discovery |
| `audiobook` | Out of scope |
| `payment` / `billing` | Not discovery-related |
| `login` / `password` | Technical support, not discovery |
| `offline` / `download` | Feature unrelated to discovery |
| `family plan` | Pricing, not discovery |
| `ads` / `advertisement` | Free tier complaints — deprioritize unless tied to discovery |

---

## Reddit Targets

### Primary Subreddits

| Subreddit | Expected Content | Collection Method |
|---|---|---|
| [r/spotify](https://reddit.com/r/spotify) | General complaints, feature feedback, discovery threads | Search + hot/top/year |
| [r/truespotify](https://reddit.com/r/truespotify) | Critical/discussion-focused Spotify feedback | Search + top/year |
| [r/spotifyplaylists](https://reddit.com/r/spotifyplaylists) | Playlist and discovery behavior | Keyword search only |

### Reddit Search Queries (PRAW)

```
subreddit:spotify (discover weekly OR recommendations OR algorithm OR "find new music")
subreddit:spotify ("same songs" OR repetitive OR "smart shuffle")
subreddit:truespotify (discovery OR recommendations OR algorithm)
subreddit:spotify (daylist OR "release radar" OR "daily mix")
subreddit:spotify ("private session" OR "explore new" OR genre)
```

### Reddit Collection Parameters

| Parameter | Value |
|---|---|
| Sort | `relevance`, `top` (time_filter=`year`), `new` |
| Limit per query | 100–500 posts |
| Comments | Expand all comment trees (`replace_more(limit=0)`) |
| Min comment length | 20 characters (filter noise) |
| Target volume | 500–1,500 records |

---

## Spotify Community Targets

**Base URL:** `https://community.spotify.com`

### Target Boards

| Board | URL Path | Focus |
|---|---|---|
| Content Questions | `/c/content-questions/` | Recommendation quality, algorithm complaints |
| Live Ideas | `/c/live-ideas/` | Feature requests for discovery |
| Your Library | `/c/your-library/` | Library and playlist management |
| Help — Android | `/c/spotify-android/` | App experience including discovery |
| Help — iOS | `/c/spotify-ios/` | App experience including discovery |

### Forum Search Queries

```
recommendations algorithm
discover weekly
find new music
repetitive songs
smart shuffle
release radar
daily mix
music discovery
song radio
```

### Collection Parameters

| Parameter | Value |
|---|---|
| Endpoint | `/search.json?q={query}` |
| Max topics per query | 50 |
| Include replies | Yes — fetch full thread via `/t/{id}.json` |
| Delay between requests | 1 second |
| Target volume | 300–800 posts |

---

## App Store Review Targets

### Google Play Store

| Parameter | Value |
|---|---|
| App ID | `com.spotify.music` |
| Language | `en` |
| Countries | `us`, `gb` (optional) |
| Sort orders | `NEWEST`, `MOST_RELEVANT` |
| Star filter | All ratings (1–5) — sentiment diversity |
| Post-filter | Apply primary/secondary keyword match on review body |
| Target volume | 500–1,500 reviews |

### Apple App Store

| Parameter | Value |
|---|---|
| App ID | `324684580` |
| Country | `us` |
| Sort | `mostRecent`, `mostHelpful` |
| Max reviews | 500 per sort (Apple RSS cap) |
| Post-filter | Apply keyword match on title + content |
| Target volume | 400–600 discovery-related reviews |

---

## Keyword Match Implementation (Phase 2)

```python
PRIMARY_KEYWORDS = [
    "discover weekly", "release radar", "daily mix", "daylist",
    "recommendation", "music discovery", "find new music",
    "algorithm", "smart shuffle", "song radio", "made for you",
]

SECONDARY_KEYWORDS = [
    "repetitive", "same songs", "same artist", "playlist",
    "skip", "genre", "explore", "bored", "shuffle",
    "suggestions", "spotify dj", "autoplay", "private session",
]

def is_discovery_related(text: str) -> bool:
    text_lower = text.lower()
    primary_hits = sum(1 for kw in PRIMARY_KEYWORDS if kw in text_lower)
    secondary_hits = sum(1 for kw in SECONDARY_KEYWORDS if kw in text_lower)
    return primary_hits >= 1 or secondary_hits >= 2
```

---

## Expected Volume After Filtering

| Source | Raw Pull | After Keyword Filter | Target |
|---|---|---|---|
| Google Play | 2,000–3,000 | 500–1,000 | ✓ |
| Apple App Store | 800–1,000 | 400–600 | ✓ |
| Reddit | 800–2,000 | 500–1,200 | ✓ |
| Spotify Community | 400–600 | 300–500 | ✓ |
| **Total** | **4,000–6,600** | **1,700–3,300** | **2,000–5,000 ✓** |

---

## Exit Criteria

- [x] Primary and secondary keyword lists defined
- [x] Reddit subreddits and search queries specified
- [x] Spotify Community boards and search queries specified
- [x] App store collection parameters documented
- [x] Volume estimates confirm 2,000–5,000 target is achievable
