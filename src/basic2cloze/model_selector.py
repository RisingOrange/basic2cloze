import re

from aqt import mw

from .model_finder import get_basic_note_type_ids, get_cloze_note_type

CLOZE_HIDE_ALL_NAME = "Cloze (Hide all)"

# named for the opening delimiter, not a whole cloze: basic2cloze.CLOZE_RE is a
# different pattern that also requires the closing braces
CLOZE_START_RE = r"\{\{c\d+::"
# in the cloze-hide-all add-on a leading "!" marks a cloze that stays exposed
EXPOSED_CLOZE_START_RE = CLOZE_START_RE + "!"


def target_model(note):
    """The note type this note should become, or None to leave it alone."""
    if note.note_type()["id"] not in get_basic_note_type_ids():
        return None

    if not any(re.search(CLOZE_START_RE, value) for _, value in note.items()):
        return None

    if any(re.search(EXPOSED_CLOZE_START_RE, value) for _, value in note.items()):
        hide_all_id = mw.col.models.id_for_name(CLOZE_HIDE_ALL_NAME)
        if hide_all_id:
            return mw.col.models.get(hide_all_id)
        # Fall through to the plain Cloze type rather than refuse the add. That
        # note type belongs to the cloze-hide-all add-on, which now calls it
        # legacy and applies hide-all to regular Cloze notes instead -- so its
        # absence often means the plain type is the correct target. Don't strip
        # the "!" either: it is only a marker to that add-on, and is ordinary
        # answer text in clozes like {{c1::!=}}.

    return get_cloze_note_type()
