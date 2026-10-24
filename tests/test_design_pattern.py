"""Tests for the modular structure: Strategy objects per feature (SCORERS), the no-match
adjuster, and re-rankers (DiversityReranker and custom ones)."""
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import recommender as rec
from recommender import (
    EXTRA_WEIGHTS,
    SCORERS,
    WEIGHTS,
    DiversityReranker,
    FeatureScorer,
    TermResult,
    apply_no_match_penalty,
    load_songs,
    recommend_songs,
    score_song,
    weights_for,
)

CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "songs.csv")
BASE = {"favorite_genre": "pop", "favorite_mood": "happy", "target_energy": 0.8}


def song(**overrides):
    base = {"id": 1, "title": "T", "artist": "A", "genre": "pop", "mood": "happy", "energy": 0.8,
            "tempo_bpm": 120.0, "valence": 0.7, "danceability": 0.7, "acousticness": 0.2}
    base.update(overrides)
    return base


# scorers (Strategy) -------------------------------------------------------

def test_every_scorer_follows_the_interface_and_has_a_unique_weight_key():
    keys = [scorer.key for scorer in SCORERS]
    assert all(isinstance(scorer, FeatureScorer) for scorer in SCORERS)
    assert len(keys) == len(set(keys))
    assert set(keys) == set(WEIGHTS) | set(EXTRA_WEIGHTS)


def test_the_base_class_is_abstract():
    with pytest.raises(NotImplementedError):
        FeatureScorer().applies({})
    with pytest.raises(NotImplementedError):
        FeatureScorer().score({}, {}, {})


def test_each_scorer_returns_a_term_result_within_its_weight():
    prefs = {"favorite_genre": "pop", "favorite_mood": "happy", "target_energy": 0.8, "likes_acoustic": False,
             "target_tempo": 120, "target_valence": 0.7, "target_danceability": 0.7, "target_popularity": 50,
             "preferred_decade": 2010, "favorite_mood_tags": ["sunny"], "preferred_language": "english",
             "target_instrumentalness": 0.1}
    full = song(popularity=50, release_decade=2010, mood_tags=["sunny"], language="english", instrumentalness=0.1)
    weights = weights_for(prefs)
    for scorer in SCORERS:
        assert scorer.applies(prefs)
        result = scorer.score(prefs, full, weights)
        assert isinstance(result, TermResult)
        assert 0.0 <= result.points <= weights[scorer.key] + 1e-12
        assert result.reason and "+" in result.reason


def test_scorers_only_apply_when_the_profile_asks_for_them():
    applying = {scorer.key for scorer in SCORERS if scorer.applies(BASE)}
    assert applying == {"genre", "mood", "energy"}


def test_reasons_keep_their_format_and_order():
    s = {"id": 7, "title": "Coffee Shop Stories", "artist": "Slow Stereo", "genre": "jazz", "mood": "relaxed",
         "energy": 0.37, "tempo_bpm": 90.0, "valence": 0.71, "danceability": 0.54, "acousticness": 0.89}
    prefs = {"favorite_genre": "lofi", "favorite_mood": "chill", "target_energy": 0.4, "likes_acoustic": True,
             "target_tempo": 78.0, "target_valence": 0.58, "target_danceability": 0.6}
    score, reasons = score_song(prefs, s)
    assert [r.split(" +")[0] for r in reasons] == [
        "related genre (jazz ~ lofi)", "related mood (relaxed ~ chill)", "energy 0.37 vs target 0.40",
        "acoustic fit", "tempo 90 vs target 78", "valence 0.71 vs target 0.58", "danceability 0.54 vs target 0.6"]
    assert round(score, 2) == 0.82


