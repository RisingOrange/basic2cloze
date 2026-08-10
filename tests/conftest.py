"""Lets the add-on be imported without Anki, by standing in for what it imports.

These stubs only prove our own code does what we meant; they cannot notice Anki
changing underneath us. test_anki_api_contract.py is what covers that.
"""

import sys
import types
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"

BASIC_ID = 1111
CLOZE_ID = 2222
HIDE_ALL_ID = 3333

BASIC = {"id": BASIC_ID, "name": "Basic", "flds": [{"name": "Front"}, {"name": "Back"}]}
CLOZE = {
    "id": CLOZE_ID,
    "name": "Cloze",
    "flds": [{"name": "Text"}, {"name": "Back Extra"}],
}
CLOZE_HIDE_ALL = {
    "id": HIDE_ALL_ID,
    "name": "Cloze (Hide all)",
    "flds": [{"name": "Text"}, {"name": "Back Extra"}],
}


class FakeModels:
    """The handful of ModelManager methods the add-on reaches for."""

    def __init__(self, notetypes, cloze_ords=(0,), deleted_ids=()):
        self.notetypes = {notetype["id"]: notetype for notetype in notetypes}
        self.cloze_ords = cloze_ords
        # ids model_finder cached at profile load, before the note type went
        self.deleted_ids = set(deleted_ids)

    def get(self, notetype_id):
        if notetype_id in self.deleted_ids:
            return None
        return self.notetypes.get(notetype_id)

    def id_for_name(self, name):
        for notetype in self.notetypes.values():
            if notetype["name"] == name:
                return notetype["id"]
        return None

    def cloze_fields(self, notetype_id):
        if self.get(notetype_id) is None:
            # the real backend panics on an unknown id, and a panic is a
            # BaseException, so the add-on's except Exception won't save it
            raise BaseException(f"panic: no note type {notetype_id}")
        # only the Cloze note type has cloze fields, so asking about the
        # wrong one has to come back empty rather than quietly succeed
        return list(self.cloze_ords) if notetype_id == CLOZE_ID else []


class EditableNote:
    """Enough of anki.notes.Note for the conversion to be exercised.

    The signature matters: convert_basic_to_cloze re-inits the note in place as
    `note.__init__(col, new_model)`, which in Anki yields a blank note of that
    note type -- hence the reset here.
    """

    def __init__(self, col, notetype, id=None):
        self._notetype = notetype
        self.fields = [""] * len(notetype["flds"])
        self.tags = []

    @property
    def mid(self):
        return self._notetype["id"]

    def note_type(self):
        return self._notetype

    def keys(self):
        return [field["name"] for field in self._notetype["flds"]]

    def items(self):
        return list(zip(self.keys(), self.fields))

    def __getitem__(self, name):
        return self.fields[self.keys().index(name)]

    def __setitem__(self, name, value):
        self.fields[self.keys().index(name)] = value


def basic_note(*field_values):
    note = EditableNote(None, BASIC)
    for index, value in enumerate(field_values):
        note.fields[index] = value
    return note


class FilterHook:
    """Stands in for an Anki hook, keeping the callbacks so tests can call them."""

    def __init__(self):
        self.callbacks = []

    def append(self, callback):
        self.callbacks.append(callback)


class FakeNote:
    def __init__(self, notetype_id, field_count):
        self.notetype_id = notetype_id
        self.field_count = field_count

    def note_type(self):
        return {
            "id": self.notetype_id,
            "flds": [{"name": f"field{i}"} for i in range(self.field_count)],
        }


