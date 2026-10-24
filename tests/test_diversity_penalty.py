"""Tests for the soft diversity penalty (DiversityPenaltyReranker) and the --diversity modes."""
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import main as cli
from recommender import DiversityPenaltyReranker, load_songs, recommend_songs

CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "songs.csv")
LOFI = {"favorite_genre": "lofi", "favorite_mood": "chill", "target_energy": 0.4}


def item(title, score, genre="pop", artist="A"):
    return ({"title": title, "genre": genre, "artist": artist}, score, "base reason")


def test_penalty_is_subtracted_per_earlier_song_of_the_same_genre_and_artist():
    ranked = [item("One", 0.9), item("Two", 0.85), item("Three", 0.8)]
    out = DiversityPenaltyReranker(0.1, 0.2)(ranked, 3)
    assert [s["title"] for s, _, _ in out] == ["One", "Two", "Three"]
    assert out[0][1] == 0.9
    assert math.isclose(out[1][1], 0.85 - 0.1 - 0.2)             # one earlier pop song by A
    assert math.isclose(out[2][1], 0.8 - 2 * 0.1 - 2 * 0.2)       # two earlier of each


def test_a_weaker_song_from_a_new_genre_and_artist_overtakes_a_repeat():
    ranked = [item("Pop 1", 0.9, "pop", "A"), item("Pop 2", 0.88, "pop", "A"), item("Jazz", 0.8, "jazz", "B")]
    out = DiversityPenaltyReranker(0.1, 0.1)(ranked, 3)
    assert [s["title"] for s, _, _ in out] == ["Pop 1", "Jazz", "Pop 2"]


def test_a_much_stronger_song_still_repeats_the_genre():
    ranked = [item("Pop 1", 0.99, "pop", "A"), item("Pop 2", 0.98, "pop", "B"), item("Jazz", 0.5, "jazz", "C")]
    out = DiversityPenaltyReranker(0.1, 0.1)(ranked, 2)
    assert [s["title"] for s, _, _ in out] == ["Pop 1", "Pop 2"]  # soft, not a ban


def test_explanation_says_how_much_was_taken_off_and_why():
    ranked = [item("One", 0.9, "pop", "Neon Echo"), item("Two", 0.85, "pop", "Neon Echo")]
    explanation = DiversityPenaltyReranker(0.1, 0.2)(ranked, 2)[1][2]
    assert explanation.startswith("base reason; diversity penalty -0.30")
    assert "1 earlier pop song" in explanation and "1 earlier by Neon Echo" in explanation
    assert "(s)" not in explanation


def test_first_song_and_unrelated_songs_have_no_penalty_text():
    out = DiversityPenaltyReranker(0.1, 0.1)([item("One", 0.9, "pop", "A"), item("Two", 0.8, "jazz", "B")], 2)
    assert all("diversity penalty" not in explanation for _, _, explanation in out)


def test_scores_never_go_below_zero_and_results_stay_best_first():
    ranked = [item(f"S{i}", 0.2) for i in range(6)]
    out = DiversityPenaltyReranker(0.5, 0.5)(ranked, 6)
    scores = [score for _, score, _ in out]
    assert min(scores) == 0.0 and scores == sorted(scores, reverse=True)


def test_zero_penalties_change_nothing_and_k_is_respected():
    ranked = [item("One", 0.9), item("Two", 0.8), item("Three", 0.7)]
    assert DiversityPenaltyReranker(0.0, 0.0)(ranked, 5) == ranked
    assert len(DiversityPenaltyReranker(0.1, 0.1)(ranked, 2)) == 2
    assert DiversityPenaltyReranker(0.1, 0.1)(ranked, 0) == []


def test_negative_penalties_are_rejected():
    with pytest.raises(ValueError):
        DiversityPenaltyReranker(-0.1, 0.0)
    with pytest.raises(ValueError):
        DiversityPenaltyReranker(0.0, -0.1)


def test_recommend_songs_penalty_arguments_match_the_class():
    songs = load_songs(CSV_PATH)
    via_args = recommend_songs(LOFI, songs, k=5, genre_penalty=0.08, artist_penalty=0.12)
    via_class = recommend_songs(LOFI, songs, k=5, rerankers=[DiversityPenaltyReranker(0.08, 0.12)])
    assert via_args == via_class


