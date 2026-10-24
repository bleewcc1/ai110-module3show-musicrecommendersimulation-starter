"""
Command line runner for the Music Recommender Simulation.

This file helps you quickly run and test your recommender.

You will implement the functions in recommender.py:
- load_songs
- score_song
- recommend_songs
"""

import argparse
import textwrap

try:  # python -m src.main
    from .recommender import (
        DEFAULT_STRATEGY, STRATEGY_DESCRIPTIONS, STRATEGY_NAMES,
        confidence_warnings, load_songs, profile_coverage, recommend_songs,
    )
except ImportError:  # python src/main.py
    from recommender import (
        DEFAULT_STRATEGY, STRATEGY_DESCRIPTIONS, STRATEGY_NAMES,
        confidence_warnings, load_songs, profile_coverage, recommend_songs,
    )


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

# Uses the extra song attributes: release decade, detailed mood tags, popularity,
# language and instrumentalness. It likes moody, neon-lit instrumentals from the 2010s
# that are not too famous.
NOSTALGIC_NIGHT_DRIVE_PROFILE = {
    "favorite_genre": "synthwave",
    "favorite_mood": "nostalgic",
    "target_energy": 0.70,
    "likes_acoustic": False,
    "preferred_decade": 2010,
    "favorite_mood_tags": ["nostalgic", "neon", "late-night"],
    "target_popularity": 55,
    "preferred_language": "instrumental",
    "target_instrumentalness": 0.80,
}

