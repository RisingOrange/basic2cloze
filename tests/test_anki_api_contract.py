"""Checks that the Anki internals this add-on hooks into still exist.

Every bug in this add-on's history has been "Anki changed", not "our logic is
wrong", so these tests are pointed at Anki rather than at us. Run them against
the newest Anki release to find out what the next release broke.

`aqt` is inspected as source text rather than imported, so this needs no Qt:
install it with `--no-deps` and nothing here imports it.
"""

import ast
import importlib.util
from pathlib import Path

import pytest

# anki.hooks_gen imports anki.cards, so importing anki.models or anki.notes
# first hits a circular import; anki.collection pulls them in in a working order
pytest.importorskip("anki.collection")

from anki.models import ModelManager  # noqa: E402
from anki.notes import NoteFieldsCheckResult  # noqa: E402


def package_dir(name: str) -> Path:
    spec = importlib.util.find_spec(name)
    if spec is None or not spec.submodule_search_locations:
        pytest.skip(f"{name} is not installed")
    return Path(list(spec.submodule_search_locations)[0])


def source_of(package: str, *candidates: str) -> tuple[str, str]:
    """Return (filename, text) of the first candidate that exists.

    Anki moves code between modules (Editor lived in aqt/editor.py until 26.8
    moved it to aqt/editor_legacy.py), so callers pass every known home.
    """
    directory = package_dir(package)
    for candidate in candidates:
        path = directory / candidate
        if path.exists():
            return candidate, path.read_text(encoding="utf8", errors="replace")
    pytest.fail(f"none of {candidates} found in {package} -- did Anki move them?")


EDITOR_MODULES = ("editor_legacy.py", "editor.py")
ADDCARDS_MODULES = ("addcards_legacy.py", "addcards.py")


def test_cloze_fields_exists_on_model_manager():
    """main() gates the cloze-field widening on this attribute existing."""
    assert hasattr(ModelManager, "cloze_fields")


def test_editor_will_load_note_hook_exists():
    """We append our setClozeFields() call through this filter hook."""
    _, hooks = source_of("_aqt", "hooks.py")

    assert "editor_will_load_note = " in hooks


def function_containing(source: str, needle: str) -> str:
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.FunctionDef):
            continue
        body = ast.get_source_segment(source, node) or ""
        if needle in body:
            return body
    return ""


def test_load_note_filters_its_js_through_the_hook():
    """Our appended JS only runs because loadNote filters the batch first."""
    name, editor = source_of("aqt", *EDITOR_MODULES)

    assert "gui_hooks.editor_will_load_note(" in editor, (
        f"{name} no longer filters its load JS -- the cloze-field widening in "
        "enable_cloze_in_all_fields_for_basic will silently stop applying"
    )


def test_cloze_fields_are_set_in_the_js_batch_we_filter():
    """Our override has to land in the same batch, not a separate eval."""
    name, editor = source_of("aqt", *EDITOR_MODULES)

    load_note = function_containing(editor, "gui_hooks.editor_will_load_note(")
    assert load_note, f"{name} no longer filters any JS through the hook"
    assert "setClozeFields(" in load_note, (
        f"setClozeFields moved out of the {name} function that filters its JS "
        "through editor_will_load_note, so appending to that JS no longer wins"
    )


def editor_bundle() -> str:
    bundle = package_dir("_aqt") / "data" / "web" / "js" / "editor.js"
    if not bundle.exists():
        pytest.skip("editor.js bundle not present in this build")
    return bundle.read_text(encoding="utf8", errors="replace")


def test_editor_frontend_exposes_set_cloze_fields():
    """enable_cloze_in_all_fields_for_basic calls this global by name."""
    assert "setClozeFields" in editor_bundle()


def test_editor_frontend_exposes_the_notetype_toolbar():
    """maybe_show_cloze_button reaches the cloze button through this module.

    Widening the cloze fields only enables the button; this is what makes it
    visible in the first place, so both halves need the frontend to hold still.
    """
    bundle = editor_bundle()

    assert '"anki/NoteEditor"' in bundle, (
        "the editor no longer registers anki/NoteEditor -- the require() in "
        "maybe_show_cloze_button will stop finding it"
    )
    # matched loosely: everything else in that registration is a minified name
    registration = bundle.split('"anki/NoteEditor"', 1)[1][:200]
    assert "instances" in registration, (
        "anki/NoteEditor no longer exposes instances, which "
        "maybe_show_cloze_button indexes to reach the toolbar"
    )


def test_add_note_problem_is_filtered_through_addons():
    """convert_basic_to_cloze clears Anki's objection through this filter."""
    name, addcards = source_of("aqt", *ADDCARDS_MODULES)

    assert "gui_hooks.add_cards_will_add_note(" in addcards, (
        f"{name} no longer filters the add problem through add-ons -- Basic "
        "notes containing clozes would be rejected before we convert them"
    )


@pytest.mark.parametrize(
    "member", ["NORMAL", "NOTETYPE_NOT_CLOZE", "FIELD_NOT_CLOZE"]
)
def test_note_fields_check_results_we_suppress(member):
    """_update_duplicate_display_ignore_cloze_problems_for_basic_notes maps these."""
    assert hasattr(NoteFieldsCheckResult, member)


def test_editor_has_update_duplicate_display():
    """We wrap this method to hide cloze warnings on Basic notes."""
    name, editor = source_of("aqt", *EDITOR_MODULES)

    assert "def _update_duplicate_display(" in editor, (
        f"{name} no longer defines _update_duplicate_display"
    )
