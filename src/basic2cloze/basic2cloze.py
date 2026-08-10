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


def main():
    def convert_basic_to_cloze(problem, note: Note):
        if not (
            note.note_type()["id"] in get_basic_note_type_ids() and contains_cloze(note)
        ):
            return problem

        new_model = target_model(note)
        if not new_model:
            tooltip("[Automatic Basic to Cloze] Cannot find 'Cloze' note type")
            return problem

        old_model = mw.col.models.get(note.mid)

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
    # from 25.9 this only makes them visible -- see the per-field flags below
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
    # field is one of the note type's cloze fields, and Basic has none, so the
    # button shown above would never become usable. Answer for Basic with the
    # ordinals its fields land on once converted: fields map positionally onto
    # the Cloze note type, and only some of those are cloze fields -- Back
    # Extra is not -- so a cloze typed into Basic's Back deletes nothing.
    #
    # Anki feeds this to the editor itself. Appending our own setClozeFields()
    # to the JS that loadNote runs would be narrower, but it has to run after
    # Anki's own call, and an add-on that defers that batch wins instead:
    # AnKing Note Types wraps it in EditorIO.clearOcclusionMode().then(...),
    # which leaves Anki's call to overwrite ours.
    if hasattr(ModelManager, "cloze_fields"):
        original_cloze_fields = ModelManager.cloze_fields

        def cloze_fields_for_basic_too(self, notetype_id):
            try:
                # Only answer for the collection whose note type ids we cached
                # and whose Cloze id get() confirms below. This is a class-wide
                # patch, so another add-on can call it holding a different
                # collection, and handing that one an id validated against ours
                # is the uncatchable backend panic the check exists to avoid.
                collection = mw.col
                if collection is None or self is not collection.models:
                    return original_cloze_fields(self, notetype_id)

                if notetype_id in get_basic_note_type_ids():
                    # Nothing to convert into means conversion will refuse and
                    # Anki will block the add, so leave the button disabled
                    # rather than invite a cloze that cannot be added.
                    cloze_note_type = get_cloze_note_type()
                    if cloze_note_type:
                        # get() confirmed the id, so this cannot hit the
                        # missing-note-type panic in the Rust backend
                        return original_cloze_fields(self, cloze_note_type["id"])
            except Exception:
                traceback.print_exc()

            return original_cloze_fields(self, notetype_id)

        ModelManager.cloze_fields = cloze_fields_for_basic_too

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