PROFILES = {
    "Chill Lofi": TASTE_PROFILE,
    "Intense Rock": INTENSE_ROCK_PROFILE,
    "High-Energy Pop": HIGH_ENERGY_POP_PROFILE,
    "Pop Happy": POP_HAPPY_PROFILE,
    "Nostalgic Night Drive": NOSTALGIC_NIGHT_DRIVE_PROFILE,
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
# Table layout: column widths in characters (the borders add 16 more).
TABLE_WIDTHS = (2, 19, 15, 6, 52)
TABLE_HEADERS = ("#", "Title", "Artist", "Score", "Why (reasons)")
FORMATS = ("table", "detailed")
DEFAULT_FORMAT = "table"
# Diversity rules. "penalty" (default) is soft: each song loses GENRE_PENALTY for every song of
# its genre already in the list and ARTIST_PENALTY for every song by its artist. "artist" is the
# same penalty for repeated artists only. "cap" is hard: no more than this many songs of one
# genre or by one artist. "off" turns all of them off.
GENRE_PENALTY = 0.08
ARTIST_PENALTY = 0.12
MAX_PER_GENRE = 2
MAX_PER_ARTIST = 2
DIVERSITY_MODES = ("penalty", "artist", "cap", "off")
DEFAULT_DIVERSITY = "penalty"


def diversity_options(mode: str) -> dict:
    """The recommend_songs() arguments for a diversity mode."""
    if mode == "penalty":
        return {"genre_penalty": GENRE_PENALTY, "artist_penalty": ARTIST_PENALTY}
    if mode == "artist":
        return {"artist_penalty": ARTIST_PENALTY}
    if mode == "cap":
        return {"max_per_genre": MAX_PER_GENRE, "max_per_artist": MAX_PER_ARTIST}
    return {}


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


def _wrap(text: str, width: int, bullet: str = "") -> list:
    """Wraps text to width; a bullet goes on the first line and later lines are indented under it."""
    lines = textwrap.wrap(text, width, initial_indent=bullet, subsequent_indent=" " * len(bullet))
    return lines or [""]


def format_table(results: list) -> str:
    """
    The recommendations as an ASCII table: rank, title, artist, score and the reasons behind
    the score (one per line), followed by a one-line summary.
    """
    widths = TABLE_WIDTHS
    border = "+" + "+".join("-" * (w + 2) for w in widths) + "+"

    def line(cells: list) -> list:
        height = max(len(cell) for cell in cells)
        padded = [cell + [""] * (height - len(cell)) for cell in cells]
        return ["| " + " | ".join(text.ljust(w) for text, w in zip(row, widths)) + " |"
                for row in zip(*padded)]

    lines = [border, *line([[h] for h in TABLE_HEADERS]), border]
    for rank, (song, score, explanation) in enumerate(results, start=1):
        reasons = [wrapped for reason in explanation.split("; ") for wrapped in _wrap(reason, widths[4], "- ")]
        score_cell = [f"{score:.2f}"] + (["weak"] if score < WEAK_SCORE else [])
        lines += line([[str(rank)], _wrap(song["title"], widths[1]), _wrap(song["artist"], widths[2]),
                       score_cell, reasons])
        lines.append(border)
    if results:
        genres = list(dict.fromkeys(song["genre"] for song, _, _ in results))
        artists = {song["artist"] for song, _, _ in results}
        average = sum(score for _, score, _ in results) / len(results)
        lines.append(f"Summary: average score {average:.2f} | {len(genres)} genres ({', '.join(genres)}) "
                     f"| {len(artists)} artists")
    return "\n".join(lines)


def format_comparison(name: str, user_prefs: dict, songs: list, diversity: str = DEFAULT_DIVERSITY) -> str:
    """The top 5 titles for one profile under every strategy, side by side."""
    columns = {
        strategy: [song["title"] for song, _, _ in recommend_songs(
            user_prefs, songs, k=TOP_K, strategy=strategy, **diversity_options(diversity))]
        for strategy in STRATEGY_NAMES
    }
    col = 22
    lines = ["\n" + "=" * WIDTH, f"  {name}: {format_profile(user_prefs)}", "=" * WIDTH,
             "     " + "".join(strategy.ljust(col) for strategy in STRATEGY_NAMES)]
    for rank in range(TOP_K):
        row = "".join((titles[rank] if rank < len(titles) else "").ljust(col) for titles in columns.values())
        lines.append(f"  {rank + 1}. {row}".rstrip())
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Music Recommender Simulation")
    parser.add_argument("--strategy", choices=STRATEGY_NAMES, default=DEFAULT_STRATEGY,
                        help="ranking mode (default: %(default)s)")
    parser.add_argument("--diversity", choices=DIVERSITY_MODES, default=DEFAULT_DIVERSITY,
                        help="how to avoid repeating a genre or artist (default: %(default)s)")
    parser.add_argument("--format", choices=FORMATS, default=DEFAULT_FORMAT,
                        help="how to print results: a table, or a detailed list (default: %(default)s)")
    parser.add_argument("--compare", action="store_true",
                        help="show the top 5 titles under every strategy side by side")
    parser.add_argument("--list-strategies", action="store_true", help="describe the ranking modes and exit")
    parser.add_argument("--adversarial", action="store_true", help="also run the edge-case profiles")
    return parser


def main(argv: list = None) -> None:
    args = build_parser().parse_args(argv)
    if args.list_strategies:
        for strategy in STRATEGY_NAMES:
            print(f"{strategy:<15} {STRATEGY_DESCRIPTIONS[strategy]}")
        return
    songs = load_songs("data/songs.csv")
    profiles = {**PROFILES, **ADVERSARIAL_PROFILES} if args.adversarial else PROFILES

    if args.adversarial:
        for name, user_prefs in INVALID_PROFILES.items():
            try:
                recommend_songs(user_prefs, songs, k=TOP_K)
            except ValueError as error:
                print(f"Rejected invalid profile '{name}': {error}")

    if args.compare:
        for name, user_prefs in profiles.items():
            print(format_comparison(name, user_prefs, songs, args.diversity))
        print()
        return

    print(f"Ranking strategy: {args.strategy} ({STRATEGY_DESCRIPTIONS[args.strategy]})")
    print(f"Diversity: {args.diversity}")
    for name, user_prefs in profiles.items():
        print("\n" + "=" * WIDTH)
        print(f"  {name}: {format_profile(user_prefs)}")
        print("=" * WIDTH)

        coverage = profile_coverage(user_prefs, songs)
        if coverage < TOP_K:
            print(f"! Profile may be too narrow: only {coverage} songs match genre or mood "
                  f"(fewer than the {TOP_K} requested).")

        results = recommend_songs(user_prefs, songs, k=TOP_K, strategy=args.strategy,
                                  **diversity_options(args.diversity))
        for warning in confidence_warnings(user_prefs, songs, results):
            print(f"! Low confidence: {warning}.")

        if args.format == "table":
            print("\n" + format_table(results))
        else:
            for rank, (song, score, explanation) in enumerate(results, start=1):
                print("\n" + format_recommendation(rank, song, score, explanation))
        print()


if __name__ == "__main__":
    main()
