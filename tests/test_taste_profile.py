import os
import sys

# main.py imports `recommender` as a top-level module, so put src/ on the path.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from main import HIGH_ENERGY_POP_PROFILE, INTENSE_ROCK_PROFILE, POP_HAPPY_PROFILE, PROFILES, TASTE_PROFILE
from recommender import load_songs, profile_coverage, recommend_songs, score_song

CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "songs.csv")


def test_profile_has_expected_values():
    assert TASTE_PROFILE["favorite_genre"] == "lofi"
    assert TASTE_PROFILE["favorite_mood"] == "chill"
    assert TASTE_PROFILE["target_energy"] == 0.40
    assert TASTE_PROFILE["likes_acoustic"] is True


def test_profile_genre_and_mood_exist_in_catalog():
    songs = load_songs(CSV_PATH)
    assert any(s["genre"] == TASTE_PROFILE["favorite_genre"] for s in songs)
    assert any(s["mood"] == TASTE_PROFILE["favorite_mood"] for s in songs)


def test_top_recommendations_are_lofi_chill():
    songs = load_songs(CSV_PATH)
    top_two = recommend_songs(TASTE_PROFILE, songs, k=2)
    for song, _, _ in top_two:
        assert song["genre"] == "lofi"
        assert song["mood"] == "chill"


def test_calm_acoustic_song_beats_loud_electronic_song():
    songs = load_songs(CSV_PATH)
    by_title = {s["title"]: s for s in songs}
    calm, _ = score_song(TASTE_PROFILE, by_title["Library Rain"])
    loud, _ = score_song(TASTE_PROFILE, by_title["Storm Runner"])
    assert calm > loud


def test_scores_stay_between_zero_and_one():
    for song in load_songs(CSV_PATH):
        score, _ = score_song(TASTE_PROFILE, song)
        assert 0.0 <= score <= 1.0


def titles(profile, k):
    return [s["title"] for s, _, _ in recommend_songs(profile, load_songs(CSV_PATH), k=k)]


def test_intense_rock_and_chill_lofi_get_different_recommendations():
    assert set(titles(TASTE_PROFILE, 3)).isdisjoint(titles(INTENSE_ROCK_PROFILE, 3))


def test_intense_rock_top_pick_is_rock_intense():
    top = recommend_songs(INTENSE_ROCK_PROFILE, load_songs(CSV_PATH), k=1)[0][0]
    assert top["genre"] == "rock" and top["mood"] == "intense"


def test_chill_lofi_scores_low_for_rock_song_and_vice_versa():
    songs = {s["title"]: s for s in load_songs(CSV_PATH)}
    storm, library = songs["Storm Runner"], songs["Library Rain"]
    assert score_song(TASTE_PROFILE, storm)[0] < score_song(TASTE_PROFILE, library)[0]
    assert score_song(INTENSE_ROCK_PROFILE, library)[0] < score_song(INTENSE_ROCK_PROFILE, storm)[0]


def test_profile_coverage_flags_narrow_profile():
    songs = load_songs(CSV_PATH)
    narrow = {"favorite_genre": "no-such-genre", "favorite_mood": "no-such-mood", "target_energy": 0.5}
    assert profile_coverage(narrow, songs) == 0
    assert profile_coverage(TASTE_PROFILE, songs) > profile_coverage(INTENSE_ROCK_PROFILE, songs)


def test_pop_happy_top_pick_is_the_only_exact_match_then_pop_family():
    ranked = recommend_songs(POP_HAPPY_PROFILE, load_songs(CSV_PATH), k=2)
    assert ranked[0][0]["title"] == "Sunrise City"
    assert ranked[1][0]["genre"] in ("pop", "indie pop")  # next best is still pop-family


def test_pop_happy_is_distinct_from_the_other_profiles():
    pop = set(titles(POP_HAPPY_PROFILE, 2))
    assert pop.isdisjoint(titles(TASTE_PROFILE, 2))
    assert pop.isdisjoint(titles(INTENSE_ROCK_PROFILE, 2))


def test_high_energy_pop_prefers_a_bright_pop_song_over_calm_lofi():
    songs = {s["title"]: s for s in load_songs(CSV_PATH)}
    pop, lofi = songs["Sunrise City"], songs["Library Rain"]
    assert score_song(HIGH_ENERGY_POP_PROFILE, pop)[0] > score_song(HIGH_ENERGY_POP_PROFILE, lofi)[0]
    assert titles(HIGH_ENERGY_POP_PROFILE, 1) == ["Sunrise City"]


def test_all_profiles_are_distinct_and_have_required_keys():
    assert len(PROFILES) >= 3
    for prefs in PROFILES.values():
        assert {"favorite_genre", "favorite_mood", "target_energy"} <= prefs.keys()
    assert len({repr(sorted(p.items())) for p in PROFILES.values()}) == len(PROFILES)


def test_typo_lofi_profile_matches_clean_lofi_results():
    from main import ADVERSARIAL_PROFILES
    typo = ADVERSARIAL_PROFILES["Typo Lofi"]
    clean = {**typo, "favorite_genre": "lofi", "favorite_mood": "chill"}
    assert titles(typo, 5) == titles(clean, 5)


def test_adversarial_profiles_never_crash():
    from main import ADVERSARIAL_PROFILES
    songs = load_songs(CSV_PATH)
    for prefs in ADVERSARIAL_PROFILES.values():
        assert len(recommend_songs(prefs, songs, k=5)) == 5


def test_invalid_profiles_are_rejected():
    import pytest
    from main import INVALID_PROFILES
    for prefs in INVALID_PROFILES.values():
        with pytest.raises(ValueError):
            recommend_songs(prefs, load_songs(CSV_PATH), k=5)


def test_low_scoring_results_are_labelled_weak_match():
    from main import WEAK_SCORE, format_recommendation
    song = {"title": "T", "artist": "A"}
    assert "weak match" in format_recommendation(1, song, WEAK_SCORE - 0.01, "x")
    assert "weak match" not in format_recommendation(1, song, WEAK_SCORE + 0.01, "x")
