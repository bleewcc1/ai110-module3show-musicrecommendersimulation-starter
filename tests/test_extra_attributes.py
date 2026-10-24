"""Tests for the extra song attributes: popularity, release decade, mood tags, language and
instrumentalness, and the optional profile preferences that score them."""
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from main import NOSTALGIC_NIGHT_DRIVE_PROFILE
from recommender import (
    EXTRA_WEIGHTS,
    WEIGHTS,
    Recommender,
    Song,
    UserProfile,
    load_songs,
    recommend_songs,
    score_song,
    tag_overlap,
    weights_for,
)

CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "songs.csv")
BASE = {"favorite_genre": "pop", "favorite_mood": "happy", "target_energy": 0.8}


def make_song(**overrides):
    song = {
        "id": 1, "title": "T", "artist": "A", "genre": "pop", "mood": "happy",
        "energy": 0.8, "tempo_bpm": 120.0, "valence": 0.7, "danceability": 0.7,
        "acousticness": 0.2, "popularity": 50, "release_decade": 2010,
        "mood_tags": ["sunny", "neon"], "language": "english", "instrumentalness": 0.1,
    }
    song.update(overrides)
    return song


def test_catalog_has_the_five_new_attributes_with_the_right_types():
    songs = load_songs(CSV_PATH)
    for song in songs:
        assert isinstance(song["popularity"], int) and 0 <= song["popularity"] <= 100
        assert isinstance(song["release_decade"], int) and song["release_decade"] % 10 == 0
        assert isinstance(song["mood_tags"], list) and song["mood_tags"]
        assert all(isinstance(tag, str) and tag == tag.lower() for tag in song["mood_tags"])
        assert isinstance(song["language"], str) and song["language"]
        assert isinstance(song["instrumentalness"], float) and 0.0 <= song["instrumentalness"] <= 1.0


def test_catalog_new_attributes_have_variety():
    songs = load_songs(CSV_PATH)
    assert len({s["release_decade"] for s in songs}) >= 4
    assert len({s["language"] for s in songs}) >= 3
    assert len({tag for s in songs for tag in s["mood_tags"]}) >= 15
    assert max(s["popularity"] for s in songs) - min(s["popularity"] for s in songs) >= 40


def test_old_style_csv_without_the_new_columns_still_loads(tmp_path):
    path = tmp_path / "old.csv"
    path.write_text("id,title,artist,genre,mood,energy,tempo_bpm,valence,danceability,acousticness\n"
                    "1,A,B,pop,happy,0.8,120,0.7,0.7,0.2\n")
    song = load_songs(str(path))[0]
    assert "popularity" not in song and song["energy"] == 0.8
    assert score_song(BASE, song)[0] > 0


def test_profile_without_extra_preferences_is_scored_exactly_as_before():
    assert weights_for(BASE) == WEIGHTS
    _, reasons = score_song(BASE, make_song())
    assert not any(word in reason for reason in reasons for word in ("popularity", "decade", "tags", "language"))


def test_extra_weights_keep_the_total_at_one():
    prefs = dict(BASE, target_popularity=60, preferred_decade=2010, favorite_mood_tags=["sunny"],
                 preferred_language="english", target_instrumentalness=0.1)
    weights = weights_for(prefs)
    assert math.isclose(sum(weights.values()), 1.0)
    assert weights["genre"] < WEIGHTS["genre"]  # base weights shrink to make room
    assert set(EXTRA_WEIGHTS) <= set(weights)


def test_only_the_extras_that_are_set_get_weight():
    weights = weights_for(dict(BASE, preferred_decade=2010))
    assert "decade" in weights and "popularity" not in weights and "tags" not in weights


def test_popularity_closer_to_target_scores_higher():
    prefs = dict(BASE, target_popularity=80)
    assert score_song(prefs, make_song(popularity=78))[0] > score_song(prefs, make_song(popularity=30))[0]


def test_release_decade_closer_to_preferred_scores_higher():
    prefs = dict(BASE, preferred_decade=1990)
    near, far = score_song(prefs, make_song(release_decade=1990))[0], score_song(prefs, make_song(release_decade=2020))[0]
    assert near > score_song(prefs, make_song(release_decade=2000))[0] > far


def test_mood_tags_score_by_share_of_wanted_tags_matched():
    prefs = dict(BASE, favorite_mood_tags=["sunny", "neon", "dreamy"])
    two = score_song(prefs, make_song(mood_tags=["sunny", "neon"]))[0]
    one = score_song(prefs, make_song(mood_tags=["sunny"]))[0]
    none = score_song(prefs, make_song(mood_tags=["dark"]))[0]
    assert two > one > none


def test_tag_overlap_ignores_case_and_spaces():
    fit, hits = tag_overlap([" Sunny ", "NEON"], ["sunny", "neon", "extra"])
    assert fit == 1.0 and hits == ["neon", "sunny"]
    assert tag_overlap([], ["sunny"]) == (0.0, [])


