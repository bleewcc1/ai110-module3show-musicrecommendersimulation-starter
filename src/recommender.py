import csv
import math
from collections import Counter
from typing import Callable, List, Dict, Sequence, Tuple, Optional
from dataclasses import dataclass, asdict, field

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
    # Extra attributes (all optional so older catalogs still load).
    popularity: Optional[int] = None  # 0-100, how mainstream the song is
    release_decade: Optional[int] = None  # e.g. 1990, 2010
    mood_tags: List[str] = field(default_factory=list)  # detailed tags, e.g. ["nostalgic", "neon"]
    language: Optional[str] = None  # e.g. "english", "spanish", "instrumental"
    instrumentalness: Optional[float] = None  # 0-1, 1 = no vocals

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
    target_popularity: Optional[float] = None
    preferred_decade: Optional[int] = None
    favorite_mood_tags: Optional[List[str]] = None
    preferred_language: Optional[str] = None
    target_instrumentalness: Optional[float] = None

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

# Ranking strategies: the same scoring rules with a different emphasis. Each strategy lists
# raw weights for the seven base terms and is rescaled to sum to 1.0, so scores stay in
# [0, 1] in every mode. "balanced" is the default and uses WEIGHTS above.
DEFAULT_STRATEGY = "balanced"
_STRATEGY_RAW_WEIGHTS = {
    "genre-first": {"genre": 0.45, "mood": 0.15, "energy": 0.20, "acoustic": 0.10,
                    "tempo": 0.04, "valence": 0.03, "danceability": 0.03},
    "mood-first": {"genre": 0.10, "mood": 0.45, "energy": 0.20, "acoustic": 0.10,
                   "tempo": 0.04, "valence": 0.03, "danceability": 0.03},
    "energy-focused": {"genre": 0.08, "mood": 0.10, "energy": 0.62, "acoustic": 0.10,
                       "tempo": 0.04, "valence": 0.03, "danceability": 0.03},
}
STRATEGIES = {
    name: {key: value / sum(raw.values()) for key, value in raw.items()}
    for name, raw in _STRATEGY_RAW_WEIGHTS.items()
}
STRATEGY_DESCRIPTIONS = {
    "balanced": "default mix: energy counts most, then mood, genre and acoustic feel",
    "genre-first": "the genre label counts most; stays inside the genre you named",
    "mood-first": "the mood label counts most; follows the feeling across genres",
    "energy-focused": "how energetic the song is counts most; follows the sound, not the labels",
}
STRATEGY_NAMES = (DEFAULT_STRATEGY, *STRATEGIES)
# Optional terms for the extra attributes (keys match the scorer names below). Like tempo /
# valence / danceability they only count when the profile sets the matching preference. When some are active, every weight
# for that profile is divided by (1 + their total) so the score still stays in [0, 1],
# and a profile that sets none of them is scored exactly as before.
EXTRA_WEIGHTS = {
    "popularity": 0.03, "decade": 0.03, "tags": 0.05, "language": 0.02, "instrumental": 0.03,
}
POPULARITY_SIGMA = 25.0  # on the 0-100 scale
DECADE_SIGMA = 10.0  # in years: one decade away keeps ~0.6, two decades ~0.14
INSTRUMENTAL_SIGMA = 0.25
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
POPULARITY_RANGE = (0.0, 100.0)
DECADE_RANGE = (1900, 2100)
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
    popularity = user_prefs.get("target_popularity")
    if popularity is not None and not POPULARITY_RANGE[0] <= popularity <= POPULARITY_RANGE[1]:
        raise ValueError(f"target_popularity must be between 0 and 100, got {popularity}")
    decade = user_prefs.get("preferred_decade")
    if decade is not None and not DECADE_RANGE[0] <= decade <= DECADE_RANGE[1]:
        raise ValueError(f"preferred_decade must be between {DECADE_RANGE[0]} and {DECADE_RANGE[1]}, got {decade}")
    instrumental = user_prefs.get("target_instrumentalness")
    if instrumental is not None and not 0.0 <= instrumental <= 1.0:
        raise ValueError(f"target_instrumentalness must be between 0 and 1, got {instrumental}")
    tags = user_prefs.get("favorite_mood_tags")
    if tags is not None and (isinstance(tags, str) or not all(isinstance(t, str) for t in tags)):
        raise ValueError("favorite_mood_tags must be a list of strings")


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


