# 🎧 Model Card: Music Recommender Simulation

## 1. Model Name  

Give your model a short, descriptive name.  
Example: **VibeFinder 1.0**  

---

## 2. Intended Use  

Describe what your recommender is designed to do and who it is for. 

Prompts:  

- What kind of recommendations does it generate  
- What assumptions does it make about the user  
- Is this for real users or classroom exploration  

---

## 3. How the Model Works  

Think of the recommender as a judge at a talent show who has a short checklist and gives every song a mark out of 100. It judges each song in the catalog one at a time, writes down why it gave each mark, and then hands you the five songs with the highest marks.

**What it knows about a song.** Each song has a genre (like lofi or rock), a mood (like chill or intense), and a few numbers describing how it sounds: how energetic it is, how acoustic it is, how fast it is, how happy it sounds, and how danceable it is.

**What it knows about you.** You tell it your favorite genre, your favorite mood, how energetic you want the music to feel, and whether you like acoustic sounds. You can also give it a target speed, happiness and danceability, but those are optional.

**How a song earns its mark.** The judge hands out points for each thing on the checklist. (The app shows points as decimals, so 12 points appears as +0.12 and a perfect song scores close to 1.00.)

- **Genre (up to 12 points).** A song gets the full points if it is your favorite genre. If it is a close cousin, like indie pop for a pop fan, it gets half.
- **Mood (up to 19 points).** The same idea: full points for your favorite mood, half for a similar one (relaxed counts as similar to chill).
- **Energy (up to 49 points).** Here the judge asks "how close is this song to the energy you wanted?", not "is it high or low?". A song right on your target gets all the points, and the points shrink the further away it is in either direction. That way a calm listener is not handed a loud song just because loud songs have "more" energy.
- **Acoustic feel (up to 11 points).** If you like acoustic music, the more acoustic the song, the more points. If you don't, it works the other way around.
- **Speed, happiness and danceability (up to 9 points together).** Only used if you gave targets, and they work like energy: closer to your target means more points. They are small, so mostly they break ties between songs that are otherwise equal.

**One penalty.** If a song matches neither your genre nor your mood, not even as a close cousin, its total is cut in half. A song that merely happens to have the right energy should not beat a song that really fits your taste. These songs are labeled "closest fit only" so you can see they are filler.

**Picking the winners.** After every song has a mark, the judge lines them up from highest to lowest and shows the top five. If two songs tie, they are listed alphabetically so the result is the same every time. Each song comes with its list of reasons, such as "genre match, +0.12", so you can see exactly why it ranked where it did.

**What I changed from the starter logic.** The starter only gave a song points for an exact genre or mood match, and nothing otherwise. I made four changes:

1. Energy is scored by closeness to your target, not by "more is better".
2. Close-cousin genres and moods earn half credit instead of zero, so a jazz "relaxed" song can still reach a "chill lofi" listener.
3. Songs that match neither genre nor mood are halved.
4. Speed, happiness and danceability can be used as small tie-breakers, and the app warns you when your taste is so narrow that fewer than five songs in the catalog really fit it.

---

## 4. Data  

Describe the dataset the model uses.  

Prompts:  

- How many songs are in the catalog  
- What genres or moods are represented  
- Did you add or remove data  
- Are there parts of musical taste missing in the dataset  

---

## 5. Strengths  

Where does your system seem to work well  

Prompts:  

- User types for which it gives reasonable results  
- Any patterns you think your scoring captures correctly  
- Cases where the recommendations matched your intuition  

---

## 6. Limitations and Bias 

**Biggest weakness: the hand-written genre and mood families favor some listeners.** Only pop, rock, lofi, folk/country/blues and edm/synthwave have related genres that earn half credit, while classical, hip hop, latin, r&b and reggae have none, and the moods "confident", "moody" and "romantic" have none either. When I built a listener for each genre, hip hop and r&b listeners had a top 5 that averaged only 0.43, against 0.75 for lofi, because they get all-or-nothing matching on one or two songs and the rest of the list is padded with penalized near-misses. A lofi fan, by contrast, gets 9 songs that earn genre credit. This happens because I wrote the families myself from a pop-and-rock-centered view of music and the catalog has only 1-2 songs in most genres, so the system serves some tastes much better than others.

