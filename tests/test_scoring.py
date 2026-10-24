import math

from src.recommender import (
    ENERGY_SIGMA,
    NO_MATCH_PENALTY,
    WEIGHTS,
    closeness,
    load_songs,
    recommend_songs,
    score_song,
)


def make_song(**overrides):
    song = {
        "id": 1, "title": "T", "artist": "A", "genre": "pop", "mood": "happy",
        "energy": 0.8, "tempo_bpm": 120.0, "valence": 0.7,
        "danceability": 0.7, "acousticness": 0.2,
    }
    song.update(overrides)
    return song


# closeness() -----------------------------------------------------------

def test_closeness_is_one_at_target():
    assert closeness(0.6, 0.6, 0.25) == 1.0


def test_closeness_is_symmetric():
    assert math.isclose(closeness(0.5, 0.3, 0.25), closeness(0.5, 0.7, 0.25))


def test_closeness_decreases_with_distance():
    scores = [closeness(0.5, 0.5 + d, 0.25) for d in (0.0, 0.1, 0.2, 0.4, 0.6)]
    assert scores == sorted(scores, reverse=True)
    assert len(set(scores)) == len(scores)


def test_closeness_known_values():
    assert math.isclose(closeness(0.5, 0.6, 0.25), math.exp(-0.08))
    assert closeness(0.5, 0.9, 0.25) < 0.3


def test_closeness_stays_in_unit_range():
    for value in (0.0, 0.25, 0.5, 1.0):
        assert 0.0 <= closeness(0.5, value, 0.25) <= 1.0


def test_smaller_sigma_is_pickier():
    assert closeness(0.5, 0.8, 0.1) < closeness(0.5, 0.8, 0.4)


# score_song() ----------------------------------------------------------

def test_closer_energy_beats_higher_energy():
    prefs = {"genre": "pop", "mood": "happy", "energy": 0.4}
    close = score_song(prefs, make_song(energy=0.45))[0]
    high = score_song(prefs, make_song(energy=0.95))[0]
    assert close > high


def test_closer_energy_beats_lower_energy():
    prefs = {"genre": "pop", "mood": "happy", "energy": 0.8}
    close = score_song(prefs, make_song(energy=0.75))[0]
    low = score_song(prefs, make_song(energy=0.2))[0]
    assert close > low


def test_equal_distance_above_and_below_scores_equally():
    prefs = {"genre": "pop", "mood": "happy", "energy": 0.5}
    above = score_song(prefs, make_song(energy=0.7))[0]
    below = score_song(prefs, make_song(energy=0.3))[0]
    assert math.isclose(above, below)


def test_perfect_match_without_acoustic_pref():
    prefs = {"genre": "pop", "mood": "happy", "energy": 0.8}
    score, _ = score_song(prefs, make_song())
    assert math.isclose(score, WEIGHTS["genre"] + WEIGHTS["mood"] + WEIGHTS["energy"])


def test_no_genre_or_mood_match_is_penalized():
    prefs = {"genre": "rock", "mood": "intense", "energy": 0.8}
    score, reasons = score_song(prefs, make_song())
    assert math.isclose(score, WEIGHTS["energy"] * NO_MATCH_PENALTY)
    assert any("no genre or mood match" in r for r in reasons)


def test_acoustic_preference_flips_ranking():
    song = make_song(acousticness=0.9)
    likes = score_song({"genre": "pop", "mood": "happy", "energy": 0.8, "likes_acoustic": True}, song)[0]
    dislikes = score_song({"genre": "pop", "mood": "happy", "energy": 0.8, "likes_acoustic": False}, song)[0]
    assert likes > dislikes


def test_reasons_are_returned():
    _, reasons = score_song({"genre": "pop", "mood": "happy", "energy": 0.8}, make_song())
    assert len(reasons) == 3


# recommend_songs() / load_songs() -------------------------------------

def test_recommend_songs_sorted_and_limited():
    songs = [make_song(id=i, energy=e) for i, e in enumerate((0.1, 0.8, 0.5, 0.9), 1)]
    results = recommend_songs({"genre": "pop", "mood": "happy", "energy": 0.8}, songs, k=3)
    scores = [r[1] for r in results]
    assert len(results) == 3
    assert scores == sorted(scores, reverse=True)
    assert results[0][0]["energy"] == 0.8


def test_load_songs_converts_types():
    songs = load_songs("data/songs.csv")
    assert len(songs) == 40
    for song in songs:
        assert isinstance(song["id"], int)
        for field in ("title", "artist", "genre", "mood"):
            assert isinstance(song[field], str)
        for field in ("tempo_bpm", "energy", "valence", "danceability", "acousticness"):
            assert isinstance(song[field], float), field


