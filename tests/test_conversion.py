"""Covers the conversion itself: a Basic note with clozes becoming a Cloze note.

This is what the add-on is for, and it runs as an `add_cards_will_add_note`
filter: returning None clears Anki's objection to clozes in a non-cloze note
type and lets the add proceed, while returning the problem blocks it.
"""

import pytest

from conftest import BASIC, CLOZE, CLOZE_HIDE_ALL, CLOZE_ID, HIDE_ALL_ID, basic_note

NOT_CLOZE_PROBLEM = "you have a cloze deletion outside a cloze note type"


@pytest.fixture
def convert(load_addon):
    """The registered filter, plus the fake collection it runs against."""

    def make(notetypes=(BASIC, CLOZE)):
        addon = load_addon(cloze_fields_exists=True, notetypes=notetypes)
        hook = addon.gui_hooks.add_cards_will_add_note
        assert len(hook.callbacks) == 1
        return hook.callbacks[0], addon

    return make


def test_basic_note_with_a_cloze_becomes_a_cloze_note(convert):
    convert_basic_to_cloze, _ = convert()
    note = basic_note("Canberra is the capital of {{c1::Australia}}", "extra")

    problem = convert_basic_to_cloze(NOT_CLOZE_PROBLEM, note)

    assert problem is None, "Anki's objection should have been cleared"
    assert note.note_type()["id"] == CLOZE_ID
    assert note["Text"] == "Canberra is the capital of {{c1::Australia}}"
    assert note["Back Extra"] == "extra"


def test_tags_survive_the_conversion(convert):
    convert_basic_to_cloze, _ = convert()
    note = basic_note("{{c1::tagged}}")
    note.tags = ["geography", "marked"]

    convert_basic_to_cloze(None, note)

    assert note.note_type()["id"] == CLOZE_ID, "otherwise nothing was converted"
    assert note.tags == ["geography", "marked"]


def test_basic_note_without_a_cloze_is_left_alone(convert):
    convert_basic_to_cloze, _ = convert()
    note = basic_note("plain front", "plain back")

    problem = convert_basic_to_cloze(NOT_CLOZE_PROBLEM, note)

    assert problem == NOT_CLOZE_PROBLEM, "nothing to convert, so don't interfere"
    assert note.note_type()["id"] == BASIC["id"]


def test_hide_all_syntax_uses_the_hide_all_note_type(convert):
    """`{{c1::!...}}` is the marker for the "Cloze (Hide all)" note type."""
    convert_basic_to_cloze, _ = convert(notetypes=(BASIC, CLOZE, CLOZE_HIDE_ALL))
    note = basic_note("{{c1::!hidden}}", "extra")

    problem = convert_basic_to_cloze(NOT_CLOZE_PROBLEM, note)

    assert problem is None
    assert note.note_type()["id"] == HIDE_ALL_ID
    assert note["Text"] == "{{c1::!hidden}}"
    assert note["Back Extra"] == "extra"


def test_hide_all_syntax_falls_back_when_that_note_type_is_missing(convert):
    """Most collections have no "Cloze (Hide all)"; adding must still work.

    This is the regression that used to raise TypeError out of the filter hook,
    which Anki responds to by unregistering the callback -- so the first note
    with this syntax also killed conversion for the rest of the session.
    """
    convert_basic_to_cloze, _ = convert(notetypes=(BASIC, CLOZE))
    note = basic_note("{{c1::!hidden}}", "extra")

    problem = convert_basic_to_cloze(NOT_CLOZE_PROBLEM, note)

    assert problem is None
    assert note.note_type()["id"] == CLOZE_ID
    assert note["Text"] == "{{c1::!hidden}}"


def test_no_cloze_note_type_at_all_blocks_the_add_with_a_tooltip(convert):
    convert_basic_to_cloze, addon = convert(notetypes=(BASIC,))
    note = basic_note("{{c1::orphaned}}")
    # model_finder warns about the missing note type at profile load too, so
    # only tooltips from the conversion itself should count here
    addon.tooltips.clear()

    problem = convert_basic_to_cloze(NOT_CLOZE_PROBLEM, note)

    assert problem == NOT_CLOZE_PROBLEM, "no target note type, so don't clear it"
    assert note.note_type()["id"] == BASIC["id"]
    assert any("Cloze" in text for text in addon.tooltips)


def test_hide_all_is_reachable_without_a_plain_cloze_note_type(convert):
    """The hide-all branch returns before the plain Cloze lookup, so a
    collection with only that note type still converts."""
    convert_basic_to_cloze, _ = convert(notetypes=(BASIC, CLOZE_HIDE_ALL))
    note = basic_note("{{c1::!hidden}}")

    problem = convert_basic_to_cloze(NOT_CLOZE_PROBLEM, note)

    assert problem is None
    assert note.note_type()["id"] == HIDE_ALL_ID


def test_surplus_target_fields_are_left_blank(convert):
    three_field_cloze = {
        "id": CLOZE_ID,
        "name": "Cloze",
        "flds": [{"name": "Text"}, {"name": "Back Extra"}, {"name": "Notes"}],
    }
    convert_basic_to_cloze, _ = convert(notetypes=(BASIC, three_field_cloze))
    note = basic_note("{{c1::kept}}", "extra")

    problem = convert_basic_to_cloze(NOT_CLOZE_PROBLEM, note)

    assert problem is None
    assert note.fields == ["{{c1::kept}}", "extra", ""]


def test_overlapping_fields_are_kept_when_the_target_has_fewer_fields(convert):
    """The surplus field is silently dropped -- pre-existing, documented here.

    Basic and Cloze both have two fields today, so nothing hits this in a
    stock collection, but neither note type is guaranteed to stay that way.
    """
    one_field_cloze = {"id": CLOZE_ID, "name": "Cloze", "flds": [{"name": "Text"}]}
    convert_basic_to_cloze, _ = convert(notetypes=(BASIC, one_field_cloze))
    note = basic_note("{{c1::kept}}", "dropped")

    problem = convert_basic_to_cloze(NOT_CLOZE_PROBLEM, note)

    assert problem is None
    assert note.fields == ["{{c1::kept}}"], "'dropped' has nowhere to go"