Other limitations:

- **Energy now outweighs the labels.** After the weight-shift experiment energy is about 49% of the score, genre 12% and mood 19%. A song with the right energy and mood can win without the right genre, such as Bass Cathedral (EDM) reaching Intense Rock's top 5 and Highway Daydream (rock) reaching Pop Happy's. Energy uses a single target, so a listener who likes both calm and intense music cannot be described.
- **Closed vocabulary.** Only the labels in the 40-song catalog (and the families in `GENRE_FAMILIES` / `MOOD_FAMILIES`) earn credit. Any other genre or mood scores zero, so the user's request is partly ignored.
- **Small catalog.** Lofi has 6 songs and pop and rock 5 each, but most other genres have 1-2, so "genre match" is nearly a hard-coded answer for them.
- **Weak numeric terms can't veto.** Valence, tempo and danceability are 3-4% each. A melancholy listener who asks for valence 0.95 still gets the 0.35-valence folk song at 0.90.
- **The 0.5x penalty is a cliff.** Songs with no genre/mood match are halved, so a loosely related label can beat a much better audio fit.

---

## 7. Evaluation  

I evaluated the recommender three ways: by checking the four everyday profiles against my own musical intuition, by stress-testing it with adversarial profiles, and by running controlled experiments that change one thing at a time. The 67 automated tests in `tests/` cover scoring, ranking, loading, the profiles, the adversarial cases and the diversity rule, and all of them pass.

### Profiles I tested

- **Four everyday listeners:** Chill Lofi (calm, acoustic study music), Intense Rock (loud, fast, not acoustic), High-Energy Pop (bright, danceable party pop) and Pop Happy (the sparse starter profile with only genre, mood and energy).
- **Six adversarial listeners:** Sad Ravers (wants sad music at energy 0.9), Typo Lofi (messy capitalization and spaces), Metalhead Sleeper (metal, peaceful, energy 0.1), Sad Sunshine (melancholy but wants a very happy valence of 0.95), Unknown Tastes (polka / zany) and an Empty Profile (no genre or mood).
- **Three invalid listeners:** energy 1.5, energy -1 and tempo 400, to check that bad numbers are rejected.
- **Forty generated listeners:** one built from each song's own genre, mood and energy, to see whether one song wins everywhere. I also built one listener per genre to compare how well each genre is served, and swept target energies from 0.05 to 0.95.

### Everyday profiles

Run `python -m src.main` to see the top 5 for Chill Lofi, Intense Rock, High-Energy Pop and Pop Happy, each with its score and reasons.

| Profile | Current #1 | Does it feel right? |
|---|---|---|
| Chill Lofi | Library Rain (0.97) | Yes. Calm, acoustic, lofi and chill. The calm ambient and jazz songs make the list once the diversity rule widens it. |
| Intense Rock | Storm Runner (0.99) | Yes. The top three are rock or metal with intense moods and energy of 0.89 or higher. |
| High-Energy Pop | Sunrise City (0.96) | The top three feel right. Gym Hero is workout pop, not happy, so it fits less well. |
| Pop Happy | Sunrise City (0.81) | Mostly right, but #5 (Highway Daydream, a rock song) is there mainly on mood and energy. |

Chill Lofi and Intense Rock share no songs in their top 5, so the system does tell "chill lofi" from "intense rock". The calmest songs (Moonlit Sonata, Spacewalk Thoughts) were the main miss under the original weights.

### Experiments

