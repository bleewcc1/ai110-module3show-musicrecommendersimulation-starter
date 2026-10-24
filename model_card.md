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

**How a song earns its mark.** The judge hands out points for each thing on the checklist. (The app shows points as decimals, so 28 points appears as +0.28 and a perfect song scores close to 1.00.)

- **Genre (up to 28 points).** A song gets the full points if it is your favorite genre. If it is a close cousin, like indie pop for a pop fan, it gets half.
- **Mood (up to 22 points).** The same idea: full points for your favorite mood, half for a similar one (relaxed counts as similar to chill).
- **Energy (up to 28 points).** Here the judge asks "how close is this song to the energy you wanted?", not "is it high or low?". A song right on your target gets all the points, and the points shrink the further away it is in either direction. That way a calm listener is not handed a loud song just because loud songs have "more" energy.
- **Acoustic feel (up to 12 points).** If you like acoustic music, the more acoustic the song, the more points. If you don't, it works the other way around.
- **Speed, happiness and danceability (up to 10 points together).** Only used if you gave targets, and they work like energy: closer to your target means more points. They are small, so mostly they break ties between songs that are otherwise equal.

**One penalty.** If a song matches neither your genre nor your mood, not even as a close cousin, its total is cut in half. A song that merely happens to have the right energy should not beat a song that really fits your taste. These songs are labeled "closest fit only" so you can see they are filler.

**Picking the winners.** After every song has a mark, the judge lines them up from highest to lowest and shows the top five. If two songs tie, they are listed alphabetically so the result is the same every time. Each song comes with its list of reasons, such as "genre match, +0.28", so you can see exactly why it ranked where it did.

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

Where the system struggles or behaves unfairly. 

Prompts:  

- Features it does not consider  
- Genres or moods that are underrepresented  
- Cases where the system overfits to one preference  
- Ways the scoring might unintentionally favor some users  

---

## 7. Evaluation  

How you checked whether the recommender behaved as expected. 

Prompts:  

- Which user profiles you tested  
- What you looked for in the recommendations  
- What surprised you  
- Any simple tests or comparisons you ran  

No need for numeric metrics unless you created some.

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