def test_a_new_scorer_can_be_added_without_touching_score_song(monkeypatch):
    class ExplicitScorer(FeatureScorer):
        key = "explicit"
        def applies(self, prefs):
            return prefs.get("avoid_explicit") is not None
        def score(self, prefs, s, weights):
            points = weights["explicit"] * (0.0 if s.get("explicit") else 1.0)
            return TermResult(points, f"clean lyrics +{points:.2f}")

    monkeypatch.setattr(rec, "SCORERS", [*SCORERS, ExplicitScorer()])
    monkeypatch.setitem(EXTRA_WEIGHTS, "explicit", 0.05)
    prefs = dict(BASE, avoid_explicit=True)
    clean, dirty = score_song(prefs, song(explicit=False)), score_song(prefs, song(explicit=True))
    assert clean[0] > dirty[0]
    assert any("clean lyrics" in reason for reason in clean[1])
    assert math.isclose(sum(weights_for(prefs).values()), 1.0)


# the shared "is it set?" check ------------------------------------------------

@pytest.mark.parametrize("blank", [{"preferred_language": "   "}, {"favorite_mood_tags": [" "]},
                                   {"preferred_language": ""}, {"favorite_mood_tags": []}])
def test_a_blank_extra_preference_does_not_change_any_score(blank):
    s = load_songs(CSV_PATH)[0]
    assert score_song(dict(BASE, **blank), s) == score_song(BASE, s)
    assert weights_for(dict(BASE, **blank)) == WEIGHTS


# no-match adjuster ----------------------------------------------------------

def test_adjuster_halves_only_when_every_label_missed():
    reasons = []
    assert apply_no_match_penalty(0.8, reasons, ["none", "none"]) == pytest.approx(0.4)
    assert "closest fit only" in reasons[0]
    assert apply_no_match_penalty(0.8, [], ["near", "none"]) == 0.8
    assert apply_no_match_penalty(0.8, [], []) == 0.8


# rerankers ----------------------------------------------------------------

def test_diversity_reranker_class_matches_the_caps_arguments():
    songs = load_songs(CSV_PATH)
    prefs = {"favorite_genre": "lofi", "favorite_mood": "chill", "target_energy": 0.4}
    via_args = recommend_songs(prefs, songs, k=5, max_per_genre=2, max_per_artist=1)
    via_class = recommend_songs(prefs, songs, k=5, rerankers=[DiversityReranker(2, 1)])
    assert via_args == via_class


def test_a_custom_reranker_can_be_plugged_in():
    songs = load_songs(CSV_PATH)
    prefs = {"favorite_genre": "pop", "favorite_mood": "happy", "target_energy": 0.8}

    def no_hip_hop(ranked, k):
        return [item for item in ranked if item[0]["genre"] != "hip hop"][:k]

    plain = [s["genre"] for s, _, _ in recommend_songs(prefs, songs, k=10)]
    filtered = [s["genre"] for s, _, _ in recommend_songs(prefs, songs, k=10, rerankers=[no_hip_hop])]
    assert "hip hop" in plain and "hip hop" not in filtered


def test_rerankers_run_in_order_after_the_diversity_caps():
    songs = load_songs(CSV_PATH)
    prefs = {"favorite_genre": "lofi", "favorite_mood": "chill", "target_energy": 0.4}
    calls = []

    def spy(ranked, k):
        calls.append([item[0]["title"] for item in ranked])
        return ranked

    result = recommend_songs(prefs, songs, k=5, max_per_genre=2, rerankers=[spy])
    assert calls == [[s["title"] for s, _, _ in result]]  # the spy saw the already-capped list


def test_diversity_reranker_rejects_bad_caps():
    with pytest.raises(ValueError):
        DiversityReranker(0, None)
    with pytest.raises(ValueError):
        DiversityReranker(None, -1)


def test_results_are_never_longer_than_k_and_stay_best_first():
    songs = load_songs(CSV_PATH)
    prefs = {"favorite_genre": "rock", "favorite_mood": "intense", "target_energy": 0.9}
    for k in (0, 1, 3, 5, 40, 100):
        out = recommend_songs(prefs, songs, k=k, max_per_genre=1, max_per_artist=1)
        assert len(out) <= k
        assert [score for _, score, _ in out] == sorted((score for _, score, _ in out), reverse=True)