def base_weights(strategy: Optional[str] = None) -> Dict[str, float]:
    """The seven base weights for a ranking strategy (None or "balanced" = the default)."""
    if strategy in (None, DEFAULT_STRATEGY):
        return WEIGHTS
    if strategy not in STRATEGIES:
        raise ValueError(f"unknown strategy '{strategy}'; choose from {', '.join(STRATEGY_NAMES)}")
    return STRATEGIES[strategy]


def weights_for(user_prefs: Dict, strategy: Optional[str] = None) -> Dict[str, float]:
    """
    The weights to use for this profile and strategy. Extra terms whose scorer applies to
    the profile are added and everything is divided by (1 + their total), so the weights
    still sum to at most 1. The scorers decide what counts as "set", so a blank preference
    never reserves weight it cannot use.
    """
    active = {
        scorer.key: EXTRA_WEIGHTS[scorer.key]
        for scorer in SCORERS
        if scorer.key in EXTRA_WEIGHTS and scorer.applies(user_prefs)
    }
    divisor = 1.0 + sum(active.values())
    weights = {name: weight / divisor for name, weight in base_weights(strategy).items()}
    weights.update({name: weight / divisor for name, weight in active.items()})
    return weights


def tag_overlap(wanted: List[str], song_tags: List[str]) -> Tuple[float, List[str]]:
    """Share of the wanted mood tags the song has (0-1), plus the tags that matched."""
    wanted_tags = {tag for tag in map(normalize_label, wanted) if tag}
    have = {tag for tag in map(normalize_label, song_tags or []) if tag}
    hits = sorted(wanted_tags & have)
    return (len(hits) / len(wanted_tags) if wanted_tags else 0.0), hits


@dataclass
class TermResult:
    """What one scorer gives a song: its points, the reason to show, and (for labels) the match kind."""
    points: float
    reason: Optional[str] = None
    match: Optional[str] = None


class FeatureScorer:
    """Strategy interface: one scorer judges one feature of a song against the profile."""
    key = ""  # the weight this scorer uses

    def applies(self, user_prefs: Dict) -> bool:
        """True when the profile asks for this feature, so the term counts."""
        raise NotImplementedError

    def score(self, user_prefs: Dict, song: Dict, weights: Dict[str, float]) -> TermResult:
        """Points and a reason for this song."""
        raise NotImplementedError


class LabelScorer(FeatureScorer):
    """Genre or mood: full weight for an exact match, half for a related label."""

    def __init__(self, key: str, pref_keys: Tuple[str, str], families: List[set]):
        self.key, self.pref_keys, self.families = key, pref_keys, families

    def applies(self, user_prefs: Dict) -> bool:
        return True  # always scored; a missing label just earns nothing

    def score(self, user_prefs, song, weights):
        target = user_prefs.get(self.pref_keys[0], user_prefs.get(self.pref_keys[1]))
        match = label_match(target, song[self.key], self.families)
        if match == "exact":
            points = weights[self.key]
            return TermResult(points, f"{self.key} match ({song[self.key]}) +{points:.2f}", match)
        if match == "near":
            points = weights[self.key] * NEAR_MATCH_CREDIT
            return TermResult(points, f"related {self.key} ({song[self.key]} ~ {target}) +{points:.2f}", match)
        return TermResult(0.0, None, match)


class EnergyScorer(FeatureScorer):
    """Gaussian closeness of the song's energy to the target energy."""
    key = "energy"

    def applies(self, user_prefs):
        return user_prefs.get("target_energy", user_prefs.get("energy")) is not None

    def score(self, user_prefs, song, weights):
        target = user_prefs.get("target_energy", user_prefs.get("energy"))
        points = weights["energy"] * closeness(target, song["energy"], ENERGY_SIGMA)
        return TermResult(points, f"energy {song['energy']:.2f} vs target {target:.2f} +{points:.2f}")


