from app.models import VideoToggles
from app.pipeline.instructions import apply_instructions


def test_music_off_phrase_disables_music():
    toggles = VideoToggles()
    apply_instructions(toggles, "Bu videoya müzik ekleme lütfen")
    assert toggles.music is False


def test_effects_off_phrase_disables_effects():
    toggles = VideoToggles()
    apply_instructions(toggles, "efektsiz olsun, sade kalsin")
    assert toggles.effects is False


def test_unrecognized_text_leaves_toggles_untouched():
    toggles = VideoToggles()
    apply_instructions(toggles, "bugün hava çok güzeldi parkta oynadık")
    assert toggles == VideoToggles()


def test_made_for_kids_override():
    toggles = VideoToggles()
    apply_instructions(toggles, "made for kids kapalı olsun")
    assert toggles.made_for_kids is False


def test_long_form_phrase_enables_long_form():
    toggles = VideoToggles()
    apply_instructions(toggles, "bu video uzun youtube videosu olsun, shorts olmayacak")
    assert toggles.long_form is True


def test_shorts_phrase_keeps_long_form_off():
    toggles = VideoToggles()
    apply_instructions(toggles, "shorts olsun bu video")
    assert toggles.long_form is False


def test_matches_without_turkish_diacritics():
    # Real failure: a user typed "muzik olmasin" (no ü/ı) on a phone keyboard
    # and it silently failed to match "müzik olmasın" before normalization.
    toggles = VideoToggles()
    apply_instructions(toggles, "barbie videosunu efektli hazirla, muzik olmasin")
    assert toggles.music is False
    assert toggles.effects is True
