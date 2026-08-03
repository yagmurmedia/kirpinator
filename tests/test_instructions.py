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
