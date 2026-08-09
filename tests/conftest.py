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
    """Import the add-on against stubbed Anki modules and return its gui_hooks.

    `basic2cloze.__init__` calls main() on import, so importing is what
    registers the hooks.
    """

    def load(
        *,
        cloze_fields_exists: bool,
        hook_exists: bool = True,
        has_cloze_note_type: bool = True,
        # stock Cloze: Text is a cloze field, Back Extra is not
        cloze_ords: tuple = (0,),
        # ids the cache still knows but the collection no longer has, i.e.
        # note types deleted after profile load
        deleted_note_type_ids: tuple = (),
    ):
        profile_hooks = []

        anki = types.ModuleType("anki")
        anki.version = "26.8.1"

        anki_hooks = types.ModuleType("anki.hooks")
        anki_hooks.wrap = lambda old, new, position: old
        anki_hooks.addHook = lambda name, cb: profile_hooks.append((name, cb))

        anki_notes = types.ModuleType("anki.notes")
        anki_notes.Note = FakeNote
        anki_notes.NoteFieldsCheckResult = types.SimpleNamespace(
            NORMAL=0, NOTETYPE_NOT_CLOZE=1, FIELD_NOT_CLOZE=2
        )

        class ModelManager:
            pass

        if cloze_fields_exists:
            ModelManager.cloze_fields = lambda self, mid: []

        anki_models = types.ModuleType("anki.models")
        anki_models.ModelManager = ModelManager

        notetype_ids = {"Basic": BASIC_ID}
        if has_cloze_note_type:
            notetype_ids["Cloze"] = CLOZE_ID

        existing_notetypes = set(notetype_ids.values()) - set(deleted_note_type_ids)

        models = types.SimpleNamespace(
            id_for_name=notetype_ids.get,
            get=lambda notetype_id: (
                {"id": notetype_id} if notetype_id in existing_notetypes else None
            ),
            # only the Cloze note type has cloze fields, so asking about the
            # wrong one has to come back empty rather than quietly succeed
            cloze_fields=lambda notetype_id: (
                list(cloze_ords) if notetype_id == CLOZE_ID else []
            ),
        )
        mw = types.SimpleNamespace(col=types.SimpleNamespace(models=models))

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
        aqt_utils.tooltip = lambda *args, **kwargs: None
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

        return gui_hooks

    return load
