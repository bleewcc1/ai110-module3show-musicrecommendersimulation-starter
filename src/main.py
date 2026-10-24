"""
Command line runner for the Music Recommender Simulation.

This file helps you quickly run and test your recommender.

You will implement the functions in recommender.py:
- load_songs
- score_song
- recommend_songs
"""

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
    "target_tempo": 78,
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
    "target_tempo": 155,
    "target_valence": 0.45,
    "target_danceability": 0.65,
}

PROFILES = {
    "Chill Lofi": TASTE_PROFILE,
    "Intense Rock": INTENSE_ROCK_PROFILE,
}

TOP_K = 5


def main() -> None:
    songs = load_songs("data/songs.csv")

    for name, user_prefs in PROFILES.items():
        print(f"\n=== {name} ===")
        coverage = profile_coverage(user_prefs, songs)
        if coverage < TOP_K:
            print(f"Warning: profile may be too narrow, only {coverage} songs match genre or mood "
                  f"(fewer than the {TOP_K} requested).")

        for song, score, explanation in recommend_songs(user_prefs, songs, k=TOP_K):
            print(f"{song['title']} - Score: {score:.2f}")
            print(f"Because: {explanation}")
            print()


if __name__ == "__main__":
    main()