def test_low_energy_user_gets_low_energy_top_pick():
    songs = load_songs("data/songs.csv")
    top = recommend_songs({"genre": "lofi", "mood": "chill", "energy": 0.35}, songs, k=1)[0][0]
    assert top["genre"] == "lofi" and top["energy"] < 0.5


def test_high_energy_user_not_matched_to_low_energy_song():
    songs = load_songs("data/songs.csv")
    top3 = [r[0]["title"] for r in recommend_songs({"genre": "rock", "mood": "intense", "energy": 0.92}, songs, k=3)]
    assert top3[0] == "Storm Runner"
    assert "Spacewalk Thoughts" not in top3


def test_ties_are_broken_by_title_regardless_of_input_order():
    prefs = {"genre": "pop", "mood": "happy", "energy": 0.8}
    b = make_song(id=1, title="B Song")
    a = make_song(id=2, title="A Song")
    for songs in ([b, a], [a, b]):
        results = recommend_songs(prefs, songs, k=2)
        assert [r[0]["title"] for r in results] == ["A Song", "B Song"]


# borderline-case handling ----------------------------------------------

from src.recommender import NEAR_MATCH_CREDIT, label_match, GENRE_FAMILIES, MOOD_FAMILIES


def test_label_match_levels():
    assert label_match("pop", "pop", GENRE_FAMILIES) == "exact"
    assert label_match("pop", "indie pop", GENRE_FAMILIES) == "near"
    assert label_match("pop", "metal", GENRE_FAMILIES) == "none"
    assert label_match("chill", "relaxed", MOOD_FAMILIES) == "near"


def test_related_genre_earns_partial_credit():
    prefs = {"favorite_genre": "pop", "favorite_mood": "none", "target_energy": 0.8}
    exact = score_song(prefs, make_song(genre="pop", mood="x"))[0]
    near = score_song(prefs, make_song(genre="indie pop", mood="x"))[0]
    none = score_song(prefs, make_song(genre="metal", mood="x"))[0]
    assert none < near < exact
    assert math.isclose(near - none / NO_MATCH_PENALTY, WEIGHTS["genre"] * NEAR_MATCH_CREDIT)


def test_related_match_avoids_no_match_penalty():
    prefs = {"favorite_genre": "rock", "favorite_mood": "intense", "target_energy": 0.9}
    _, reasons = score_song(prefs, make_song(genre="metal", mood="aggressive", energy=0.9))
    assert not any("closest fit only" in r for r in reasons)


def test_unrelated_song_is_labelled_closest_fit_only():
    prefs = {"favorite_genre": "rock", "favorite_mood": "intense", "target_energy": 0.9}
    _, reasons = score_song(prefs, make_song(genre="pop", mood="happy", energy=0.9))
    assert any("closest fit only" in r for r in reasons)


def test_optional_tempo_breaks_a_tie():
    prefs = {"favorite_genre": "rock", "favorite_mood": "intense", "target_energy": 0.9, "target_tempo": 155.0}
    a = score_song(prefs, make_song(genre="pop", mood="happy", energy=0.9, tempo_bpm=150.0))[0]
    b = score_song(prefs, make_song(genre="pop", mood="happy", energy=0.9, tempo_bpm=90.0))[0]
    assert a > b


def test_weights_sum_to_one():
    assert math.isclose(sum(WEIGHTS.values()), 1.0)


# recommend_songs() edge cases -------------------------------------------

import pytest


def test_k_larger_than_catalog_returns_every_song():
    songs = [make_song(id=i, title=f"S{i}") for i in range(3)]
    prefs = {"favorite_genre": "pop", "favorite_mood": "happy", "target_energy": 0.8}
    assert len(recommend_songs(prefs, songs, k=10)) == 3


def test_k_zero_returns_nothing():
    prefs = {"favorite_genre": "pop", "favorite_mood": "happy", "target_energy": 0.8}
    assert recommend_songs(prefs, [make_song()], k=0) == []


def test_negative_k_is_rejected():
    prefs = {"favorite_genre": "pop", "favorite_mood": "happy", "target_energy": 0.8}
    with pytest.raises(ValueError):
        recommend_songs(prefs, [make_song()], k=-1)


def test_empty_catalog_returns_nothing():
    assert recommend_songs({"favorite_genre": "pop"}, [], k=5) == []


# Adversarial / edge cases ----------------------------------------------

import pytest

from src.recommender import (
    LOW_CONFIDENCE_SCORE,
    confidence_warnings,
    label_match,
    MOOD_FAMILIES,
    normalize_label,
    validate_prefs,
)


def test_labels_ignore_case_and_edge_whitespace():
    assert normalize_label(" Lofi ") == "lofi"
    assert normalize_label("   ") is None
    prefs = {"favorite_genre": " Lofi ", "favorite_mood": "CHILL", "target_energy": 0.4}
    clean = {"favorite_genre": "lofi", "favorite_mood": "chill", "target_energy": 0.4}
    song = make_song(genre="lofi", mood="chill")
    assert score_song(prefs, song) == score_song(clean, song)