def test_language_match_earns_points_and_mismatch_earns_none():
    prefs = dict(BASE, preferred_language="Spanish")
    same, _ = score_song(prefs, make_song(language="spanish"))
    other, reasons = score_song(prefs, make_song(language="english"))
    assert same > other
    assert any("language english" in reason and "+0.00" in reason for reason in reasons)


def test_instrumentalness_closer_to_target_scores_higher():
    prefs = dict(BASE, target_instrumentalness=0.9)
    assert score_song(prefs, make_song(instrumentalness=0.9))[0] > score_song(prefs, make_song(instrumentalness=0.0))[0]


def test_song_missing_an_attribute_earns_nothing_for_it_and_does_not_crash():
    prefs = dict(BASE, target_popularity=60, preferred_decade=2010, favorite_mood_tags=["sunny"],
                 preferred_language="english", target_instrumentalness=0.1)
    bare = {k: v for k, v in make_song().items()
            if k not in ("popularity", "release_decade", "mood_tags", "language", "instrumentalness")}
    score, reasons = score_song(prefs, bare)
    assert 0.0 <= score <= 1.0
    assert sum("+0.00" in reason for reason in reasons) >= 5


def test_a_perfect_song_scores_one_with_every_preference_set():
    prefs = {"favorite_genre": "pop", "favorite_mood": "happy", "target_energy": 0.8, "likes_acoustic": False,
             "target_tempo": 120.0, "target_valence": 0.7, "target_danceability": 0.7,
             "target_popularity": 50, "preferred_decade": 2010, "favorite_mood_tags": ["sunny", "neon"],
             "preferred_language": "english", "target_instrumentalness": 0.1}
    perfect = make_song(acousticness=0.0)
    assert math.isclose(score_song(prefs, perfect)[0], 1.0)


def test_all_scores_stay_in_range_for_the_nostalgic_profile():
    for song in load_songs(CSV_PATH):
        assert 0.0 <= score_song(NOSTALGIC_NIGHT_DRIVE_PROFILE, song)[0] <= 1.0


@pytest.mark.parametrize("bad", [
    {"target_popularity": 150}, {"target_popularity": -1}, {"preferred_decade": 1500},
    {"target_instrumentalness": 2}, {"favorite_mood_tags": "neon"}, {"favorite_mood_tags": [1, 2]},
])
def test_invalid_extra_preferences_are_rejected(bad):
    with pytest.raises(ValueError):
        score_song(dict(BASE, **bad), make_song())


def test_nostalgic_profile_picks_the_matching_synthwave_instrumental_first():
    songs = load_songs(CSV_PATH)
    top = recommend_songs(NOSTALGIC_NIGHT_DRIVE_PROFILE, songs, k=2)
    assert top[0][0]["title"] == "Chrome Skyline"
    assert top[0][0]["language"] == "instrumental" and top[0][0]["release_decade"] == 2010


def test_extra_attributes_can_change_who_wins():
    songs = load_songs(CSV_PATH)
    plain = {"favorite_genre": "pop", "favorite_mood": "happy", "target_energy": 0.85}
    spanish = dict(plain, preferred_language="spanish", favorite_mood_tags=["festive", "danceable"],
                   target_popularity=80)
    assert recommend_songs(plain, songs, k=1)[0][0]["title"] != "Calle Sol"
    ranks = [s["title"] for s, _, _ in recommend_songs(spanish, songs, k=40)]
    plain_ranks = [s["title"] for s, _, _ in recommend_songs(plain, songs, k=40)]
    assert ranks.index("Calle Sol") < plain_ranks.index("Calle Sol")


def test_recommender_class_passes_the_new_preferences_through():
    songs = [
        Song(1, "Match", "X", "synthwave", "nostalgic", 0.7, 110, 0.5, 0.7, 0.2,
             popularity=55, release_decade=2010, mood_tags=["nostalgic", "neon"],
             language="instrumental", instrumentalness=0.8),
        Song(2, "Miss", "Y", "synthwave", "nostalgic", 0.7, 110, 0.5, 0.7, 0.2,
             popularity=95, release_decade=1970, mood_tags=["gritty"],
             language="english", instrumentalness=0.0),
    ]
    user = UserProfile("synthwave", "nostalgic", 0.7, False, target_popularity=55, preferred_decade=2010,
                       favorite_mood_tags=["nostalgic", "neon"], preferred_language="instrumental",
                       target_instrumentalness=0.8)
    rec = Recommender(songs)
    assert [s.title for s in rec.recommend(user, k=2)] == ["Match", "Miss"]
    assert "mood tags matched: neon, nostalgic" in rec.explain_recommendation(user, songs[0])


def test_song_dataclass_new_fields_default_to_empty():
    song = Song(1, "T", "A", "pop", "happy", 0.8, 120, 0.7, 0.7, 0.2)
    assert song.popularity is None and song.mood_tags == [] and song.language is None
