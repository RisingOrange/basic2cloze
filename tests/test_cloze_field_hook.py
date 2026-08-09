"""Covers the JS that flag_cloze_fields_for_basic appends."""

import pytest

from conftest import BASIC_ID, CLOZE_ID, FakeNote

UNRELATED_ID = 3333


@pytest.fixture
def flag_cloze_fields(load_addon):
    def make(**kwargs):
        hook = load_addon(cloze_fields_exists=True, **kwargs).editor_will_load_note
        assert len(hook.callbacks) == 1
        return hook.callbacks[0]

    return make


@pytest.fixture
def widen_cloze_fields(flag_cloze_fields):
    return flag_cloze_fields()


def test_only_fields_that_survive_conversion_are_flagged(widen_cloze_fields):
    """Basic's Back maps onto Cloze's Back Extra, which is not a cloze field,
    so offering the button there would invite a cloze that deletes nothing."""
    js = widen_cloze_fields("setFields(x);", FakeNote(BASIC_ID, 2), None)

    assert js == (
        "setFields(x); if (typeof setClozeFields === 'function')"
        " { setClozeFields([true, false]); }"
    )


def test_flags_follow_a_customised_cloze_note_type(flag_cloze_fields):
    """If the user made Back Extra a cloze field too, Back should follow."""
    hook = flag_cloze_fields(cloze_ords=(0, 1))

    js = hook("js;", FakeNote(BASIC_ID, 2), None)

    assert "setClozeFields([true, true]);" in js


def test_every_field_is_flagged_without_a_cloze_note_type(flag_cloze_fields):
    """Nothing to convert into, so don't disable what the add-on just enabled."""
    hook = flag_cloze_fields(has_cloze_note_type=False)

    js = hook("js;", FakeNote(BASIC_ID, 2), None)

    assert "setClozeFields([true, true]);" in js


def test_flag_count_follows_the_field_count(widen_cloze_fields):
    """One flag per field, whatever the Basic note type has been edited into."""
    js = widen_cloze_fields("js;", FakeNote(BASIC_ID, 5), None)

    assert "setClozeFields([true, false, false, false, false]);" in js


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


def test_the_appended_js_degrades_if_the_global_disappears(widen_cloze_fields):
    """A bare call would reject the promise Anki runs this JS in."""
    js = widen_cloze_fields("js;", FakeNote(BASIC_ID, 1), None)

    assert "typeof setClozeFields === 'function'" in js


def test_hook_is_not_registered_on_anki_without_cloze_fields(load_addon):
    """Before Anki 25.9 there were no per-field cloze flags to widen."""
    gui_hooks = load_addon(cloze_fields_exists=False)

    assert gui_hooks.editor_will_load_note.callbacks == []


def test_addon_still_loads_if_anki_drops_the_hook(load_addon):
    """Registering blind would AttributeError and take the add-on with it."""
    gui_hooks = load_addon(cloze_fields_exists=True, hook_exists=False)

    assert not hasattr(gui_hooks, "editor_will_load_note")
    # the rest of the add-on still came up
    assert gui_hooks.add_cards_will_add_note.callbacks
