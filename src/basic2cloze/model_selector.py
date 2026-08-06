import re

from aqt import mw

from .model_finder import get_basic_note_type_ids, get_cloze_note_type

CLOZE_HIDE_ALL_NAME = "Cloze (Hide all)"

CLOZE_RE = r"\{\{c\d+::"
HIDE_ALL_CLOZE_RE = r"\{\{c\d+::!"


def target_model(note):
    """The note type this note should become, or None to leave it alone."""
    if note.note_type()["id"] not in get_basic_note_type_ids():
        return None

    if not any(re.search(CLOZE_RE, value) for _, value in note.items()):
        return None

    if any(re.search(HIDE_ALL_CLOZE_RE, value) for _, value in note.items()):
        hide_all_id = mw.col.models.id_for_name(CLOZE_HIDE_ALL_NAME)
        if hide_all_id:
            return mw.col.models.get(hide_all_id)
        # that note type comes from another add-on and is usually absent, so
        # fall through to the plain Cloze type rather than refusing the add

    return get_cloze_note_type()
