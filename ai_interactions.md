# AI Interactions Log

> **Stretch features only.** Only fill in the sections that apply to stretch features you attempted. If you did not attempt a stretch feature, leave its section blank or delete it. This file is not required for the core project.

---

## Agentic Workflow (SF8)

> Document your experience using an AI agent (e.g., Cursor Agent, Claude, Copilot) to make multi-step changes autonomously.

**What task did you give the agent?**

I asked an AI agent (Claude Code, running in VS Code) to build a small content-based music recommender with me, one step at a time, and then to test, stress-test and document it. The work covered:

- a taste profile that can tell "intense rock" from "chill lofi"
- a scoring recipe, with weights and a mermaid data-flow chart
- the code: `load_songs`, `score_song` and `recommend_songs`
- terminal output, tests and a sample-output section
- experiments that change one thing at a time, and a model card
- five new song attributes (popularity, release decade, detailed mood tags, language, instrumentalness)
- switchable ranking modes and a Strategy-pattern refactor that keeps the code modular

The agent could read and edit files, run `python -m src.main` and `pytest`, and run small scripts to measure results.

**Prompts used:**

Each prompt was one clear step. These are the key ones, in order:

1. "the profile should be a dictionary containing target values for the features you identified e.g., favorite_genre, favorite_mood, target_energy." and "it should allow the system to differentiate between 'intense rock' and 'chill lofi,' or if the profile is too narrow."
2. "Describe the 'algorithm recipe'", then "How much should a 'Mood' match count compared to a 'Genre' match?", then "suggest a few to handle for borderline cases" and "please make the changes".
3. "Sketch a quick map of the data flow ... Input (User Prefs), then Process (The Loop ...), then Output (The Ranking: Top K Recommendations) using mermaid charts", followed by "please review the chart that it's accurate".
4. "implement the load_songs function to use Python's csv module ... numerical values ... must be converted to floats or integers", then "yes, make the data type consistent and review for other data type for consistency".
5. "for score_song(user_prefs, song) function implement based on your 'Algorithm Recipe' ... return both a numeric score and a list of 'reasons'", then "in the recommend_songs function ... use your score_song function as a 'judge' for every single song ... then sort", then "use the most 'Pythonic' way to loop through all songs".
6. "format the output of your recommendations for a clean, readable layout in the terminal", then "Run the script: python -m src.main. Verify that the top results match what you would expect for the default 'pop/happy' profile."
7. "please review and run test case" (run several times as the code grew).
8. "Run the recommender for each profile and observe the top 5 results in your terminal and provide suggestions", then "Compare the recommendations for at least one profile to your own musical intuition. Do the results 'feel' right?"
9. "Choose one change to test your system's sensitivity: Weight Shift ... or Feature Removal ...", then "apply one of these experimental changes ... describe the specific logic change ... and please verify that the math remains valid."
10. "identify potential 'filter bubbles' or biases in your current scoring logic. For example, does your system ignore certain types of users because of how you calculate the 'energy gap'?", then "implement the diversity rule".
11. "Introduce 5 or more complex attributes to your dataset ... such as Song Popularity (0-100), Release Decade, or Detailed Mood Tags ... Update both data/songs.csv and the scoring logic in src/recommender.py so scoring accounts for the new attributes."
12. Documentation prompts for `README.md` and `model_card.md`: the sample output as fenced code blocks, a pair-by-pair comparison of profiles "in plain language, as if explaining why Gym Hero keeps showing up for Happy Pop", and a personal reflection.
13. "Build two or more different ranking strategies (e.g., 'Genre-First,' 'Mood-First,' or 'Energy-Focused') so a user can switch between modes".
14. "brainstorm a design pattern (like a simple 'Strategy' pattern) that keeps the code modular", then "review this approach and test", then "please implement these changes".
15. "Implement a 'Diversity Penalty' that prevents the recommender from suggesting too many songs from the same artist or genre in the top results", then "a rule to penalize a song's score if its artist is already present in the top recommendations list".
16. "Improve the readability of your terminal output by providing a formatted table or summary. Use a library like tabulate or simple ASCII formatting to display your top recommendations and the table must include the 'reasons' for each score."

