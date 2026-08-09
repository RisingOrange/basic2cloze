# Automatic Basic To Cloze

[![AnkiWeb page](https://img.shields.io/badge/AnkiWeb-addon-blue.svg)](https://ankiweb.net/shared/info/800723229)

Patreon link of original author:
[![Donate via patreon](https://img.shields.io/badge/patreon-donate-green.svg)](https://www.patreon.com/trgk)


Automatically convert cloze-y things to cloze type.

![Example image](screenshots/basic2cloze.gif)

## Compatibility

This add-on works with Anki's classic editor. It does nothing in the newer
Svelte editor, which is currently behind the `SVELTE_EDITOR` experimental
feature flag and off by default: that editor gets its note data straight from
the backend and does not run the hooks this add-on relies on.

## Tests

This add-on breaks when Anki changes, so most of the tests check that the Anki
internals it hooks into still exist, against whatever Anki release is current.
Worth running when a new Anki comes out:

```sh
uv venv
uv pip install pytest anki
uv pip install --no-deps aqt   # only read as source text, so PyQt6 isn't needed
uv run --no-project pytest
```

A failure names the add-on code that depended on whatever Anki removed.