| Experiment | What changed | Result |
|---|---|---|
| Bigger catalog | 20 to 40 songs | Intense Rock went from 3 genre or mood matches (two weak fallbacks scoring 0.22 and 0.20) to 9 matches, with no "too narrow" warning. Lists got more meaningful but the genre bias became more visible. |
| Weight shift | Genre halved (0.28 to 0.14), energy doubled (0.28 to 0.56), rescaled to sum to 1 | Different, not clearly more accurate. The #1 pick did not change for any profile and one song entered or left three of the four top 5s. It helped Chill Lofi (Spacewalk Thoughts entered) and hurt Intense Rock (Bass Cathedral, an EDM song, entered). Math check: weights sum to 1.0 and all scores stay between 0.01 and 0.99. |
| Diversity rule | At most 2 songs per genre and 2 per artist in a top 5 | More varied lists for a small cost: distinct genres rose by one in three profiles and the average score dropped by 0.01-0.04. It cannot help genres with few songs. |
| Bias audit | A profile for each genre, plus a sweep of target energies | 40 test profiles produced 40 different #1 songs, so no single song dominates. Hip hop and r&b listeners get weaker lists (average 0.43) than lofi listeners (0.75). Energy extremes lose at most 0.06 of the energy points. |

### Adversarial profiles

I also stress-tested the scorer with profiles meant to trick it. Run them with `python src/main.py --adversarial`.

| Profile | What it probes | Result before | Fix | Result now |
|---|---|---|---|---|
| Sad Ravers (pop, sad, energy 0.9) | conflicting mood and energy; "sad" not in catalog | Happy pop returned, no hint of the conflict | "sad" added to the melancholy family; low-confidence warning when the top pick misses the mood | Dancefloor Mirage first, with a warning that it does not match the mood |
| Typo Lofi (`" Lofi "`, `"CHILL"`) | casing and whitespace | Zero genre/mood credit, jazz and blues returned | Labels are trimmed and lower-cased | Top results are lofi and chill songs (Midnight Coding, Library Rain), as with plain "lofi / chill" |
| Metalhead Sleeper (metal, peaceful, energy 0.1) | contradictory genre vs. mood and energy | Classical wins; metal fan sees no metal | Documented as a limitation (labels vs. numbers) | Moonlit Sonata first; energy now outweighs the metal label, so no metal song appears at all |
| Sad Sunshine (melancholy, valence 0.95) | label vs. numeric conflict | Sad folk song still scores 0.89 | Documented as a limitation (valence weight is about 3%) | Pine Smoke Lullaby still first at 0.90 |
| Unknown Tastes / Empty Profile | no label matches at all | Ranking by energy coincidence, scores about 0.14, no warning | Low-confidence warnings (zero coverage, weak best score) | Three warnings appear and the best score is 0.25 |
| Energy 1.5, energy -1, tempo 400 | out-of-range numbers | Accepted; energy silently stopped counting | Rejected with `ValueError` | Rejected with a clear message |

### Comparing the profiles, pair by pair

The four everyday listeners give six pairs. For each one, here is what changed in the top 5 and why that makes sense. (Song names are from the current `python -m src.main` run.)

1. **Chill Lofi vs Intense Rock: no songs in common.** Chill Lofi gets quiet, acoustic songs (Library Rain, Midnight Coding, Spacewalk Thoughts) and Intense Rock gets loud, fast ones (Storm Runner, Thunder Alley, Forged in Ash). This is what these profiles should test for: one asks for a calm 0.40 energy and acoustic sound, the other for 0.92 energy and no acoustic. They want opposite things on almost every checklist item, so they get opposite songs.
2. **Chill Lofi vs High-Energy Pop: no songs in common.** The study listener gets slow lofi, ambient and jazz and the party listener gets bright pop and dance tracks. Even a very popular pop song like Gym Hero scores only 0.05 for the study listener, because it is loud and matches neither the genre nor the mood. That low score is correct: nobody studying would want it.
3. **Chill Lofi vs Pop Happy: no songs in common.** Pop Happy only says "pop, happy, medium-high energy", and it gets upbeat songs from pop, hip hop and rock. The lofi listener's songs all have energy of 0.45 or less. Different genre, different mood and different energy all point the same way, so there is no overlap.
4. **Intense Rock vs High-Energy Pop: no songs in common, even though both want loud music.** Their energy targets are close (0.92 and 0.88). What splits them is the label and the feel: Intense Rock wants a dark, heavy sound (valence 0.45, 155 BPM) and High-Energy Pop wants a happy, danceable one (valence 0.85, 125 BPM). The one song that sits between them is Gym Hero. It is pop and very loud, so it turns up for both: it takes the fifth slot in Intense Rock's list (after the variety rule removes a third rock song) and was High-Energy Pop's fifth pick before the variety rule pushed it out.
5. **Intense Rock vs Pop Happy: no songs in common.** Pop Happy's target of 0.80 energy is lower than Rock's 0.92, and it asks for a happy mood, so it picks cheerful pop and hip hop at 0.7 to 0.9 energy. Rock picks angrier, heavier songs. This is a sensible split between a "pump me up" listener and a "keep me smiling" listener.
6. **High-Energy Pop vs Pop Happy: four of five songs in common.** They share Sunrise City, Dancefloor Mirage, Rooftop Lights and Block Party Sunday. That makes sense because they ask for the same genre and mood. Only the last slot differs: High-Energy Pop gets Neon Pulse (loud electronic dance music) and Pop Happy gets Highway Daydream (a mid-energy rock song). The extra targets in High-Energy Pop (not acoustic, 125 BPM, very happy, very danceable) all describe a loud electronic party sound, which Neon Pulse matches. Pop Happy has none of those extras, so a gentler song can slip in. The extra detail changed only the edges of the list, which is the right size of change for a small difference in the request.