**What did the agent generate or change?**

- **`src/recommender.py`**
  - **Core scoring:** `load_songs` with type conversion. `score_song` returns a score and a list of reasons, with a Gaussian "closeness" for energy, tempo, valence and danceability. Related genres and moods earn half credit, and songs that match neither get a 0.5x penalty.
  - **Ranking:** `recommend_songs` ranks with a generator expression and `sorted`. It also takes optional diversity caps (at most 2 songs per genre and per artist).
  - **Validation and warnings:** Label normalization, range checks for numeric targets, and `profile_coverage` and `confidence_warnings`.
  - **Weight shift:** The weight experiment (genre halved, energy doubled), rescaled so the weights sum to 1.
  - **Extra attributes:** `weights_for` and `tag_overlap`, plus five optional scoring terms (popularity, decade, mood tags, language, instrumentalness). Extra weights shrink the base weights so the total stays at 1.
  - **Docstrings and classes:** One-line docstrings on every function, and updates to the `Song`, `UserProfile` and `Recommender` classes.
  - **Ranking modes:** Four switchable modes (`balanced`, `genre-first`, `mood-first`, `energy-focused`), each a set of weights that sums to 1.
  - **Diversity penalty:** A `DiversityPenaltyReranker` that subtracts 0.08 per earlier same-genre song and 0.12 per earlier same-artist song, picking greedily, with a `diversity penalty -0.12 (1 earlier by Neon Echo)` line in the reasons.
  - **Strategy refactor:** Per-feature scorer objects, a `SCORERS` registry, a separate no-match adjuster and a `DiversityReranker` (details in the Design Pattern section below).
- **`src/main.py`**
  - **Output:** A clean terminal layout with score bars and "Why" bullets, plus a "weak match" label for low scores.
  - **Profiles:** Five profiles (Chill Lofi, Intense Rock, High-Energy Pop, Pop Happy and Nostalgic Night Drive).
  - **Adversarial mode:** Adversarial profiles run with `--adversarial`.
  - **Table output:** `format_table()` prints rank, title, artist, score and one line per reason in a simple ASCII table (no extra library), plus a one-line summary. `--format detailed` keeps the older layout.
  - **Mode switching:** `--strategy`, `--diversity` (penalty, artist, cap, off), `--compare` (the top 5 under every mode, side by side) and `--list-strategies`.
  - **Imports:** A try/except import fallback so both `python -m src.main` and `python src/main.py` work.
- **`data/songs.csv`:** Grew from 20 to 40 songs, then gained five new columns for every song.
- **Tests:** 161 tests in `tests/test_scoring.py`, `tests/test_taste_profile.py`, `tests/test_recommender.py`, `tests/test_extra_attributes.py`, `tests/test_strategies.py`, `tests/test_design_pattern.py` and `tests/test_diversity_penalty.py` and `tests/test_table_output.py`.
- **`README.md`:** A plan, feature tables, mermaid chart, algorithm recipe, worked example, expected biases, sample output (one fenced block per profile), six experiments, a section on how the code is organized and a personal reflection.
- **`model_card.md`:** Every section filled in, including a pair-by-pair profile comparison and the Gym Hero explanation.
- **Commands run:** `python -m src.main`, `pytest`, and small throwaway scripts that measured weight changes, score ranges, top-5 lists and per-genre results.

**What did you verify or fix manually?**

The agent's first drafts had real mistakes. I found them by running the code and comparing against the docs:

- **A wrong number in the README.** It said a poor-fit song was "halved to 0.22". Running the code showed the real score was 0.03, so I corrected it.
- **A wrong claim about weights.** A bias note said a small weight change would swap two songs. Measuring it showed this was false under the current weights, and I replaced it with measured values.
- **A command that crashed.** `python -m src.main` raised `ModuleNotFoundError`. The first fix changed the README to a different command. I then fixed the imports in `main.py` so the original command works.
- **A flowchart that did not match the code.** I asked for a review, and it found that the profile was wrongly feeding the loop condition and the "too narrow" warning was missing.
- **Stale text.** The README still said "10-song catalog" after the catalog grew. Each time the weights or catalog changed, old numbers in the README and model card had to be found and updated.
- **A macOS-only problem.** `sed -i` failed on macOS, so that edit was done another way.
- **An ambiguous request.** My docstring request was cut off mid-sentence. The agent guessed which functions I meant, so I should check that guess.