@pytest.fixture
def load_addon(monkeypatch):
    """Import the add-on against stubbed Anki modules.

    `basic2cloze.__init__` calls main() on import, so importing is what
    registers the hooks. Returns the stubbed gui_hooks, the fake ModelManager,
    and the list any tooltip() text lands in.
    """

    def load(
        *,
        cloze_fields_exists: bool,
        hook_exists: bool = True,
        notetypes=(BASIC, CLOZE),
        # stock Cloze: Text is a cloze field, Back Extra is not
        cloze_ords: tuple = (0,),
        # ids the cache still knows but the collection no longer has, i.e.
        # note types deleted after profile load
        deleted_note_type_ids: tuple = (),
    ):
        profile_hooks = []
        tooltips = []

        anki = types.ModuleType("anki")
        anki.version = "26.8.1"

        anki_hooks = types.ModuleType("anki.hooks")
        anki_hooks.wrap = lambda old, new, position: old
        anki_hooks.addHook = lambda name, cb: profile_hooks.append((name, cb))

        anki_notes = types.ModuleType("anki.notes")
        anki_notes.Note = EditableNote
        anki_notes.NoteFieldsCheckResult = types.SimpleNamespace(
            NORMAL=0, NOTETYPE_NOT_CLOZE=1, FIELD_NOT_CLOZE=2
        )

        # mw.col.models has to be an instance of the very class the add-on
        # patches, as it is in Anki: the wrapper compares the two to tell the
        # current collection's manager from any other one
        members = {
            "__init__": FakeModels.__init__,
            "get": FakeModels.get,
            "id_for_name": FakeModels.id_for_name,
        }
        if cloze_fields_exists:
            members["cloze_fields"] = FakeModels.cloze_fields
        ModelManager = type("ModelManager", (), members)

        models = ModelManager(notetypes, cloze_ords, deleted_note_type_ids)
        mw = types.SimpleNamespace(col=types.SimpleNamespace(models=models))

        anki_models = types.ModuleType("anki.models")
        anki_models.ModelManager = ModelManager

        gui_hooks = types.SimpleNamespace(
            add_cards_will_add_note=FilterHook(),
            add_cards_did_init=FilterHook(),
            editor_did_load_note=FilterHook(),
            profile_did_open=FilterHook(),
        )
        if hook_exists:
            gui_hooks.editor_will_load_note = FilterHook()

        aqt = types.ModuleType("aqt")
        aqt.gui_hooks = gui_hooks
        aqt.mw = mw

        aqt_addcards = types.ModuleType("aqt.addcards")
        aqt_addcards.AddCards = type("AddCards", (), {})

        aqt_editor = types.ModuleType("aqt.editor")
        aqt_editor.Editor = type(
            "Editor",
            (),
            {
                "_update_duplicate_display": lambda self, result: None,
                "_onCloze": lambda self: None,
            },
        )
        aqt_editor.MODEL_CLOZE = 1

        aqt_utils = types.ModuleType("aqt.utils")
        aqt_utils.tooltip = lambda text, *args, **kwargs: tooltips.append(text)
        aqt_utils.tr = types.SimpleNamespace(
            notetypes_basic_name=lambda: "Basic",
            notetypes_cloze_name=lambda: "Cloze",
        )

        stubs = {
            "anki": anki,
            "anki.hooks": anki_hooks,
            "anki.notes": anki_notes,
            "anki.models": anki_models,
            "aqt": aqt,
            "aqt.addcards": aqt_addcards,
            "aqt.editor": aqt_editor,
            "aqt.utils": aqt_utils,
        }

        # monkeypatch restores sys.modules afterwards, so the real anki stays
        # importable for the contract tests however these run interleaved
        for name in list(sys.modules):
            if name.split(".")[0] in ("anki", "aqt", "basic2cloze"):
                monkeypatch.delitem(sys.modules, name)
        for name, module in stubs.items():
            monkeypatch.setitem(sys.modules, name, module)
        monkeypatch.syspath_prepend(str(SRC))

        import basic2cloze  # noqa: F401  -- importing registers the hooks

        # Plain del, not monkeypatch: this import has to be forgotten for good,
        # or a later test gets a basic2cloze still bound to these stubs. The
        # hooks registered above keep working, they hold the functions directly.
        for name in list(sys.modules):
            if name.split(".")[0] == "basic2cloze":
                del sys.modules[name]

        for name, callback in profile_hooks:
            if name == "profileLoaded":
                callback()  # populates model_finder's cached notetype ids

        return types.SimpleNamespace(
            gui_hooks=gui_hooks,
            models=models,
            tooltips=tooltips,
            # the add-on wraps cloze_fields on the class, so tests need the
            # class the add-on actually saw
            model_manager=ModelManager,
        )

    return load
