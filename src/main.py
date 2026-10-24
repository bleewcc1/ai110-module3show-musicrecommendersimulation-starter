"""
Command line runner for the Music Recommender Simulation.

This file helps you quickly run and test your recommender.

You will implement the functions in recommender.py:
- load_songs
- score_song
- recommend_songs
"""

import sys

try:  # python -m src.main
    from .recommender import confidence_warnings, load_songs, profile_coverage, recommend_songs
except ImportError:  # python src/main.py
    from recommender import confidence_warnings, load_songs, profile_coverage, recommend_songs


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

# Upbeat party listener: bright, fast, danceable, electronic-sounding pop.
HIGH_ENERGY_POP_PROFILE = {
    "favorite_genre": "pop",
    "favorite_mood": "happy",
    "target_energy": 0.88,
    "likes_acoustic": False,
    "target_tempo": 125.0,
    "target_valence": 0.85,
    "target_danceability": 0.85,
}

PROFILES = {
    "Chill Lofi": TASTE_PROFILE,
    "Intense Rock": INTENSE_ROCK_PROFILE,
    "High-Energy Pop": HIGH_ENERGY_POP_PROFILE,
    "Pop Happy": POP_HAPPY_PROFILE,
}

# Adversarial / edge-case profiles (run with --adversarial): conflicting or unusual
# preferences meant to expose where the scoring logic can be tricked. Invalid numeric
# targets live in INVALID_PROFILES because the scorer rejects them.
ADVERSARIAL_PROFILES = {
    "Sad Ravers": {"favorite_genre": "pop", "favorite_mood": "sad", "target_energy": 0.9,
                   "likes_acoustic": False},
    "Typo Lofi": {"favorite_genre": " Lofi ", "favorite_mood": "CHILL", "target_energy": 0.4},
    "Metalhead Sleeper": {"favorite_genre": "metal", "favorite_mood": "peaceful",
                          "target_energy": 0.1, "likes_acoustic": True},
    "Sad Sunshine": {"favorite_genre": "folk", "favorite_mood": "melancholy", "target_energy": 0.3,
                     "likes_acoustic": True, "target_valence": 0.95},
    "Unknown Tastes": {"favorite_genre": "polka", "favorite_mood": "zany", "target_energy": 0.5},
    "Empty Profile": {"favorite_genre": None, "favorite_mood": None, "target_energy": 0.5},
}

INVALID_PROFILES = {
    "Energy Too High": {"favorite_genre": "rock", "favorite_mood": "intense", "target_energy": 1.5},
    "Energy Negative": {"favorite_genre": "lofi", "favorite_mood": "chill", "target_energy": -1.0},
    "Absurd Tempo": {"favorite_genre": "pop", "favorite_mood": "happy", "target_energy": 0.8,
                     "target_tempo": 400},
}

TOP_K = 5
WIDTH = 64
BAR_WIDTH = 20
# Scores below this are fallbacks (usually no genre or mood match), so flag them.
WEAK_SCORE = 0.40
# Diversity rule: no more than this many songs of one genre or by one artist per list.
MAX_PER_GENRE = 2
MAX_PER_ARTIST = 2


def format_profile(user_prefs: dict) -> str:
    """One-line summary of what the profile is asking for."""
    parts = [user_prefs["favorite_genre"] or "any genre", user_prefs["favorite_mood"] or "any mood",
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
        f"   Score {score:.2f}  [{bar}]" + ("  (weak match)" if score < WEAK_SCORE else ""),
        "   Why:",
    ]
    lines += [f"     - {reason}" for reason in explanation.split("; ")]
    return "\n".join(lines)


def main(argv: list = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    songs = load_songs("data/songs.csv")
    profiles = {**PROFILES, **ADVERSARIAL_PROFILES} if "--adversarial" in argv else PROFILES

    if "--adversarial" in argv:
        for name, user_prefs in INVALID_PROFILES.items():
            try:
                recommend_songs(user_prefs, songs, k=TOP_K)
            except ValueError as error:
                print(f"Rejected invalid profile '{name}': {error}")

    for name, user_prefs in profiles.items():
        print("\n" + "=" * WIDTH)
        print(f"  {name}: {format_profile(user_prefs)}")
        print("=" * WIDTH)

        coverage = profile_coverage(user_prefs, songs)
        if coverage < TOP_K:
            print(f"! Profile may be too narrow: only {coverage} songs match genre or mood "
                  f"(fewer than the {TOP_K} requested).")

        results = recommend_songs(user_prefs, songs, k=TOP_K, max_per_genre=MAX_PER_GENRE,
                                  max_per_artist=MAX_PER_ARTIST)
        for warning in confidence_warnings(user_prefs, songs, results):
            print(f"! Low confidence: {warning}.")

        for rank, (song, score, explanation) in enumerate(results, start=1):
            print("\n" + format_recommendation(rank, song, score, explanation))
        print()


if __name__ == "__main__":
    main()