How I checked the results:

- **Tests and reruns:** I reran the test suite after every change (it ended at 161 passing) and reran `python -m src.main` after changes to code or data.
- **Sample output:** The README sample output was generated from a real run, not typed by hand.
- **Math checks:** Weights sum to 1.0. All scores stay between 0 and 1. A song that matches every target scores exactly 1.0. Extra attributes do not change the score of a profile that does not use them.
- **Claims backed by measurement:** I re-measured every claim about bias or ranking before keeping it. Examples are the per-genre averages (hip hop and r&b 0.43, lofi 0.75) and the 40-profile sweep that gave 40 different #1 songs.
- **Judgment calls:** I decided whether results "feel right" myself, using the songs' labels and numbers, because the agent cannot hear music. The tests check the math, not the taste.
- **Verdicts on changes:** I treated the weight shift as "different, not clearly more accurate". That verdict came from comparing the top 5 lists, not from the agent's first guess.
- **Still not checked:** The song data is made up, so none of the results say anything about real listeners.

---

## How AI Helped (summary)

**Where the AI saved the most time**

- **Turning a plan into working code.** I described each step in plain words (the recipe, the data flow, the three core functions), and the AI produced a first version I could run right away. That let me spend my time judging results instead of typing boilerplate.
- **Writing tests as the code grew.** It wrote 128 tests, including edge cases I might have skipped: `k` larger than the catalog, negative `k`, an empty catalog, out-of-range numbers, blank preferences and catalogs with missing columns.
- **Running experiments quickly.** It wrote throwaway scripts to compare weights, strategies and profiles (the weight shift, the 40-profile bias sweep, the 49,760-combination refactor check). Each would have taken me much longer by hand.
- **Keeping documents in sync.** Every time the weights, the catalog or the code changed, it found the old numbers in the README and model card and updated them. It regenerated the sample output from real runs instead of retyping it.
- **Brainstorming and explaining.** It compared design-pattern options, explained why "Gym Hero" keeps showing up for happy-pop listeners, and found biases I had not thought of, like the hand-written genre families and the thin middle of the energy range.
- **Writing for different readers.** It wrote the model card in short, plain sentences and the Gym Hero explanation for a non-programmer.

**Where I had to double-check it**

- **Numbers in documents.** The first README draft contained a wrong score (0.22 instead of 0.03) and a wrong claim about a weight swap. Both looked plausible until I ran the code. My rule became: if a document states a number, run the code and compare.
- **Commands.** `python -m src.main` crashed with `ModuleNotFoundError`. The AI first "fixed" it by changing the README, which hid the problem instead of fixing it.
- **Taste.** The AI cannot hear music. It judged whether results "feel right" from labels and numbers, so I treated those judgments as opinions and checked them against the scores.
- **Its own work.** The AI reviewed its own design and found a gap (the no-match penalty needs information from other scorers) and a bug (blank preferences reserved weight and lowered scores). I only trusted the refactor after it passed an exact comparison with the old code.
- **Wording of my own prompts.** When a prompt was cut off or vague (the docstring request), the AI guessed. A short check of that guess prevented a wrong assumption.

**What I learned about working with an AI agent**

- Small, clear steps worked better than one big request. Each step could be run and checked before the next began.
- The best use of the AI was as a fast first drafter and a second pair of eyes. It was not a source of truth.
- Asking it to review its own plan ("review this approach and test") caught problems before they were built into the code.
- Tests and exact comparisons made it safe to let the AI change a lot of code, because I could see right away if behavior changed.

---

## Design Pattern (SF10)

> Document how AI helped you choose or implement a design pattern.

