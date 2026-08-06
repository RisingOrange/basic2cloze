"""Covers the JS that enable_cloze_in_all_fields_for_basic appends."""

import pytest

from conftest import BASIC_ID, CLOZE_ID, FakeNote

UNRELATED_ID = 3333


@pytest.fixture
def widen_cloze_fields(load_addon):
    hook = load_addon(cloze_fields_exists=True).editor_will_load_note
    assert len(hook.callbacks) == 1
    return hook.callbacks[0]


def test_basic_note_gets_every_field_flagged(widen_cloze_fields):
    js = widen_cloze_fields("setFields(x);", FakeNote(BASIC_ID, 2), None)

    assert js == "setFields(x); setClozeFields([true, true]); triggerChanges();"


def test_flag_count_follows_the_field_count(widen_cloze_fields):
    js = widen_cloze_fields("js;", FakeNote(BASIC_ID, 5), None)

    assert "setClozeFields([true, true, true, true, true]);" in js


def test_cloze_note_is_left_alone(widen_cloze_fields):
    """Anki already flags these correctly."""
    assert widen_cloze_fields("js;", FakeNote(CLOZE_ID, 2), None) == "js;"


def test_unrelated_note_type_is_left_alone(widen_cloze_fields):
    assert widen_cloze_fields("js;", FakeNote(UNRELATED_ID, 2), None) == "js;"


def test_a_raising_note_does_not_take_the_hook_down_with_it(widen_cloze_fields):
    """Anki unregisters a filter callback permanently if it raises, so ours
    has to swallow and pass the JS through untouched."""

    class ExplodingNote:
        def note_type(self):
            raise RuntimeError("notetype went away")

    assert widen_cloze_fields("js;", ExplodingNote(), None) == "js;"


def test_hook_is_not_registered_on_anki_without_cloze_fields(load_addon):
    """Before Anki 25.9 there were no per-field cloze flags to widen."""
    gui_hooks = load_addon(cloze_fields_exists=False)

    assert gui_hooks.editor_will_load_note.callbacks == []
