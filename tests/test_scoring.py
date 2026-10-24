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
    assert len(songs) == 20
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
