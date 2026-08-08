from app.pipeline.variant_profiles import SHORTS_VARIANT_PROFILES


def test_exactly_ten_distinct_profiles():
    names = [name for name, _ in SHORTS_VARIANT_PROFILES]
    assert len(SHORTS_VARIANT_PROFILES) == 10
    assert len(set(names)) == 10  # no duplicate names


def test_every_profile_is_shorts_with_cuts_and_captions_on():
    for _name, toggles in SHORTS_VARIANT_PROFILES:
        assert toggles["long_form"] is False
        assert toggles["cut_silence"] is True
        assert toggles["captions"] is True


def test_five_distinct_music_takes_across_both_framing_styles():
    moods = {toggles.get("music_mood") for _name, toggles in SHORTS_VARIANT_PROFILES}
    assert moods == {None, "calm", "playful", "funny", "exciting"}

    face_crop_values = {toggles["face_crop"] for _name, toggles in SHORTS_VARIANT_PROFILES}
    assert face_crop_values == {True, False}


def test_music_off_profiles_have_no_mood_set():
    for _name, toggles in SHORTS_VARIANT_PROFILES:
        if toggles["music"] is False:
            assert toggles["music_mood"] is None
