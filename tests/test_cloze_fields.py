"""Covers the ModelManager.cloze_fields wrapper that enables the cloze button.

Anki >= 25.9 asks which of a note type's fields are cloze fields and greys the
editor's cloze button out on the rest. Basic has none, so the add-on answers
for Basic with the ordinals its fields land on once converted.
"""

import pytest

from conftest import BASIC, BASIC_ID, CLOZE, CLOZE_HIDE_ALL, CLOZE_ID, HIDE_ALL_ID

UNRELATED_ID = 9999  # distinct from every id conftest hands out


@pytest.fixture
def cloze_fields(load_addon):
    """The wrapped ModelManager.cloze_fields, bound to a stub instance."""

    def make(**kwargs):
        addon = load_addon(cloze_fields_exists=True, **kwargs)
        return addon.model_manager().cloze_fields

    return make


def test_basic_answers_with_the_cloze_note_types_ordinals(cloze_fields):
    """Basic's Front maps onto Cloze's Text, which is a cloze field; its Back
    maps onto Back Extra, which is not."""
    assert cloze_fields()(BASIC_ID) == [0]


def test_a_customised_cloze_note_type_is_followed(cloze_fields):
    """If Back Extra was made a cloze field too, Back should follow."""
    assert cloze_fields(cloze_ords=(0, 1))(BASIC_ID) == [0, 1]


def test_the_cloze_note_type_itself_is_untouched(cloze_fields):
    assert cloze_fields()(CLOZE_ID) == [0]


def test_an_unrelated_note_type_is_untouched(cloze_fields):
    answer = cloze_fields(notetypes=(BASIC, CLOZE, CLOZE_HIDE_ALL))
    assert answer(HIDE_ALL_ID) == []


def test_basic_is_untouched_without_a_cloze_note_type(cloze_fields):
    """Conversion would refuse and Anki would block the add, so an enabled
    cloze button could only lead to a note that cannot be added."""
    assert cloze_fields(notetypes=(BASIC,))(BASIC_ID) == []


def test_a_deleted_cloze_note_type_does_not_reach_the_backend(cloze_fields):
    """The ids are cached at profile load, so they outlive the note type, and
    asking the backend about a missing one panics past `except Exception`."""
    assert cloze_fields(deleted_note_type_ids=(CLOZE_ID,))(BASIC_ID) == []


def test_not_wrapped_on_anki_without_cloze_fields(load_addon):
    """Before 25.9 there was no per-field gating to correct."""
    addon = load_addon(cloze_fields_exists=False)

    assert not hasattr(addon.model_manager, "cloze_fields")


def test_the_rest_of_the_addon_still_loads(load_addon):
    addon = load_addon(cloze_fields_exists=False)

    assert addon.gui_hooks.add_cards_will_add_note.callbacks
    assert addon.gui_hooks.editor_did_load_note.callbacks
