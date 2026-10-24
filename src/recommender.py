import csv
import math
from collections import Counter
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
# EXPERIMENT (weight shift): genre halved (0.28 -> 0.14), energy doubled (0.28 -> 0.56).
# The raw values now sum to 1.28, so they are rescaled to sum to exactly 1.0, which keeps
# every score in [0, 1]. The last three are optional: they only count when the profile
# supplies a target_tempo / target_valence / target_danceability.
_RAW_WEIGHTS = {
    "genre": 0.14, "mood": 0.22, "energy": 0.56, "acoustic": 0.12,
    "tempo": 0.04, "valence": 0.03, "danceability": 0.03,
}
WEIGHTS = {name: value / sum(_RAW_WEIGHTS.values()) for name, value in _RAW_WEIGHTS.items()}
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
    {"intense", "aggressive", "angry"},
    {"happy", "euphoric", "festive", "upbeat"},
    {"melancholy", "sorrowful", "nostalgic", "sad"},
]

# Numeric targets must sit in these ranges; anything else is rejected, not silently scored.
UNIT_RANGE_TARGETS = ("target_energy", "target_valence", "target_danceability")
TEMPO_RANGE = (20.0, 300.0)
# A best score under this means even the top pick is a weak fit for the profile.
LOW_CONFIDENCE_SCORE = 0.4


def closeness(target: float, value: float, sigma: float) -> float:
    """
    Gaussian similarity in [0, 1]: 1.0 at the target, falling smoothly as the
    value moves away in either direction. Rewards closeness, not high/low.
    """
    return math.exp(-((value - target) ** 2) / (2 * sigma ** 2))


def normalize_label(label: Optional[str]) -> Optional[str]:
    """Trims and lower-cases a genre/mood so "Lofi " matches "lofi". Blank becomes None."""
    if label is None:
        return None
    label = str(label).strip().lower()
    return label or None


def validate_prefs(user_prefs: Dict) -> None:
    """Raises ValueError for numeric targets outside their valid range (None is allowed)."""
    energy = user_prefs.get("target_energy", user_prefs.get("energy"))
    values = {name: user_prefs.get(name) for name in UNIT_RANGE_TARGETS}
    values["target_energy"] = energy
    for name, value in values.items():
        if value is not None and not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} must be between 0 and 1, got {value}")
    tempo = user_prefs.get("target_tempo")
    if tempo is not None and not TEMPO_RANGE[0] <= tempo <= TEMPO_RANGE[1]:
        raise ValueError(f"target_tempo must be between {TEMPO_RANGE[0]:g} and {TEMPO_RANGE[1]:g} BPM, got {tempo}")


def label_match(target: Optional[str], value: str, families: List[set]) -> str:
    """Returns "exact", "near" (same family), or "none". Case and edge spaces are ignored."""
    target, value = normalize_label(target), normalize_label(value)
    if target is None or value is None:
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
    validate_prefs(user_prefs)
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
            reasons.append(f"{key} {song[column]:g} vs target {target:g} +{points:.2f}")

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


def confidence_warnings(user_prefs: Dict, songs: List[Dict], results: List[Tuple[Dict, float, str]]) -> List[str]:
    """
    Plain-language caveats for a result list: no genre/mood coverage, a weak best score,
    or a top pick that does not match the requested mood.
    """
    warnings: List[str] = []
    if not results:
        return warnings
    if profile_coverage(user_prefs, songs) == 0:
        warnings.append("no song in the catalog matches this genre or mood; ranking uses audio numbers only")
    if results[0][1] < LOW_CONFIDENCE_SCORE:
        warnings.append(f"best score is only {results[0][1]:.2f}; nothing fits this profile well")
    mood = user_prefs.get("favorite_mood", user_prefs.get("mood"))
    top_song = results[0][0]
    if normalize_label(mood) and label_match(mood, top_song["mood"], MOOD_FAMILIES) == "none":
        warnings.append(f"the top pick ({top_song['title']}) does not match the mood '{mood}'")
    return warnings


def recommend_songs(
    user_prefs: Dict,
    songs: List[Dict],
    k: int = 5,
    max_per_genre: Optional[int] = None,
    max_per_artist: Optional[int] = None,
) -> List[Tuple[Dict, float, str]]:
    """
    Functional implementation of the recommendation logic.
    Required by src/main.py
    Returns the top k as (song_dict, score, explanation), best first. Optional diversity
    caps keep at most max_per_genre songs of one genre and max_per_artist by one artist;
    skipped songs only backfill if fewer than k songs fit under the caps.
    """
    if k < 0:
        raise ValueError("k must be non-negative")
    if any(cap is not None and cap < 1 for cap in (max_per_genre, max_per_artist)):
        raise ValueError("diversity caps must be at least 1")
    scored = (
        (song, score, "; ".join(reasons))
        for song in songs
        for score, reasons in [score_song(user_prefs, song)]
    )
    # Best score first; equal scores fall back to title so order is reproducible.
    order = lambda item: (-item[1], item[0]["title"])
    ranked = sorted(scored, key=order)
    if max_per_genre is None and max_per_artist is None:
        return ranked[:k]

    picked, skipped = [], []
    genre_counts: Counter = Counter()
    artist_counts: Counter = Counter()
    for item in ranked:
        if len(picked) == k:
            break
        genre = normalize_label(item[0]["genre"])
        artist = normalize_label(item[0]["artist"])
        if (max_per_genre is not None and genre_counts[genre] >= max_per_genre) or (
            max_per_artist is not None and artist_counts[artist] >= max_per_artist
        ):
            skipped.append(item)
            continue
        picked.append(item)
        genre_counts[genre] += 1
        artist_counts[artist] += 1
    picked += skipped[: k - len(picked)]
    return sorted(picked, key=order)


def load_songs(csv_path: str) -> List[Dict]:
    """
    Loads songs from a CSV file, converting numeric columns.
    Required by src/main.py
    """
    int_fields = ("id",)
    float_fields = ("tempo_bpm", "energy", "valence", "danceability", "acousticness")
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
        """Stores the song catalog to recommend from."""
        self.songs = songs

    @staticmethod
    def _prefs(user: UserProfile) -> Dict:
        """Converts a UserProfile into the preference dict that score_song expects."""
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
        """Returns the top k songs for the user, best score first (ties by title)."""
        prefs = self._prefs(user)
        ranked = sorted(
            self.songs,
            key=lambda s: (-score_song(prefs, asdict(s))[0], s.title),
        )
        return ranked[:k]

    def explain_recommendation(self, user: UserProfile, song: Song) -> str:
        """Returns the song's score and the reasons behind it as one readable string."""
        score, reasons = score_song(self._prefs(user), asdict(song))
        return f"Score {score:.2f}: " + "; ".join(reasons)
