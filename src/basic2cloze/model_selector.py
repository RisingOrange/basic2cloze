import re

from aqt import mw

from .model_finder import get_basic_note_type_ids, get_cloze_note_type

# Looked up by exact name, and trgkanki/cloze_hide_all registers it as "Hide
# all" (src/model/consts.py) while spelling it "Hide All" in its README.
CLOZE_HIDE_ALL_NAME = "Cloze (Hide all)"

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
        # Fall through to plain Cloze rather than refuse the add. Hide-all is
        # lost (that add-on now marks notes, not note types), leaving "!" as
        # literal text -- but it must not be stripped: "!" is ordinary content
        # in answers like {{c1::!=}}.

    return get_cloze_note_type()