**Why does "Gym Hero" keep showing up for people who just want Happy Pop?** Think of the system as a judge with a checklist, and Gym Hero as a contestant who ticks two of the three big boxes. It is a pop song (box one) and it is very lively, with energy 0.93 (box two, which is worth the most points). It misses only the third box: its mood is "intense", a workout song, not "happy". Missing one box costs it some points but does not knock it out. The mood box is worth 19 points and the energy box is worth 49 points, so a song that is the right genre and the right energy can still land in the top 5 without the right mood. With my original weights, Gym Hero was fourth for both pop listeners (scores 0.77 and 0.52). It also shows up for Intense Rock because there it ticks the mood and energy boxes and only misses the genre. In short, it is not that Gym Hero is a happy song. It is a loud song with a pop label, and my checklist cares more about loudness than about whether the song feels happy.

**What this tells me about the results.** The output is valid at the level that matters most: profiles that ask for different things get different songs, and profiles that ask for nearly the same thing get nearly the same songs. The Gym Hero case is a real flaw, not a feature, and the fix is to make the mood count for more or to take points away when the mood is clearly wrong.

### What surprised me

- **The bugs were silent.** The scorer never crashed. It returned confident-looking but meaningless rankings, such as happy pop for a listener who asked for sad music, and zero label credit because of a stray space in " Lofi ". I had expected loud failures.
- **More detail in the profile did not change the picks.** High-Energy Pop (with acoustic, tempo, valence and danceability targets) and Pop Happy (with only genre, mood and energy) get almost the same songs, with Sunrise City first for both. The extra targets mainly changed the scores: a perfect pop/happy song scores 0.81 for the sparse profile and 1.0 for the full one, so a listener who gives less information looks like a worse match.
- **Doubling the weight on energy changed little at the top.** I expected a big reshuffle, but the #1 song held for every profile and only ranks 4 and 5 moved. Small score gaps decide those ranks, and one unexpected song (an EDM track) entered Intense Rock's list.
- **The system favors some listeners.** A hip hop or r&b listener's top 5 averages 0.43 against 0.75 for a lofi listener, and a listener whose target energy sits in the sparse middle of the catalog (0.6) gets lower scores than a calm or intense one. None of this is deliberate. It follows from the catalog and my hand-written families.
- **Intuition and numbers disagreed.** The Metalhead Sleeper asks for metal but gets calm classical music first, because the energy target of 0.1 outweighs the metal label. By the numbers that is correct, but a real metal fan would be annoyed, so I needed both kinds of judgment to evaluate the results.

---

## 8. Future Work  

Ideas for how you would improve the model next.  

Prompts:  

- Additional features or preferences  
- Better ways to explain recommendations  
- Improving diversity among the top results  
- Handling more complex user tastes  

---

## 9. Personal Reflection  

A few sentences about your experience.  

Prompts:  

- What you learned about recommender systems  
- Something unexpected or interesting you discovered  
- How this changed the way you think about music recommendation apps  
