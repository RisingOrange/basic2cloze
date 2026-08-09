import json
import re
import traceback

from anki.hooks import wrap
from anki.models import ModelManager
from anki.notes import Note
from aqt import gui_hooks, mw
from aqt.addcards import AddCards
from aqt.editor import Editor
from aqt.utils import tooltip

from .consts import ANKI_VERSION_TUPLE
from .model_finder import (
    get_basic_note_type_ids,
    get_cloze_note_type,
    get_cloze_note_type_ids,
)
from .model_selector import target_model

try:
    from anki.notes import NoteFieldsCheckResult
except:
    pass

try:
    from aqt.editor import MODEL_CLOZE
except:
    pass

CLOZE_RE = r"\{\{c\d+::[\s\S]*?\}\}"


def contains_cloze(note: Note):
    for fld in note.fields:
        m = re.search(CLOZE_RE, fld)
        if m:
            return True
    return False


def cloze_field_flags(note_type):
    """Which of this note type's fields to present as cloze fields.

    None when we have nothing to say and Anki's own flags should stand.

    Conversion maps fields positionally, and only some of the Cloze note
    type's fields are cloze fields -- Back Extra is not -- so a cloze typed
    into Basic's Back lands somewhere it deletes nothing. Flag the ones that
    do survive conversion, rather than all of them.

    A note destined for "Cloze (Hide all)" may not match, since that target
    only becomes knowable once the note has content, and the editor asks at
    load time. The plain Cloze type is the assumption.
    """
    cloze_note_type = get_cloze_note_type()
    if not cloze_note_type:
        # Nothing to convert into, so conversion will refuse and Anki will
        # block the add. Say nothing and let the button stay disabled rather
        # than invite a cloze that cannot be added.
        return None

    cloze_ords = set(mw.col.models.cloze_fields(cloze_note_type["id"]))
    return [ord in cloze_ords for ord in range(len(note_type["flds"]))]


