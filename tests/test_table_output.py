"""Tests for the ASCII results table (format_table) and the --format flag."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import main as cli
from recommender import load_songs, recommend_songs

CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "songs.csv")


def results_for(prefs, **kwargs):
    return recommend_songs(prefs, load_songs(CSV_PATH), k=5, **kwargs)


def table_lines(results):
    return cli.format_table(results).splitlines()


def test_table_has_a_header_row_and_borders():
    lines = table_lines(results_for(cli.TASTE_PROFILE))
    assert lines[0] == lines[2] and set(lines[0]) <= {"+", "-"}
    for header in cli.TABLE_HEADERS:
        assert header in lines[1]
    assert lines[1].startswith("| #") and lines[1].endswith("|")


def test_table_contains_every_title_artist_score_and_reason():
    for prefs in cli.PROFILES.values():
        results = results_for(prefs, **cli.diversity_options("penalty"))
        text = cli.format_table(results)
        for song, score, explanation in results:
            assert song["title"] in text and song["artist"] in text
            assert f"{score:.2f}" in text
            for reason in explanation.split("; "):
                # a long reason may wrap, so compare with the whitespace squeezed out
                assert "".join(reason.split()) in "".join(text.replace("|", "").split())


def test_every_reason_of_every_result_appears_in_order():
    results = results_for(cli.NOSTALGIC_NIGHT_DRIVE_PROFILE)
    lines = table_lines(results)
    cells = ["".join(line.split("|")[5].split()) for line in lines if line.startswith("|")]
    joined = "".join(cells)
    position = 0
    for _, _, explanation in results:
        for reason in explanation.split("; "):
            found = joined.find("-" + "".join(reason.split()), position)
            assert found >= position, reason
            position = found


def test_all_table_lines_are_equally_wide_and_within_the_layout():
    width = sum(cli.TABLE_WIDTHS) + 3 * len(cli.TABLE_WIDTHS) + 1
    for prefs in list(cli.PROFILES.values()) + list(cli.ADVERSARIAL_PROFILES.values()):
        results = results_for(prefs)
        framed = [line for line in table_lines(results) if line[:1] in "+|"]
        assert framed and all(len(line) == width for line in framed)


def test_one_reason_per_line_and_long_reasons_wrap_inside_the_column():
    lines = table_lines(results_for(cli.NOSTALGIC_NIGHT_DRIVE_PROFILE))
    reason_cells = [line.split("|")[5].rstrip() for line in lines if line.startswith("|")][1:]
    assert all(len(cell) <= cli.TABLE_WIDTHS[4] + 2 for cell in reason_cells)
    assert any(cell.strip().startswith("- mood tags matched") for cell in reason_cells)


def test_weak_matches_are_flagged_and_strong_ones_are_not():
    songs = load_songs(CSV_PATH)
    weak = recommend_songs({"favorite_genre": "polka", "favorite_mood": "zany", "target_energy": 0.5}, songs, k=2)
    assert "weak" in cli.format_table(weak)
    assert "weak" not in cli.format_table(results_for(cli.INTENSE_ROCK_PROFILE))


def test_summary_line_reports_average_genres_and_artists():
    results = results_for(cli.TASTE_PROFILE, **cli.diversity_options("penalty"))
    summary = table_lines(results)[-1]
    average = sum(score for _, score, _ in results) / len(results)
    assert summary.startswith(f"Summary: average score {average:.2f}")
    assert f"{len({s['genre'] for s, _, _ in results})} genres" in summary
    assert f"{len({s['artist'] for s, _, _ in results})} artists" in summary


def test_empty_results_make_an_empty_table_without_a_summary():
    lines = table_lines([])
    assert len(lines) == 3 and not any(line.startswith("Summary") for line in lines)


def test_diversity_penalty_reason_appears_in_the_table():
    text = cli.format_table(results_for(cli.TASTE_PROFILE, **cli.diversity_options("penalty")))
    assert "diversity penalty -0.08" in text


def test_cli_prints_tables_by_default(capsys):
    cli.main([])
    out = capsys.readouterr().out
    assert out.count("| Title") == len(cli.PROFILES)
    assert out.count("Summary: average score") == len(cli.PROFILES)
    assert "Why:" not in out


def test_cli_detailed_format_keeps_the_original_layout(capsys):
    cli.main(["--format", "detailed"])
    out = capsys.readouterr().out
    assert "Why:" in out and "| Title" not in out and "[####" in out


def test_cli_rejects_an_unknown_format(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--format", "html"])
    assert "invalid choice" in capsys.readouterr().err


def test_table_works_with_every_strategy_and_diversity_mode(capsys):
    for strategy in ("balanced", "genre-first", "mood-first", "energy-focused"):
        for mode in cli.DIVERSITY_MODES:
            cli.main(["--strategy", strategy, "--diversity", mode, "--adversarial"])
            out = capsys.readouterr().out
            assert "| Title" in out and "Traceback" not in out
