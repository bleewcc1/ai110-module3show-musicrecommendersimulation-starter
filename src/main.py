"""
Command line runner for the Music Recommender Simulation.

This file helps you quickly run and test your recommender.

You will implement the functions in recommender.py:
- load_songs
- score_song
- recommend_songs
"""

try:  # python -m src.main
    from .recommender import load_songs, profile_coverage, recommend_songs
except ImportError:  # python src/main.py
    from recommender import load_songs, profile_coverage, recommend_songs


# Taste profile: "Late-Night Study Listener".
# Wants calm, low-key, mostly acoustic music to concentrate to, not to dance to.
# - favorite_genre/favorite_mood: exact-match categories (lofi / chill are the most common pair in the catalog)
# - target_energy: ~0.40; Gaussian closeness penalizes songs that are too loud OR too sleepy
# - likes_acoustic: prefers organic sounds over electronic production
TASTE_PROFILE = {
    "favorite_genre": "lofi",
    "favorite_mood": "chill",
    "target_energy": 0.40,
    "likes_acoustic": True,
    "target_tempo": 78.0,
    "target_valence": 0.58,
    "target_danceability": 0.60,
}


# Contrasting profile: loud, fast, aggressive listener. Together with TASTE_PROFILE it
# lets us check that the recommender separates "chill lofi" from "intense rock".
INTENSE_ROCK_PROFILE = {
    "favorite_genre": "rock",
    "favorite_mood": "intense",
    "target_energy": 0.92,
    "likes_acoustic": False,
    "target_tempo": 155.0,
    "target_valence": 0.45,
    "target_danceability": 0.65,
}

# The original starter profile: genre, mood and energy only (no acoustic preference or
# tempo / valence / danceability targets), so it scores lower than the richer profiles.
POP_HAPPY_PROFILE = {
    "favorite_genre": "pop",
    "favorite_mood": "happy",
    "target_energy": 0.80,
}

PROFILES = {
    "Chill Lofi": TASTE_PROFILE,
    "Intense Rock": INTENSE_ROCK_PROFILE,
    "Pop Happy": POP_HAPPY_PROFILE,
}

TOP_K = 5
WIDTH = 64
BAR_WIDTH = 20


def format_profile(user_prefs: dict) -> str:
    """One-line summary of what the profile is asking for."""
    parts = [user_prefs["favorite_genre"], user_prefs["favorite_mood"],
             f"energy {user_prefs['target_energy']:.2f}"]
    if user_prefs.get("likes_acoustic") is not None:
        parts.append("acoustic" if user_prefs["likes_acoustic"] else "not acoustic")
    return " / ".join(parts)


def format_recommendation(rank: int, song: dict, score: float, explanation: str) -> str:
    """One result: rank, title, artist, score bar, then one bullet per reason."""
    filled = round(score * BAR_WIDTH)
    bar = "#" * filled + "." * (BAR_WIDTH - filled)
    lines = [
        f"{rank}. {song['title']}  (by {song['artist']})",
        f"   Score {score:.2f}  [{bar}]",
        "   Why:",
    ]
    lines += [f"     - {reason}" for reason in explanation.split("; ")]
    return "\n".join(lines)


def main() -> None:
    songs = load_songs("data/songs.csv")

    for name, user_prefs in PROFILES.items():
        print("\n" + "=" * WIDTH)
        print(f"  {name}: {format_profile(user_prefs)}")
        print("=" * WIDTH)

        coverage = profile_coverage(user_prefs, songs)
        if coverage < TOP_K:
            print(f"! Profile may be too narrow: only {coverage} songs match genre or mood "
                  f"(fewer than the {TOP_K} requested).")

        for rank, (song, score, explanation) in enumerate(
            recommend_songs(user_prefs, songs, k=TOP_K), start=1
        ):
            print("\n" + format_recommendation(rank, song, score, explanation))
        print()


if __name__ == "__main__":
    main()