class AcousticScorer(FeatureScorer):
    """Rewards acoustic songs for a listener who likes them, electronic ones otherwise."""
    key = "acoustic"

    def applies(self, user_prefs):
        return user_prefs.get("likes_acoustic") is not None

    def score(self, user_prefs, song, weights):
        fit = song["acousticness"] if user_prefs["likes_acoustic"] else 1 - song["acousticness"]
        points = weights["acoustic"] * fit
        return TermResult(points, f"acoustic fit +{points:.2f}")


class ClosenessScorer(FeatureScorer):
    """A numeric column scored by closeness to a target. Optional columns may be missing."""

    def __init__(self, key: str, pref_key: str, column: str, sigma: float, template: str,
                 optional_column: bool = False):
        self.key, self.pref_key, self.column, self.sigma = key, pref_key, column, sigma
        self.template, self.optional_column = template, optional_column

    def applies(self, user_prefs):
        return user_prefs.get(self.pref_key) is not None

    def score(self, user_prefs, song, weights):
        target = user_prefs[self.pref_key]
        value = song.get(self.column) if self.optional_column else song[self.column]
        points = weights[self.key] * closeness(target, value, self.sigma) if value is not None else 0.0
        shown = value if value is not None else "?"
        return TermResult(points, f"{self.template.format(value=shown, target=target)} +{points:.2f}")


class TagScorer(FeatureScorer):
    """Share of the wanted detailed mood tags that the song has."""
    key = "tags"

    def applies(self, user_prefs):
        wanted = user_prefs.get("favorite_mood_tags")
        return bool(wanted) and any(normalize_label(tag) for tag in wanted)

    def score(self, user_prefs, song, weights):
        wanted = user_prefs["favorite_mood_tags"]
        fit, hits = tag_overlap(wanted, song.get("mood_tags"))
        points = weights["tags"] * fit
        asked = len({normalize_label(tag) for tag in wanted} - {None})
        shown = ", ".join(hits) if hits else "none"
        return TermResult(points, f"mood tags matched: {shown} ({len(hits)} of {asked}) +{points:.2f}")


class LanguageScorer(FeatureScorer):
    """Full points when the song's language is the preferred one."""
    key = "language"

    def applies(self, user_prefs):
        return bool(normalize_label(user_prefs.get("preferred_language")))

    def score(self, user_prefs, song, weights):
        preferred = normalize_label(user_prefs.get("preferred_language"))
        same = normalize_label(song.get("language")) == preferred
        points = weights["language"] if same else 0.0
        return TermResult(points, f"language {song.get('language') or '?'} vs preferred {preferred} +{points:.2f}")


# The registry. Add a feature by writing a scorer and appending it here (plus a weight);
# score_song() and weights_for() pick it up with no other change. Order = order of reasons.
SCORERS: List[FeatureScorer] = [
    LabelScorer("genre", ("favorite_genre", "genre"), GENRE_FAMILIES),
    LabelScorer("mood", ("favorite_mood", "mood"), MOOD_FAMILIES),
    EnergyScorer(),
    AcousticScorer(),
    # Optional small terms; they also separate songs that would otherwise tie.
    ClosenessScorer("tempo", "target_tempo", "tempo_bpm", TEMPO_SIGMA, "tempo {value:g} vs target {target:g}"),
    ClosenessScorer("valence", "target_valence", "valence", VALENCE_SIGMA, "valence {value:g} vs target {target:g}"),
    ClosenessScorer("danceability", "target_danceability", "danceability", DANCEABILITY_SIGMA,
                    "danceability {value:g} vs target {target:g}"),
    # Extra attributes: a song missing one earns nothing for that term.
    ClosenessScorer("popularity", "target_popularity", "popularity", POPULARITY_SIGMA,
                    "popularity {value} vs target {target:g}", optional_column=True),
    ClosenessScorer("decade", "preferred_decade", "release_decade", DECADE_SIGMA,
                    "decade {value}s vs preferred {target}s", optional_column=True),
    TagScorer(),
    LanguageScorer(),
    ClosenessScorer("instrumental", "target_instrumentalness", "instrumentalness", INSTRUMENTAL_SIGMA,
                    "instrumentalness {value} vs target {target:g}", optional_column=True),
]