def main():
    def convert_basic_to_cloze(problem, note: Note):
        if not (
            note.note_type()["id"] in get_basic_note_type_ids() and contains_cloze(note)
        ):
            return problem

        if not target_model(note):
            tooltip("[Automatic Basic to Cloze] Cannot find 'Cloze' note type")
            return problem

        old_model = mw.col.models.get(note.mid)
        new_model = target_model(note)

        field_values = [
            note[old_model["flds"][i]["name"]]
            for i in range(min(len(old_model["flds"]), len(new_model["flds"])))
        ]
        tags = note.tags

        note.__init__(mw.col, new_model)
        for i, value in enumerate(field_values):
            note[new_model["flds"][i]["name"]] = value
        note.tags = tags

        return None

    gui_hooks.add_cards_will_add_note.append(convert_basic_to_cloze)

    def change_notetype_from_cloze_to_basic_in_addcards_dialog(addcards: AddCards):
        try:
            if (
                addcards.notetype_chooser.selected_notetype_id
                in get_cloze_note_type_ids()
            ):
                addcards.notetype_chooser.selected_notetype_id = (
                    get_basic_note_type_ids()[0]
                )
                addcards.notetype_chooser.show()
        except Exception as e:
            print(e)
            pass  # don't cause an error when note types are missing or this code becomes outdated

    gui_hooks.add_cards_did_init.append(
        change_notetype_from_cloze_to_basic_in_addcards_dialog
    )

    # adding the cloze buttons also enables the shortcut!
    # in older version the button and the shortcut exist by default
    def maybe_show_cloze_button(editor: Editor):
        if editor.note.note_type()["id"] not in get_basic_note_type_ids():
            return

        if ANKI_VERSION_TUPLE >= (2, 1, 52):
            editor.web.eval(
                """
                require("anki/ui").loaded.then(() =>
                    require("anki/NoteEditor").instances[0].toolbar.toolbar.show("cloze")
                )
                """
            )
        elif ANKI_VERSION_TUPLE >= (2, 1, 50):
            editor.web.eval(
                """
                require("anki/ui").loaded.then(() =>
                    require("anki/NoteEditor").instances[0].toolbar.templateButtons.show("cloze")
                )
                """
            )
        elif ANKI_VERSION_TUPLE >= (2, 1, 45):
            editor.web.eval(
                '$editorToolbar.then(({ templateButtons }) => templateButtons.showButton("cloze")); '
            )

    gui_hooks.editor_did_load_note.append(maybe_show_cloze_button)

    # Anki >= 25.9 additionally greys the cloze button out unless the focused
    # field is one of the note type's cloze fields. Basic has none, so the
    # button shown above would never become usable. Anki sets the per-field
    # flags from the JS that loadNote runs, so set ours there.
    def flag_cloze_fields_for_basic(js: str, note: Note, editor) -> str:
        try:
            note_type = note.note_type()
            if note_type["id"] not in get_basic_note_type_ids():
                return js

            field_flags = cloze_field_flags(note_type)
            if field_flags is None:
                return js

            flags = json.dumps(field_flags)
            # guarded so that losing the global degrades to Anki's own flags,
            # rather than rejecting the promise this JS runs in and costing us
            # editor_did_load_note and the duplicate display update with it
            return (
                f"{js} if (typeof setClozeFields === 'function')"
                f" {{ setClozeFields({flags}); }}"
            )
        except Exception:
            # this hook drops a callback permanently if it raises
            traceback.print_exc()
            return js

    # cloze_fields arrived with the per-field gating, so it stands in for it.
    # The hook itself long predates that, but check rather than risk an
    # AttributeError taking the whole add-on down at import.
    if hasattr(ModelManager, "cloze_fields") and hasattr(
        gui_hooks, "editor_will_load_note"
    ):
        gui_hooks.editor_will_load_note.append(flag_cloze_fields_for_basic)

    # hide cloze warnings
    if ANKI_VERSION_TUPLE >= (2, 1, 45):
        original_update_duplicate_display = Editor._update_duplicate_display

        def _update_duplicate_display_ignore_cloze_problems_for_basic_notes(
            self, result
        ) -> None:
            if self.note.note_type()["id"] in get_basic_note_type_ids():
                if (
                    result == NoteFieldsCheckResult.NOTETYPE_NOT_CLOZE
                    or result == NoteFieldsCheckResult.FIELD_NOT_CLOZE
                ):
                    result = NoteFieldsCheckResult.NORMAL
            original_update_duplicate_display(self, result)

        Editor._update_duplicate_display = (
            _update_duplicate_display_ignore_cloze_problems_for_basic_notes
        )
    elif ANKI_VERSION_TUPLE >= (2, 1, 40):

        def _onClozeNew(self, *, _old):
            basicNoteTypes = get_basic_note_type_ids()
            model_id = self.note.model()["id"]
            if model_id in basicNoteTypes and self.addMode:
                model_type_backup = self.note.model()["type"]
                self.note.model()["type"] = MODEL_CLOZE

            result = _old(self)

            if model_id in basicNoteTypes and self.addMode:
                self.note.model()["type"] = model_type_backup

            return result

        Editor._onCloze = wrap(Editor._onCloze, _onClozeNew, "around")
    else:

        def _onClozeNew(self, *, _old):
            model_id = self.note.model()["id"]
            if model_id in get_basic_note_type_ids() and self.addMode:
                hook_re_search()
                result = _old(self)
                unhook_re_search()
            else:
                result = _old(self)
            return result

        _oldReSearch = None
        _clozeCheckerRegex = "{{(.*:)*cloze:"

        def hook_re_search():
            global _oldReSearch

            # Hook this template
            # if not re.search("{{(.*:)*cloze:", self.note.model()["tmpls"][0]["qfmt"]):
            def newSearch(pattern, string, flags=0, *, _old):
                if pattern == _clozeCheckerRegex:
                    return True
                return _old(pattern, string, flags)

            _oldReSearch = re.search
            re.search = wrap(re.search, newSearch, "around")

        def unhook_re_search():
            global _oldReSearch
            if _oldReSearch:
                re.search = _oldReSearch
                _oldReSearch = None

        Editor._onCloze = wrap(Editor._onCloze, _onClozeNew, "around")
