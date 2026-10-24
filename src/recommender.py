import csv
import math
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict

@dataclass
class Song:
    """
    Represents a song and its attributes.
    Required by tests/test_recommender.py
    """
    id: int
    title: str
    artist: str
    genre: str
    mood: str
    energy: float
    tempo_bpm: float
    valence: float
    danceability: float
    acousticness: float

@dataclass
class UserProfile:
    """
    Represents a user's taste preferences.
    Required by tests/test_recommender.py
    """
    favorite_genre: str
    favorite_mood: str
    target_energy: float
    likes_acoustic: bool
    target_tempo: Optional[float] = None
    target_valence: Optional[float] = None
    target_danceability: Optional[float] = None

# Algorithm Recipe: weighted sum, gated when neither genre nor mood matches.
# Weights sum to 1.0. The last three are optional: they only count when the profile
# supplies a target_tempo / target_valence / target_danceability.
WEIGHTS = {
    "genre": 0.28, "mood": 0.22, "energy": 0.28, "acoustic": 0.12,
    "tempo": 0.04, "valence": 0.03, "danceability": 0.03,
}
NO_MATCH_PENALTY = 0.5
# Fraction of the genre/mood weight earned by a related (not identical) genre or mood.
NEAR_MATCH_CREDIT = 0.5
# Width of the Gaussian closeness curve per numeric feature: smaller = pickier.
ENERGY_SIGMA = 0.25
TEMPO_SIGMA = 25.0
VALENCE_SIGMA = 0.25
DANCEABILITY_SIGMA = 0.25

# Related labels that earn partial credit instead of nothing.
GENRE_FAMILIES = [
    {"pop", "indie pop"},
    {"rock", "metal"},
    {"lofi", "ambient", "jazz"},
    {"folk", "country", "blues"},
    {"edm", "synthwave"},
]
MOOD_FAMILIES = [
    {"chill", "relaxed", "peaceful", "laid-back", "focused"},
    {"intense", "aggressive"},
    {"happy", "euphoric", "festive"},
    {"melancholy", "sorrowful", "nostalgic"},
]


def closeness(target: float, value: float, sigma: float) -> float:
    """
    Gaussian similarity in [0, 1]: 1.0 at the target, falling smoothly as the
    value moves away in either direction. Rewards closeness, not high/low.
    """
    return math.exp(-((value - target) ** 2) / (2 * sigma ** 2))


def label_match(target: Optional[str], value: str, families: List[set]) -> str:
    """Returns "exact", "near" (same family), or "none"."""
    if target is None:
        return "none"
    if value == target:
        return "exact"
    if any(target in family and value in family for family in families):
        return "near"
    return "none"


def score_song(user_prefs: Dict, song: Dict) -> Tuple[float, List[str]]:
    """
    Scores a single song against user preferences.
    Required by recommend_songs() and src/main.py

    user_prefs keys: favorite_genre, favorite_mood, target_energy, and optionally
    likes_acoustic (bool), target_tempo, target_valence, target_danceability.
    The short names genre, mood, energy are also accepted.
    Returns (score between 0 and 1, list of reasons).
    """
    reasons: List[str] = []
    score = 0.0

    favorite_genre = user_prefs.get("favorite_genre", user_prefs.get("genre"))
    favorite_mood = user_prefs.get("favorite_mood", user_prefs.get("mood"))
    target_energy = user_prefs.get("target_energy", user_prefs.get("energy"))

    genre_match = label_match(favorite_genre, song["genre"], GENRE_FAMILIES)
    if genre_match == "exact":
        score += WEIGHTS["genre"]
        reasons.append(f"genre match ({song['genre']}) +{WEIGHTS['genre']:.2f}")
    elif genre_match == "near":
        points = WEIGHTS["genre"] * NEAR_MATCH_CREDIT
        score += points
        reasons.append(f"related genre ({song['genre']} ~ {favorite_genre}) +{points:.2f}")

    mood_match = label_match(favorite_mood, song["mood"], MOOD_FAMILIES)
    if mood_match == "exact":
        score += WEIGHTS["mood"]
        reasons.append(f"mood match ({song['mood']}) +{WEIGHTS['mood']:.2f}")
    elif mood_match == "near":
        points = WEIGHTS["mood"] * NEAR_MATCH_CREDIT
        score += points
        reasons.append(f"related mood ({song['mood']} ~ {favorite_mood}) +{points:.2f}")

    if target_energy is not None:
        fit = closeness(target_energy, song["energy"], ENERGY_SIGMA)
        points = WEIGHTS["energy"] * fit
        score += points
        reasons.append(f"energy {song['energy']:.2f} vs target {target_energy:.2f} +{points:.2f}")

    likes_acoustic = user_prefs.get("likes_acoustic")
    if likes_acoustic is not None:
        fit = song["acousticness"] if likes_acoustic else 1 - song["acousticness"]
        points = WEIGHTS["acoustic"] * fit
        score += points
        reasons.append(f"acoustic fit +{points:.2f}")

    # Optional small terms; they also separate songs that would otherwise tie.
    for key, column, sigma in (
        ("tempo", "tempo_bpm", TEMPO_SIGMA),
        ("valence", "valence", VALENCE_SIGMA),
        ("danceability", "danceability", DANCEABILITY_SIGMA),
    ):
        target = user_prefs.get(f"target_{key}")
        if target is not None:
            points = WEIGHTS[key] * closeness(target, song[column], sigma)
            score += points
            reasons.append(f"{key} {song[column]} vs target {target} +{points:.2f}")

    if genre_match == "none" and mood_match == "none":
        score *= NO_MATCH_PENALTY
        reasons.append(f"closest fit only: no genre or mood match, score x{NO_MATCH_PENALTY}")

    return score, reasons