def apply_no_match_penalty(score: float, reasons: List[str], matches: List[str]) -> float:
    """Halves the score when neither genre nor mood matched, exactly or as a related label."""
    if matches and all(match == "none" for match in matches):
        reasons.append(f"closest fit only: no genre or mood match, score x{NO_MATCH_PENALTY}")
        return score * NO_MATCH_PENALTY
    return score


def score_song(user_prefs: Dict, song: Dict, strategy: Optional[str] = None) -> Tuple[float, List[str]]:
    """
    Scores a single song against user preferences.
    Required by recommend_songs() and src/main.py

    user_prefs keys: favorite_genre, favorite_mood, target_energy, and optionally
    likes_acoustic (bool), target_tempo, target_valence, target_danceability, and the
    extra-attribute preferences target_popularity (0-100), preferred_decade (e.g. 2010),
    favorite_mood_tags (list), preferred_language and target_instrumentalness (0-1).
    The short names genre, mood, energy are also accepted. strategy picks the ranking mode
    (see STRATEGIES); the default is "balanced".
    Returns (score between 0 and 1, list of reasons).
    """
    validate_prefs(user_prefs)
    weights = weights_for(user_prefs, strategy)
    reasons: List[str] = []
    matches: List[str] = []
    score = 0.0
    for scorer in SCORERS:
        if not scorer.applies(user_prefs):
            continue
        result = scorer.score(user_prefs, song, weights)
        score += result.points
        if result.reason:
            reasons.append(result.reason)
        if result.match is not None:
            matches.append(result.match)
    score = apply_no_match_penalty(score, reasons, matches)
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


Ranked = List[Tuple[Dict, float, str]]
Reranker = Callable[[Ranked, int], Ranked]  # takes the full ranking and k, returns at most k


class DiversityReranker:
    """Keeps at most max_per_genre songs of one genre and max_per_artist by one artist."""

    def __init__(self, max_per_genre: Optional[int] = None, max_per_artist: Optional[int] = None):
        if any(cap is not None and cap < 1 for cap in (max_per_genre, max_per_artist)):
            raise ValueError("diversity caps must be at least 1")
        self.max_per_genre, self.max_per_artist = max_per_genre, max_per_artist

    def __call__(self, ranked: Ranked, k: int) -> Ranked:
        """Walks down the ranking skipping capped songs; skipped ones backfill only if needed."""
        picked, skipped = [], []
        genre_counts: Counter = Counter()
        artist_counts: Counter = Counter()
        for item in ranked:
            if len(picked) == k:
                break
            genre = normalize_label(item[0]["genre"])
            artist = normalize_label(item[0]["artist"])
            if (self.max_per_genre is not None and genre_counts[genre] >= self.max_per_genre) or (
                self.max_per_artist is not None and artist_counts[artist] >= self.max_per_artist
            ):
                skipped.append(item)
                continue
            picked.append(item)
            genre_counts[genre] += 1
            artist_counts[artist] += 1
        picked += skipped[: k - len(picked)]
        return sorted(picked, key=_rank_key)


