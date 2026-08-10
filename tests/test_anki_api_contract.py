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
    """main() wraps this method, and gates on the attribute existing."""
    assert hasattr(ModelManager, "cloze_fields")


def call_sites(package: str, method: str) -> list[str]:
    """Where `.method(` is called across a package, excluding its definition."""
    found = []
    for path in sorted(package_dir(package).rglob("*.py")):
        text = path.read_text(encoding="utf8", errors="replace")
        for number, line in enumerate(text.splitlines(), start=1):
            if f".{method}(" in line and f"def {method}(" not in line:
                found.append(f"{path.name}:{number}")
    return found


def test_cloze_fields_still_has_a_single_caller():
    """The add-on answers cloze_fields for Basic process-wide, so every caller
    gets that answer. That is only as narrow as intended while the editor is
    the one asking -- a second caller would silently be answered too, and the
    symptom would surface somewhere unrelated to the cloze button.
    """
    callers = call_sites("aqt", "cloze_fields") + call_sites("anki", "cloze_fields")

    assert len(callers) == 1, (
        "cloze_fields no longer has exactly one caller, so wrapping it now "
        f"reaches more than the editor's per-field flags: {callers}"
    )


def function_containing(source: str, needle: str) -> str:
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.FunctionDef):
            continue
        body = ast.get_source_segment(source, node) or ""
        if needle in body:
            return body
    return ""


def test_load_note_asks_cloze_fields_which_fields_are_cloze():
    """The whole fix rests on the editor deriving its per-field flags from
    this call, so that wrapping the method reaches the editor."""
    name, editor = source_of("aqt", *EDITOR_MODULES)

    load_note = function_containing(editor, "setClozeFields(")
    assert load_note, f"{name} no longer sends setClozeFields to the frontend"
    assert "cloze_fields(" in load_note, (
        f"{name} no longer derives its cloze field flags from "
        "models.cloze_fields(), so wrapping that method no longer reaches "
        "the editor's cloze button"
    )


def editor_bundle() -> str:
    bundle = package_dir("_aqt") / "data" / "web" / "js" / "editor.js"
    # not skipped: losing this bundle would mean the classic editor is gone,
    # which is exactly the change worth being told about
    assert bundle.exists(), f"{bundle.name} is no longer shipped"
    return bundle.read_text(encoding="utf8", errors="replace")


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
