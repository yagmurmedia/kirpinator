from app.pipeline.variant_profiles import LONG_FORM_VARIANT_PROFILES, SHORTS_VARIANT_PROFILES


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


def test_exactly_three_distinct_long_form_profiles():
    names = [name for name, _ in LONG_FORM_VARIANT_PROFILES]
    assert len(LONG_FORM_VARIANT_PROFILES) == 3
    assert len(set(names)) == 3


def test_every_long_form_profile_is_actually_long_form_and_labeled_as_such():
    for name, toggles in LONG_FORM_VARIANT_PROFILES:
        assert toggles["long_form"] is True
        assert toggles["cut_silence"] is True
        assert toggles["captions"] is True
        # Distinguishable from Shorts versions in the same version list.
        assert name.startswith("uzun video")
