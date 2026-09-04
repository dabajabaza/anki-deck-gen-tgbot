# CLAUDE.md

Guidance for Claude Code working in this repository. Read `CONTEXT.md` for the
vocabulary and `docs/ARCHITECTURE.md` for the numbered decisions (`A1`…) before
changing behaviour; code comments cite them.

## What this is

Telegram bot + CLI that build Anki `.apkg` decks from spreadsheets (xlsx/csv/Google
Sheets link/pasted text) with optional gTTS audio. Successor of the `anki/` subproject
of `~/Projects/Automation` (extracted 2026-09-02, rewritten 2026-09-03). Skeleton copied
from `clipivore-tgbot` (`~/Projects/twitter-dl-tgbot`); access/invites from
`lesson-tracker-tgbot`.

**Run bot:** `uv run python -m anki_deck_gen` (needs `.env`, see `.env.example`).
**Run CLI:** `uv run anki-deck-gen --source … --note-type … --lang-pair … --audio-for … --theme card|book`.
**Checks:** `uv run ruff check . && uv run ruff format --check . && uv run mypy src tests && uv run pytest -q`.

## Layout

`src/anki_deck_gen/` — `domain.py` (vocabulary, framework-free), `errors.py`,
`config.py` (`BuildSettings` for CLI, `BotSettings` for the bot), `notetypes/`
(registry; stock Anki templates in `stock.py`), `tables/` (sources → parse → validate),
`build/` (the only genanki/gTTS importer), `db/` + `services/` (SQLite: access, invites,
prefs), `bot/` (aiogram: handlers, texts, keyboards, pending, storage, middlewares),
`runtime/` (worker, watchdog), `__main__.py` (dispatcher assembly — shared with tests).

## Gotchas

- **`pyproject` `name = "anki-deck-gen"` is load-bearing.** hatchling writes
  `_editable_impl_anki_deck_gen.pth`; the deploy registry points at that name. Rename
  it and every release after the first silently runs the previous one.
- **Only `bot/`, `__main__.py`, `runtime/` may import aiogram; only `build/package.py`
  imports genanki, only `build/audio.py` imports gtts.** `tests/test_architecture.py`
  enforces it by parsing imports.
- **`build_dispatcher()` is shared with the test harness.** Middleware order *is* the
  access policy; never assemble a dispatcher by hand in tests.
- **Routers are module-level singletons.** `tests/conftest.py::_SHARED_ROUTERS` detaches
  them between tests and must list every router `build_dispatcher` includes.
- **`Pending` is the only dialog context** (`bot/pending.py`): keyed by user, TTL, extended
  by every step. Settings travel in `callback_data` (≤ 64 bytes). A new table resets
  FSM + Pending. The worker never reads Pending — `BuildRequest` is self-contained.
- **gTTS runs in a thread and cannot be cancelled.** `build_package` checks the
  `abandoned` Event between phrases; the worker sets it on timeout/cancel. Audio is
  sequential per phrase on purpose.
- **Changing a note type's fields requires a new `model_id`.** Anki conflicts on import
  otherwise. Old generator ids (2163323615/16/18, 1759261800, 1762620000) are retired.
- **`access.py` needs `db/engine.py::create_db`** (`isolation_level=None` for SAVEPOINT,
  `READONLY` execution option for the per-update auth check). Do not swap the engine.
- **Texts are plain, Russian, in `bot/texts.py`.** No parse_mode anywhere except `HELP`
  (HTML, sent from `handlers/start.py` with link preview disabled; the example URL is
  escaped). `tests/test_texts.py` rejects `<`/`>` elsewhere and unknown placeholders.
- **Card CSS lives in `notetypes/assets/css/*.css`** (`Theme.CARD`/`Theme.BOOK`), not in the note
  types. Changing CSS needs no new `model_id` (Anki updates a same-schema type on import
  when mtime is newer); `themed = False` on a type skips the theme step in the bot.
  Callback data must stay ≤ 64 bytes — the longest is `t:<type>:<lq>-<la>:<audio>:<theme>`.
- **Card templates and CSS are files, not string literals** (`notetypes/assets/`), read
  verbatim through `importlib.resources`. No templating engine touches them: `{{Front}}`
  is Anki's own syntax and Jinja2 would eat it. A template file must end with exactly one
  newline (the loader strips it); CSS keeps its own. `tests/test_assets.py` guards both,
  and that the folder holds exactly what the registry asks for.
- **`scripts/preview/` is the preview page's source** — Jinja2 template, CSS and JS as
  files; Jinja2 is a dev dependency and never ships to the server.
- **File names are ASCII, tags are not.** `build/slug.py` transliterates with `anyascii`
  for the `.apkg` and cached mp3 names (AnkiDroid refuses non-ASCII names that lost their
  encoding in transit, A16); `sanitize()` stays Unicode because it also cleans tags, which
  the user reads in Anki. Changing the slug format orphans the audio cache.
- **`themes/preview.html` is generated, not hand-edited.** Change CSS in `theme.py`, then
  `uv run python scripts/build_theme_preview.py`; `tests/test_theme_preview.py` fails if the
  committed page is stale. The builder renders the real templates, so it also breaks when a
  note type changes.
- **Tests are hermetic:** `conftest.hermetic_env` chdirs away and drops env vars —
  pydantic-settings resolves `.env` against cwd.
- **The server is FreeBSD without a Rust toolchain.** Compiled deps are pinned to ports
  versions in `[tool.uv] constraint-dependencies`; CI runs `scripts/check-freebsd-pins.py`.
  `requirements.txt` is generated (`uv export … --no-dev -o requirements.txt`) and must
  start with `-e .`.
- **No decks or user data in the repo** — it is public. Local fixtures live in gitignored
  `local/`; tests skip when they are absent.

## Language

Russian for bot texts, README, ARCHITECTURE, CONTEXT, commit messages; English
identifiers and test names.