def test_default_is_off_so_old_callers_are_unchanged():
    songs = load_songs(CSV_PATH)
    assert recommend_songs(LOFI, songs) == recommend_songs(LOFI, songs, genre_penalty=0.0, artist_penalty=0.0)


def test_penalty_widens_the_lofi_list_without_losing_the_best_song():
    songs = load_songs(CSV_PATH)
    plain = recommend_songs(LOFI, songs, k=5)
    soft = recommend_songs(LOFI, songs, k=5, genre_penalty=0.08, artist_penalty=0.12)
    assert soft[0][0]["title"] == plain[0][0]["title"]
    assert len({s["genre"] for s, _, _ in soft}) > len({s["genre"] for s, _, _ in plain})
    assert len({s["artist"] for s, _, _ in soft}) >= len({s["artist"] for s, _, _ in plain})


def test_penalized_scores_stay_in_range_for_every_profile_and_strategy():
    songs = load_songs(CSV_PATH)
    for prefs in cli.PROFILES.values():
        for strategy in ("balanced", "genre-first", "mood-first", "energy-focused"):
            for _, score, _ in recommend_songs(prefs, songs, k=10, strategy=strategy,
                                               genre_penalty=0.08, artist_penalty=0.12):
                assert 0.0 <= score <= 1.0


def test_penalty_can_be_combined_with_the_hard_cap():
    songs = load_songs(CSV_PATH)
    out = recommend_songs(LOFI, songs, k=5, max_per_genre=2, genre_penalty=0.08, artist_penalty=0.12)
    assert sum(s["genre"] == "lofi" for s, _, _ in out) <= 2


# command line ---------------------------------------------------------

def test_cli_defaults_to_the_penalty(capsys):
    cli.main([])
    out = capsys.readouterr().out
    assert "Diversity: penalty" in out and "diversity penalty -0.08" in out


def test_cli_diversity_modes_switch_behavior(capsys):
    cli.main(["--diversity", "off"])
    off = capsys.readouterr().out
    assert "Diversity: off" in off and "diversity penalty" not in off
    cli.main(["--diversity", "cap"])
    cap = capsys.readouterr().out
    assert "Diversity: cap" in cap and "diversity penalty" not in cap
    assert off != cap


def test_cli_rejects_an_unknown_diversity_mode(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--diversity", "random"])
    assert "invalid choice" in capsys.readouterr().err


def test_cli_compare_respects_the_diversity_mode(capsys):
    cli.main(["--compare", "--diversity", "off"])
    off = capsys.readouterr().out
    cli.main(["--compare", "--diversity", "penalty"])
    assert off != capsys.readouterr().out


def test_artist_only_mode_penalizes_a_repeated_artist_but_never_a_repeated_genre(capsys):
    songs = load_songs(CSV_PATH)
    prefs = cli.HIGH_ENERGY_POP_PROFILE
    plain = recommend_songs(prefs, songs, k=5)
    out = recommend_songs(prefs, songs, k=5, **cli.diversity_options("artist"))
    assert [s["artist"] for s, _, _ in plain][:2] == ["Neon Echo", "Neon Echo"]
    second_neon = next(item for item in out if item[0]["title"] == "Dancefloor Mirage")
    assert "1 earlier by Neon Echo" in second_neon[2] and "earlier pop song" not in second_neon[2]
    assert math.isclose(second_neon[1], dict((s["title"], sc) for s, sc, _ in plain)["Dancefloor Mirage"] - cli.ARTIST_PENALTY)
    assert [s["title"] for s, _, _ in out].index("Dancefloor Mirage") > 1  # moved down, still present
    cli.main(["--diversity", "artist"])
    assert "Diversity: artist" in capsys.readouterr().out


def test_artist_penalty_alone_leaves_unique_artists_untouched():
    ranked = [item("One", 0.9, "pop", "A"), item("Two", 0.8, "pop", "B"), item("Three", 0.7, "pop", "C")]
    assert DiversityPenaltyReranker(0.0, 0.2)(ranked, 3) == ranked


def test_diversity_options_helper():
    assert cli.diversity_options("off") == {}
    assert cli.diversity_options("artist") == {"artist_penalty": cli.ARTIST_PENALTY}
    assert set(cli.diversity_options("cap")) == {"max_per_genre", "max_per_artist"}
    assert set(cli.diversity_options("penalty")) == {"genre_penalty", "artist_penalty"}