class DiversityPenaltyReranker:
    """
    Soft variety rule. Songs are picked one at a time, and each candidate loses
    genre_penalty for every song of its genre already picked and artist_penalty for every
    song by its artist already picked. A strong song can still repeat a genre or artist,
    but a weaker one has to earn it. The returned score is the penalized one, and the
    explanation says how much was taken off.
    """

    def __init__(self, genre_penalty: float = 0.0, artist_penalty: float = 0.0):
        if genre_penalty < 0 or artist_penalty < 0:
            raise ValueError("diversity penalties must be non-negative")
        self.genre_penalty, self.artist_penalty = genre_penalty, artist_penalty

    def __call__(self, ranked: Ranked, k: int) -> Ranked:
        """Greedily picks the best penalized song until k are chosen."""
        pool = list(ranked)
        picked: Ranked = []
        genre_counts: Counter = Counter()
        artist_counts: Counter = Counter()
        while pool and len(picked) < k:
            best = None
            for item in pool:
                genre = normalize_label(item[0]["genre"])
                artist = normalize_label(item[0]["artist"])
                cut = self.genre_penalty * genre_counts[genre] + self.artist_penalty * artist_counts[artist]
                adjusted = max(0.0, item[1] - cut)
                key = (-adjusted, item[0]["title"])
                if best is None or key < best[0]:
                    best = (key, item, adjusted, cut, genre, artist)
            _, item, adjusted, cut, genre, artist = best
            explanation = item[2]
            if cut > 0:
                seen = []
                if genre_counts[genre] and self.genre_penalty:
                    n = genre_counts[genre]
                    seen.append(f"{n} earlier {item[0]['genre']} song{'s' if n > 1 else ''}")
                if artist_counts[artist] and self.artist_penalty:
                    seen.append(f"{artist_counts[artist]} earlier by {item[0]['artist']}")
                explanation += f"; diversity penalty -{cut:.2f} ({' and '.join(seen)})"
            picked.append((item[0], adjusted, explanation))
            pool.remove(item)
            genre_counts[genre] += 1
            artist_counts[artist] += 1
        return picked


def _rank_key(item: Tuple[Dict, float, str]) -> Tuple[float, str]:
    """Best score first; equal scores fall back to title so order is reproducible."""
    return (-item[1], item[0]["title"])


def recommend_songs(
    user_prefs: Dict,
    songs: List[Dict],
    k: int = 5,
    max_per_genre: Optional[int] = None,
    max_per_artist: Optional[int] = None,
    strategy: Optional[str] = None,
    rerankers: Optional[Sequence[Reranker]] = None,
    genre_penalty: float = 0.0,
    artist_penalty: float = 0.0,
) -> List[Tuple[Dict, float, str]]:
    """
    Functional implementation of the recommendation logic.
    Required by src/main.py
    Returns the top k as (song_dict, score, explanation), best first. strategy picks the
    ranking mode ("balanced", "genre-first", "mood-first" or "energy-focused"). The optional
    caps build a DiversityReranker and the penalties build a DiversityPenaltyReranker (caps
    run first); any extra rerankers you pass run after them, in order.
    """
    if k < 0:
        raise ValueError("k must be non-negative")
    base_weights(strategy)  # fail fast on an unknown strategy
    steps: List[Reranker] = []
    if max_per_genre is not None or max_per_artist is not None:
        steps.append(DiversityReranker(max_per_genre, max_per_artist))
    if genre_penalty or artist_penalty:
        steps.append(DiversityPenaltyReranker(genre_penalty, artist_penalty))
    steps.extend(rerankers or ())
    scored = (
        (song, score, "; ".join(reasons))
        for song in songs
        for score, reasons in [score_song(user_prefs, song, strategy)]
    )
    ranked = sorted(scored, key=_rank_key)
    for rerank in steps:
        ranked = rerank(ranked, k)
    return ranked[:k]


def load_songs(csv_path: str) -> List[Dict]:
    """
    Loads songs from a CSV file, converting numeric columns.
    Required by src/main.py
    """
    int_fields = ("id",)
    float_fields = ("tempo_bpm", "energy", "valence", "danceability", "acousticness")
    # Extra columns are optional: older files without them still load.
    optional_int_fields = ("popularity", "release_decade")
    optional_float_fields = ("instrumentalness",)
    songs = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            for key in int_fields:
                row[key] = int(row[key])
            for key in float_fields:
                row[key] = float(row[key])
            for key in optional_int_fields:
                if key in row:
                    row[key] = int(row[key]) if row[key] not in (None, "") else None
            for key in optional_float_fields:
                if key in row:
                    row[key] = float(row[key]) if row[key] not in (None, "") else None
            if "mood_tags" in row:  # "dreamy;cozy" -> ["dreamy", "cozy"]
                row["mood_tags"] = [tag.strip() for tag in (row["mood_tags"] or "").split(";") if tag.strip()]
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
            "target_popularity": user.target_popularity,
            "preferred_decade": user.preferred_decade,
            "favorite_mood_tags": user.favorite_mood_tags,
            "preferred_language": user.preferred_language,
            "target_instrumentalness": user.target_instrumentalness,
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