**Which design pattern did you use?**

The **Strategy pattern**, used in three places in `src/recommender.py`:

1. **Feature scorers (the main use).** Each feature of a song is judged by its own small object that follows one interface (`FeatureScorer`). A list called `SCORERS` holds them, and `score_song()` just loops over the list.
2. **Re-rankers.** Variety is a separate step after ranking. `DiversityReranker` is one strategy, and `recommend_songs()` accepts a `rerankers=[...]` list so others can be plugged in.
3. **Ranking modes.** The four modes (`balanced`, `genre-first`, `mood-first`, `energy-focused`) are data-only strategies: sets of weights chosen by name.

I also used a small **adjuster** step, `apply_no_match_penalty`, for the "halve the score if no label matches" rule.

**How did AI help you brainstorm or implement it?**

I asked the AI to "brainstorm a design pattern (like a simple 'Strategy' pattern) that keeps the code modular", pointing at `src/recommender.py`. It started from the code I already had. `score_song()` was one long function with a block of `if` statements per feature, and every block repeated the same three steps: compute a fit from 0 to 1, multiply by a weight, add a reason. The AI proposed four options and compared them:

| Option | Idea | The AI's view |
|---|---|---|
| A. Strategy for what to score | One scorer object per feature | Best fit: removes the repeated blocks |
| B. Strategy for how much it counts | Make the ranking modes real objects | Small gain, because they already worked as data |
| C. Decorator / post-ranker | Move the diversity rule into its own re-ranking step | Good fit, and small |
| D. Registry / plugin | Scorers register themselves by name | Nice, but needs A first |

It recommended A plus C, with a registry as a bonus, because it keeps every score identical so the existing tests act as a safety net. I then asked it to "review this approach and test". That review improved the design in two ways:

- **A gap in the first sketch.** The "halve the score if no genre or mood matched" rule needs to know the results of two other scorers, which a plain "fit" interface cannot express. The fix was to let each scorer return a result that includes the match kind, and to handle the penalty in a separate adjuster.
- **A real bug.** Reading the code side by side showed that "is this preference set?" was checked in two different places (once to reserve weight, once to score). A blank `preferred_language` or an all-spaces tag list reserved weight for a term that never scored, so every score dropped (0.8054 became 0.7897 and 0.7671). Giving each scorer one `applies()` method fixed it.

I decided to go ahead after that review ("please implement these changes"). The AI wrote the refactor and I checked it (see below).

**How does the pattern appear in your final code?**

- **`FeatureScorer`** (interface), with `LabelScorer`, `EnergyScorer`, `AcousticScorer`, `ClosenessScorer`, `TagScorer` and `LanguageScorer`. Each has `applies()` and `score()`, and returns a `TermResult` (points, reason, match).
- **`SCORERS`** is the registry list. `score_song()` loops over it, and `weights_for()` uses the same `applies()` check. To add a feature, write a scorer, append it to `SCORERS`, and add a weight.
- **`apply_no_match_penalty()`** is the adjuster step for the 0.5x rule.
- **`DiversityReranker`** and the `Reranker` type, used by `recommend_songs(..., max_per_genre, max_per_artist, rerankers=[...])`.
- **`STRATEGIES`** and `base_weights()` hold the four ranking modes, chosen with `strategy=` or `--strategy` on the command line.
- **Tests:** `tests/test_design_pattern.py` (16 tests) covers the scorer interface, adding a brand-new scorer without editing `score_song()`, the blank-preference fix, the adjuster and the re-rankers.

**How I verified the refactor kept behavior the same**

- I built the design first as a throwaway prototype outside the repo and compared it with the real `score_song` on 49,760 combinations (311 profiles, including 300 random ones, times 4 modes times 40 songs). Scores and reasons matched exactly with 0 mismatches.
- After the real refactor I reran the same comparison (0 mismatches again) and confirmed that the README sample output is identical to a fresh run.
- All 128 tests pass (112 before the refactor, plus 16 new).
- The only intended behavior change is the blank-preference fix. A test confirms that a blank preference now scores exactly like no preference.

