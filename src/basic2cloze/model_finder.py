from anki.hooks import addHook
from aqt import mw
from aqt.utils import tooltip, tr

from .consts import ANKI_VERSION_TUPLE

_basic_note_type_ids = []
_cloze_note_type_ids = []


def model_ids_for_names(names):
    ids = (mw.col.models.id_for_name(name) for name in names if name)
    # in an English collection the localised name resolves to the same note
    # type as the English one, so the same id routinely turns up twice
    return list(dict.fromkeys(id for id in ids if id))


def get_models():
    """Prepare note type"""
    global _basic_note_type_ids
    global _cloze_note_type_ids

    if ANKI_VERSION_TUPLE >= (2, 1, 45):
        _basic_note_type_ids = model_ids_for_names(
            ["Basic", tr.notetypes_basic_name()])
        _cloze_note_type_ids = model_ids_for_names(
            ["Cloze", tr.notetypes_cloze_name()])
    else:
        from anki.lang import _
        _basic_note_type_ids = model_ids_for_names(["Basic", _("Basic")])
        _cloze_note_type_ids = model_ids_for_names(["Cloze", _("Cloze")])

    if not _basic_note_type_ids:
        tooltip("[Automatic Basic to Cloze] Cannot find 'Basic' note type")

    if not _cloze_note_type_ids:
        tooltip("[Automatic Basic to Cloze] Cannot find 'Cloze' note type")


addHook("profileLoaded", get_models)


def get_basic_note_type_ids():
    return _basic_note_type_ids


def get_cloze_note_type_ids():
    return _cloze_note_type_ids


def get_cloze_note_type():
    """The plain Cloze note type, or None if the collection has none.

    Single source of that choice: the conversion and the editor's cloze field
    flags describe the same note type only for as long as they both come
    through here rather than each picking from the id list themselves.

    Not every conversion ends here -- a note using the hide-all syntax goes to
    "Cloze (Hide all)" instead, which target_model picks separately.
    """
    cloze_note_type_ids = get_cloze_note_type_ids()
    if not cloze_note_type_ids:
        return None

    return mw.col.models.get(cloze_note_type_ids[0])
