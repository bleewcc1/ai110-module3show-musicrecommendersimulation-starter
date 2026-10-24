"""Tests for the switchable ranking strategies (balanced, genre-first, mood-first, energy-focused)."""
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import main as cli
from recommender import (
    DEFAULT_STRATEGY,
    STRATEGIES,
    STRATEGY_NAMES,
    WEIGHTS,
    load_songs,
    recommend_songs,
    score_song,
    weights_for,
)

CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "songs.csv")
PREFS = {"favorite_genre": "pop", "favorite_mood": "happy", "target_energy": 0.8}


def song(**overrides):
    base = {"id": 1, "title": "T", "artist": "A", "genre": "pop", "mood": "happy", "energy": 0.8,
            "tempo_bpm": 120.0, "valence": 0.7, "danceability": 0.7, "acousticness": 0.2}
    base.update(overrides)
    return base


def test_there_are_at_least_three_strategies_including_the_default():
    assert DEFAULT_STRATEGY == "balanced"
    assert set(STRATEGY_NAMES) >= {"balanced", "genre-first", "mood-first", "energy-focused"}


@pytest.mark.parametrize("name", list(STRATEGIES))
def test_every_strategy_sums_to_one_and_is_positive(name):
    assert math.isclose(sum(STRATEGIES[name].values()), 1.0)
    assert all(weight > 0 for weight in STRATEGIES[name].values())
    assert set(STRATEGIES[name]) == set(WEIGHTS)


def test_each_strategy_puts_the_most_weight_on_its_own_feature():
    assert max(STRATEGIES["genre-first"], key=STRATEGIES["genre-first"].get) == "genre"
    assert max(STRATEGIES["mood-first"], key=STRATEGIES["mood-first"].get) == "mood"
    assert max(STRATEGIES["energy-focused"], key=STRATEGIES["energy-focused"].get) == "energy"


def test_default_and_balanced_match_the_original_scoring():
    pop = song()
    assert score_song(PREFS, pop) == score_song(PREFS, pop, "balanced") == score_song(PREFS, pop, None)
    assert weights_for(PREFS) == WEIGHTS
    songs = load_songs(CSV_PATH)
    assert recommend_songs(PREFS, songs) == recommend_songs(PREFS, songs, strategy="balanced")


def test_unknown_strategy_is_rejected():
    with pytest.raises(ValueError):
        score_song(PREFS, song(), "loudest-first")
    with pytest.raises(ValueError):
        recommend_songs(PREFS, [song()], strategy="loudest-first")


def test_genre_first_prefers_the_right_genre_over_the_right_mood_and_energy():
    right_genre = song(id=1, title="Right Genre", mood="melancholy", energy=0.4)
    right_mood = song(id=2, title="Right Mood", genre="hip hop", mood="happy", energy=0.8)
    assert score_song(PREFS, right_genre, "genre-first")[0] > score_song(PREFS, right_mood, "genre-first")[0]
    assert score_song(PREFS, right_genre, "mood-first")[0] < score_song(PREFS, right_mood, "mood-first")[0]


def test_energy_focused_prefers_the_closest_energy_over_the_right_genre():
    labels = song(id=1, title="Labels", energy=0.3)  # pop + happy, but far from the energy target
    sound = song(id=2, title="Sound", genre="hip hop", energy=0.8)  # right mood and energy, other genre
    assert score_song(PREFS, sound, "energy-focused")[0] > score_song(PREFS, labels, "energy-focused")[0]
    assert score_song(PREFS, sound, "genre-first")[0] < score_song(PREFS, labels, "genre-first")[0]


def test_scores_stay_between_zero_and_one_for_every_strategy_and_profile():
    songs = load_songs(CSV_PATH)
    for strategy in STRATEGY_NAMES:
        for prefs in cli.PROFILES.values():
            for s in songs:
                assert 0.0 <= score_song(prefs, s, strategy)[0] <= 1.0


def test_extra_attribute_weights_still_sum_to_one_under_every_strategy():
    prefs = dict(PREFS, target_popularity=60, preferred_decade=2010, favorite_mood_tags=["sunny"],
                 preferred_language="english", target_instrumentalness=0.1)
    for strategy in STRATEGY_NAMES:
        assert math.isclose(sum(weights_for(prefs, strategy).values()), 1.0)


def test_strategies_change_the_lists_but_agree_on_obvious_winners():
    songs = load_songs(CSV_PATH)
    lists = {s: [x["title"] for x, _, _ in recommend_songs(cli.POP_HAPPY_PROFILE, songs, k=5, strategy=s)]
             for s in STRATEGY_NAMES}
    assert len({tuple(titles) for titles in lists.values()}) > 1  # the modes differ
    assert all(titles[0] == "Sunrise City" for titles in lists.values())  # the only pop + happy song wins everywhere


def test_genre_first_keeps_a_rock_listener_in_the_rock_family():
    songs = load_songs(CSV_PATH)
    top5 = recommend_songs(cli.INTENSE_ROCK_PROFILE, songs, k=5, max_per_genre=2, max_per_artist=2,
                           strategy="genre-first")
    assert sum(s["genre"] in ("rock", "metal") for s, _, _ in top5) >= 4


def test_mood_first_follows_the_mood_across_genres():
    songs = load_songs(CSV_PATH)
    top5 = recommend_songs(cli.POP_HAPPY_PROFILE, songs, k=5, strategy="mood-first")
    assert len({s["genre"] for s, _, _ in top5}) >= 4
    assert sum(s["mood"] == "happy" for s, _, _ in top5) >= 4


# command line ---------------------------------------------------------

def test_cli_strategy_flag_switches_the_mode(capsys):
    cli.main(["--strategy", "mood-first"])
    out = capsys.readouterr().out
    assert "Ranking strategy: mood-first" in out
    assert "Sunrise City" in out


def test_cli_default_mode_is_balanced(capsys):
    cli.main([])
    assert "Ranking strategy: balanced" in capsys.readouterr().out


def test_cli_compare_shows_every_strategy_side_by_side(capsys):
    cli.main(["--compare"])
    out = capsys.readouterr().out
    for name in STRATEGY_NAMES:
        assert name in out
    assert out.count("Chill Lofi") == 1 and "Ranking strategy" not in out


def test_cli_list_strategies_describes_each_mode(capsys):
    cli.main(["--list-strategies"])
    out = capsys.readouterr().out
    assert all(name in out for name in STRATEGY_NAMES)


def test_cli_rejects_an_unknown_strategy(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--strategy", "bogus"])
    assert "invalid choice" in capsys.readouterr().err


def test_cli_adversarial_flag_still_works(capsys):
    cli.main(["--adversarial", "--strategy", "energy-focused"])
    out = capsys.readouterr().out
    assert "Rejected invalid profile" in out and "Empty Profile" in out