def profile_coverage(user_prefs: Dict, songs: List[Dict]) -> int:
    """
    Counts songs whose genre or mood matches, exactly or as a relative (i.e. escape the
    NO_MATCH_PENALTY). A low count means the profile is too narrow for the catalog.
    """
    genre = user_prefs.get("favorite_genre", user_prefs.get("genre"))
    mood = user_prefs.get("favorite_mood", user_prefs.get("mood"))
    return sum(
        1 for s in songs
        if label_match(genre, s["genre"], GENRE_FAMILIES) != "none"
        or label_match(mood, s["mood"], MOOD_FAMILIES) != "none"
    )


def recommend_songs(user_prefs: Dict, songs: List[Dict], k: int = 5) -> List[Tuple[Dict, float, str]]:
    """
    Functional implementation of the recommendation logic.
    Required by src/main.py
    Returns the top k as (song_dict, score, explanation), best first.
    """
    scored = []
    for song in songs:
        score, reasons = score_song(user_prefs, song)
        scored.append((song, score, "; ".join(reasons)))
    # Best score first; equal scores fall back to title so order is reproducible.
    scored.sort(key=lambda item: (-item[1], item[0]["title"]))
    return scored[:k]


def load_songs(csv_path: str) -> List[Dict]:
    """
    Loads songs from a CSV file, converting numeric columns.
    Required by src/main.py
    """
    int_fields = ("id", "tempo_bpm")
    float_fields = ("energy", "valence", "danceability", "acousticness")
    songs = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            for key in int_fields:
                row[key] = int(row[key])
            for key in float_fields:
                row[key] = float(row[key])
            songs.append(row)
    return songs


class Recommender:
    """
    OOP implementation of the recommendation logic.
    Required by tests/test_recommender.py
    """
    def __init__(self, songs: List[Song]):
        self.songs = songs

    @staticmethod
    def _prefs(user: UserProfile) -> Dict:
        return {
            "favorite_genre": user.favorite_genre,
            "favorite_mood": user.favorite_mood,
            "target_energy": user.target_energy,
            "likes_acoustic": user.likes_acoustic,
            "target_tempo": user.target_tempo,
            "target_valence": user.target_valence,
            "target_danceability": user.target_danceability,
        }

    def recommend(self, user: UserProfile, k: int = 5) -> List[Song]:
        prefs = self._prefs(user)
        ranked = sorted(
            self.songs,
            key=lambda s: (-score_song(prefs, asdict(s))[0], s.title),
        )
        return ranked[:k]

    def explain_recommendation(self, user: UserProfile, song: Song) -> str:
        score, reasons = score_song(self._prefs(user), asdict(song))
        return f"Score {score:.2f}: " + "; ".join(reasons)