def test_sad_is_related_to_melancholy_and_sorrowful():
    assert label_match("sad", "melancholy", MOOD_FAMILIES) == "near"
    assert label_match("sad", "sorrowful", MOOD_FAMILIES) == "near"
    assert label_match("sad", "happy", MOOD_FAMILIES) == "none"


@pytest.mark.parametrize("bad", [
    {"target_energy": 1.5},
    {"target_energy": -1.0},
    {"target_energy": 0.5, "target_valence": 2},
    {"target_energy": 0.5, "target_danceability": -0.1},
    {"target_energy": 0.5, "target_tempo": 400},
    {"target_energy": 0.5, "target_tempo": 0},
])
def test_out_of_range_targets_are_rejected(bad):
    with pytest.raises(ValueError):
        score_song(bad, make_song())
    with pytest.raises(ValueError):
        validate_prefs(bad)


def test_boundary_targets_are_accepted():
    validate_prefs({"target_energy": 0.0, "target_valence": 1.0, "target_tempo": 20})


def test_missing_labels_do_not_crash_and_are_penalized():
    score, _ = score_song({"favorite_genre": None, "favorite_mood": "", "target_energy": 0.8}, make_song())
    assert 0 < score <= WEIGHTS["energy"] * NO_MATCH_PENALTY


def test_sad_request_warns_when_top_pick_is_not_sad():
    songs = load_songs("data/songs.csv")
    prefs = {"favorite_genre": "pop", "favorite_mood": "sad", "target_energy": 0.9, "likes_acoustic": False}
    results = recommend_songs(prefs, songs, k=5)
    assert any("mood 'sad'" in w for w in confidence_warnings(prefs, songs, results))


def test_unknown_labels_warn_about_zero_coverage_and_weak_score():
    songs = load_songs("data/songs.csv")
    prefs = {"favorite_genre": "polka", "favorite_mood": "zany", "target_energy": 0.5}
    results = recommend_songs(prefs, songs, k=5)
    warnings = confidence_warnings(prefs, songs, results)
    assert results[0][1] < LOW_CONFIDENCE_SCORE
    assert len(warnings) == 3


def test_good_profile_has_no_warnings():
    songs = load_songs("data/songs.csv")
    prefs = {"favorite_genre": "lofi", "favorite_mood": "chill", "target_energy": 0.4, "likes_acoustic": True}
    assert confidence_warnings(prefs, songs, recommend_songs(prefs, songs, k=5)) == []


def _catalog():
    return load_songs("data/songs.csv")


def test_diversity_caps_limit_genre_and_artist_in_top_k():
    prefs = {"favorite_genre": "lofi", "favorite_mood": "chill", "target_energy": 0.4}
    plain = recommend_songs(prefs, _catalog(), k=5)
    capped = recommend_songs(prefs, _catalog(), k=5, max_per_genre=2, max_per_artist=1)
    assert sum(s["genre"] == "lofi" for s, _, _ in plain) > 2
    assert sum(s["genre"] == "lofi" for s, _, _ in capped) <= 2
    artists = [s["artist"] for s, _, _ in capped]
    assert len(artists) == len(set(artists)) == 5


def test_diversity_keeps_best_song_and_best_first_order():
    prefs = {"favorite_genre": "rock", "favorite_mood": "intense", "target_energy": 0.92}
    plain = recommend_songs(prefs, _catalog(), k=5)
    capped = recommend_songs(prefs, _catalog(), k=5, max_per_genre=2)
    assert capped[0][0]["title"] == plain[0][0]["title"]
    scores = [score for _, score, _ in capped]
    assert scores == sorted(scores, reverse=True)


def test_diversity_backfills_when_caps_leave_too_few_songs():
    songs = _catalog()[:3]  # pop, lofi, rock: cap of 1 per artist/genre still fits 3
    assert len(recommend_songs({"favorite_genre": "pop", "favorite_mood": "happy", "target_energy": 0.8},
                               songs, k=3, max_per_genre=1)) == 3
    same_genre = [s for s in _catalog() if s["genre"] == "lofi"]
    assert len(recommend_songs({"favorite_genre": "lofi", "favorite_mood": "chill", "target_energy": 0.4},
                               same_genre, k=5, max_per_genre=1)) == 5


def test_diversity_caps_default_off_and_validate():
    prefs = {"favorite_genre": "lofi", "favorite_mood": "chill", "target_energy": 0.4}
    assert recommend_songs(prefs, _catalog(), k=5) == recommend_songs(
        prefs, _catalog(), k=5, max_per_genre=None, max_per_artist=None)
    with pytest.raises(ValueError):
        recommend_songs(prefs, _catalog(), max_per_genre=0)
