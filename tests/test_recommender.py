from src.recommender import Song, UserProfile, Recommender

def make_small_recommender() -> Recommender:
    songs = [
        Song(
            id=1,
            title="Test Pop Track",
            artist="Test Artist",
            genre="pop",
            mood="happy",
            energy=0.8,
            tempo_bpm=120,
            valence=0.9,
            danceability=0.8,
            acousticness=0.2,
        ),
        Song(
            id=2,
            title="Chill Lofi Loop",
            artist="Test Artist",
            genre="lofi",
            mood="chill",
            energy=0.4,
            tempo_bpm=80,
            valence=0.6,
            danceability=0.5,
            acousticness=0.9,
        ),
    ]
    return Recommender(songs)


def test_recommend_returns_songs_sorted_by_score():
    user = UserProfile(
        favorite_genre="pop",
        favorite_mood="happy",
        target_energy=0.8,
        likes_acoustic=False,
    )
    rec = make_small_recommender()
    results = rec.recommend(user, k=2)

    assert len(results) == 2
    # Starter expectation: the pop, happy, high energy song should score higher
    assert results[0].genre == "pop"
    assert results[0].mood == "happy"


def test_explain_recommendation_returns_non_empty_string():
    user = UserProfile(
        favorite_genre="pop",
        favorite_mood="happy",
        target_energy=0.8,
        likes_acoustic=False,
    )
    rec = make_small_recommender()
    song = rec.songs[0]

    explanation = rec.explain_recommendation(user, song)
    assert isinstance(explanation, str)
    assert explanation.strip() != ""


# Recommender with optional tempo / valence / danceability targets ------------

def make_tempo_recommender():
    def song(id, title, tempo):
        return Song(id=id, title=title, artist="A", genre="pop", mood="happy", energy=0.8,
                    tempo_bpm=tempo, valence=0.7, danceability=0.7, acousticness=0.2)
    return Recommender([song(1, "Slow", 70.0), song(2, "Fast", 160.0)])


def test_recommender_uses_target_tempo():
    rec = make_tempo_recommender()
    fast_fan = UserProfile("pop", "happy", 0.8, False, target_tempo=160.0)
    slow_fan = UserProfile("pop", "happy", 0.8, False, target_tempo=70.0)
    assert rec.recommend(fast_fan, k=1)[0].title == "Fast"
    assert rec.recommend(slow_fan, k=1)[0].title == "Slow"


def test_recommender_respects_k():
    rec = make_tempo_recommender()
    user = UserProfile("pop", "happy", 0.8, False)
    assert len(rec.recommend(user, k=1)) == 1
    assert len(rec.recommend(user, k=5)) == 2


def test_explanation_mentions_optional_targets_only_when_set():
    rec = make_tempo_recommender()
    song = rec.songs[0]
    with_target = rec.explain_recommendation(
        UserProfile("pop", "happy", 0.8, False, target_tempo=70.0, target_valence=0.7), song)
    without = rec.explain_recommendation(UserProfile("pop", "happy", 0.8, False), song)
    assert "tempo" in with_target and "valence" in with_target
    assert "tempo" not in without and "valence" not in without
