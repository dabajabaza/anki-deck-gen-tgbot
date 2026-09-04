"""Диалог бота через настоящий диспетчер: от Таблицы до Задания в очереди.

Каждый тест гоняет апдейты через ``build_dispatcher`` — тот же, что в проде.
Сеть заменена RecordingSession, загрузчик Таблиц — FakeLoader.
"""

from aiogram.methods import SendDocument, SendMessage
from aiogram.types import LinkPreviewOptions

from anki_deck_gen.bot import callbacks, texts
from anki_deck_gen.domain import AudioSide, DeckSettings, Problem, Sheet, Table, Theme
from anki_deck_gen.errors import FileTooLarge, TableUnreadable
from anki_deck_gen.services import access, prefs
from tests.helpers.bot_harness import BotHarness
from tests.helpers.factories import (
    ADMIN_ID,
    GUEST_ID,
    STRANGER_ID,
    make_row,
    make_sheet,
    make_table,
)

# Полный выбор одной кнопкой (шаг оформления уже пройден): так удобнее тестам,
# которым нужно Задание в очереди, а не сам диалог.
NO_AUDIO = callbacks.build(
    DeckSettings(note_type_id="basic", lang_q="en", lang_a="ru", audio=AudioSide.NONE)
)


async def _allow_guest(harness: BotHarness) -> None:
    async with harness.sessionmaker() as s:
        await access.allow_user(s, GUEST_ID, "guest")
        await s.commit()


# ---------- доступ ----------


async def test_a_stranger_gets_silence(harness: BotHarness) -> None:
    await harness.send("/help", user_id=STRANGER_ID)
    assert harness.session.calls == []


async def test_an_admin_gets_help(harness: BotHarness) -> None:
    await harness.send("/help", user_id=ADMIN_ID)
    assert harness.session.last_text() == texts.help_message(None)
    sent = harness.session.calls_of(SendMessage)[-1]
    assert sent.parse_mode == "HTML", "HELP is the one text with markup (A11)"
    assert isinstance(sent.link_preview_options, LinkPreviewOptions)
    assert sent.link_preview_options.is_disabled


async def test_a_group_message_is_ignored(harness: BotHarness) -> None:
    await harness.send("/help", user_id=ADMIN_ID, chat_type="group")
    assert harness.session.calls == []


async def test_an_allowed_guest_gets_through(harness: BotHarness) -> None:
    await _allow_guest(harness)
    await harness.send("/help", user_id=GUEST_ID)
    assert harness.session.sent_texts()


async def test_invite_deep_link_opens_access_once(harness: BotHarness) -> None:
    await harness.send("/invite", user_id=ADMIN_ID)
    code = harness.session.last_text().split("?start=", 1)[1].split()[0]
    harness.session.clear()

    await harness.send(f"/start {code}", user_id=GUEST_ID)
    assert harness.session.last_text().startswith(texts.WELCOME_INVITED)
    harness.session.clear()

    await harness.send("/help", user_id=GUEST_ID)
    assert harness.session.sent_texts(), "access must persist without the link"
    harness.session.clear()

    await harness.send(f"/start {code}", user_id=STRANGER_ID)
    assert harness.session.calls == [], "a redeemed code is dead"


async def test_a_plain_start_from_a_stranger_is_not_a_pass(harness: BotHarness) -> None:
    await harness.send("/start", user_id=STRANGER_ID)
    assert harness.session.calls == []


async def test_allow_by_id_and_access_listing(harness: BotHarness) -> None:
    await harness.send(f"/allow {GUEST_ID}", user_id=ADMIN_ID)
    assert texts.ALLOWED.format(user_id=GUEST_ID) in harness.session.sent_texts()
    harness.session.clear()
    await harness.send("/access", user_id=ADMIN_ID)
    listing = harness.session.last_text()
    assert str(GUEST_ID) in listing and "Админы" in listing


async def test_allow_rejects_garbage(harness: BotHarness) -> None:
    await harness.send("/allow abc", user_id=ADMIN_ID)
    assert harness.session.last_text() == texts.ALLOW_USAGE


async def test_a_guest_cannot_use_admin_commands(harness: BotHarness) -> None:
    await _allow_guest(harness)
    await harness.send("/invite", user_id=GUEST_ID)
    assert harness.session.calls == []


# ---------- приём Таблицы ----------


async def test_a_clean_table_shows_summary_and_note_types(harness: BotHarness) -> None:
    harness.loader.tables["deck.xlsx"] = make_table(("cat", "кот"), ("dog", "пёс"), title="deck")
    await harness.send_document("deck.xlsx", user_id=ADMIN_ID)

    summary = harness.session.last_edit_text()
    assert "Колода «deck»" in summary
    assert texts.SUMMARY_NOTES.format(count=2) in summary
    assert texts.CHOOSE_NOTE_TYPE in summary
    labels = harness.session.last_edit_labels()
    assert "Простая" in labels and texts.BTN_RENAME in labels
    assert harness.pending.get(ADMIN_ID) is not None


async def test_pasted_text_asks_for_a_deck_name_first(harness: BotHarness) -> None:
    await harness.send("cat / кот\ndog / пёс", user_id=ADMIN_ID)
    assert harness.session.last_text() == texts.ASK_DECK_NAME
    harness.session.clear()

    await harness.send("Животные", user_id=ADMIN_ID)
    assert "Колода «Животные»" in harness.session.last_edit_text()
    item = harness.pending.get(ADMIN_ID)
    assert item is not None and item.deck_name == "Животные"


async def test_a_single_line_is_not_a_table(harness: BotHarness) -> None:
    await harness.send("cat кот", user_id=ADMIN_ID)
    assert harness.session.last_text() == texts.ERR_UNSUPPORTED


async def test_an_unreadable_table_is_refused_with_the_detail(harness: BotHarness) -> None:
    harness.loader.tables["bad.csv"] = TableUnreadable("Нужны колонки Q и A.")
    await harness.send_document("bad.csv", user_id=ADMIN_ID)
    expected = texts.ERR_TABLE_UNREADABLE.format(detail="Нужны колонки Q и A.")
    assert harness.session.last_edit_text() == expected
    assert harness.pending.get(ADMIN_ID) is None


async def test_a_too_large_file_is_refused_before_download(harness: BotHarness) -> None:
    harness.loader.tables["huge.xlsx"] = FileTooLarge(size_bytes=6 * 1024 * 1024, limit_bytes=5)
    await harness.send_document("huge.xlsx", user_id=ADMIN_ID)
    assert "Файл слишком большой" in harness.session.last_edit_text()


async def test_a_sheets_link_goes_through_the_loader(harness: BotHarness) -> None:
    url = "https://docs.google.com/spreadsheets/d/abc123/edit#gid=0"
    harness.loader.tables[url] = make_table(("one", "один"), ("two", "два"), title="Числа")
    await harness.send(f"вот таблица {url}", user_id=ADMIN_ID)
    assert harness.loader.loaded[-1].kind == "sheets"
    assert "Колода «Числа»" in harness.session.last_edit_text()


# ---------- Проблемные строки ----------


def _table_with_problems() -> Table:
    rows = [
        make_row(2, "cat", "кот"),
        make_row(3, "dog", ""),
        make_row(4, "", "птица"),
    ]
    return Table(sheets=(make_sheet(None, rows),), title="Звери")


async def test_problem_rows_show_the_problem_keyboard(harness: BotHarness) -> None:
    harness.loader.tables["p.xlsx"] = _table_with_problems()
    await harness.send_document("p.xlsx", user_id=ADMIN_ID)
    text = harness.session.last_edit_text()
    assert texts.SUMMARY_PROBLEMS.format(count=2) in text
    assert "строка 3: пустой ответ" in text
    labels = harness.session.last_edit_labels()
    assert texts.BTN_FIX in labels and texts.BTN_SKIP in labels


async def test_fixing_rows_one_by_one_then_note_types(harness: BotHarness) -> None:
    harness.loader.tables["p.xlsx"] = _table_with_problems()
    await harness.send_document("p.xlsx", user_id=ADMIN_ID)
    harness.session.clear()

    await harness.press(callbacks.PROBLEMS_FIX, user_id=ADMIN_ID)
    assert "Строка 3" in harness.session.last_text()
    await harness.send("пёс", user_id=ADMIN_ID)
    assert "Строка 4" in harness.session.last_text()
    await harness.send("bird", user_id=ADMIN_ID)
    assert texts.FIX_DONE in harness.session.sent_texts()

    item = harness.pending.get(ADMIN_ID)
    assert item is not None
    assert item.unresolved() == []
    assert item.fixes[(None, 3)].answer == "пёс"
    assert item.fixes[(None, 4)].question == "bird"
    assert texts.CHOOSE_NOTE_TYPE in harness.session.last_edit_text()


async def test_skip_during_fixing_marks_the_row_skipped(harness: BotHarness) -> None:
    harness.loader.tables["p.xlsx"] = _table_with_problems()
    await harness.send_document("p.xlsx", user_id=ADMIN_ID)
    await harness.press(callbacks.PROBLEMS_FIX, user_id=ADMIN_ID)
    await harness.send("/skip", user_id=ADMIN_ID)
    await harness.send("/skip", user_id=ADMIN_ID)
    item = harness.pending.get(ADMIN_ID)
    assert item is not None and item.skips == {(None, 3), (None, 4)}


async def test_cancel_during_fixing_keeps_the_table(harness: BotHarness) -> None:
    harness.loader.tables["p.xlsx"] = _table_with_problems()
    await harness.send_document("p.xlsx", user_id=ADMIN_ID)
    await harness.press(callbacks.PROBLEMS_FIX, user_id=ADMIN_ID)
    harness.session.clear()
    await harness.send("/cancel", user_id=ADMIN_ID)
    assert texts.FIX_CANCELLED in harness.session.sent_texts()
    item = harness.pending.get(ADMIN_ID)
    assert item is not None and len(item.unresolved()) == 2


async def test_skip_all_button_resolves_everything(harness: BotHarness) -> None:
    harness.loader.tables["p.xlsx"] = _table_with_problems()
    await harness.send_document("p.xlsx", user_id=ADMIN_ID)
    await harness.press(callbacks.PROBLEMS_SKIP, user_id=ADMIN_ID)
    item = harness.pending.get(ADMIN_ID)
    assert item is not None and item.unresolved() == []
    assert texts.CHOOSE_NOTE_TYPE in harness.session.last_edit_text()


async def test_cancel_button_forgets_the_table(harness: BotHarness) -> None:
    harness.loader.tables["p.xlsx"] = _table_with_problems()
    await harness.send_document("p.xlsx", user_id=ADMIN_ID)
    await harness.press(callbacks.PROBLEMS_CANCEL, user_id=ADMIN_ID)
    assert harness.pending.get(ADMIN_ID) is None
    assert harness.session.last_edit_text() == texts.CANCELLED


async def test_a_separatorless_line_is_fixed_with_a_full_pair(harness: BotHarness) -> None:
    await harness.send("cat / кот\nтут нет разделителя\ndog / пёс", user_id=ADMIN_ID)
    await harness.send("Звери", user_id=ADMIN_ID)
    item = harness.pending.get(ADMIN_ID)
    assert item is not None
    assert [p.problem for p in item.unresolved()] == [Problem.NO_SEPARATOR]
    await harness.press(callbacks.PROBLEMS_FIX, user_id=ADMIN_ID)
    await harness.send("всё ещё без", user_id=ADMIN_ID)
    assert harness.session.last_text() == texts.FIX_STILL_NO_SEPARATOR
    await harness.send("bird / птица", user_id=ADMIN_ID)
    assert item.fixes[(None, 2)].question == "bird"


async def test_text_during_a_dialog_answers_it_instead_of_starting_a_table(
    harness: BotHarness,
) -> None:
    """«bird / птица» — и ответ на правку, и текст-таблица; в диалоге выигрывает ответ."""
    harness.loader.tables["p.xlsx"] = _table_with_problems()
    await harness.send_document("p.xlsx", user_id=ADMIN_ID)
    await harness.press(callbacks.RENAME, user_id=ADMIN_ID)
    await harness.send("Звери / птицы", user_id=ADMIN_ID)
    item = harness.pending.get(ADMIN_ID)
    assert item is not None and item.deck_name == "Звери / птицы"


async def test_a_new_table_resets_a_fix_dialog(harness: BotHarness) -> None:
    harness.loader.tables["p.xlsx"] = _table_with_problems()
    harness.loader.tables["clean.xlsx"] = make_table(("a", "б"), ("c", "д"), title="clean")
    await harness.send_document("p.xlsx", user_id=ADMIN_ID)
    await harness.press(callbacks.PROBLEMS_FIX, user_id=ADMIN_ID)
    await harness.send_document("clean.xlsx", user_id=ADMIN_ID)
    item = harness.pending.get(ADMIN_ID)
    assert item is not None and item.deck_name == "clean"
    harness.session.clear()
    # Текст теперь — не ответ на правку, а мусор: диалог сброшен.
    await harness.send("пёс", user_id=ADMIN_ID)
    assert harness.session.last_text() == texts.ERR_UNSUPPORTED


# ---------- переименование ----------


async def test_rename_changes_the_deck_name(harness: BotHarness) -> None:
    harness.loader.tables["deck.xlsx"] = make_table(("a", "б"), ("c", "д"), title="deck")
    await harness.send_document("deck.xlsx", user_id=ADMIN_ID)
    await harness.press(callbacks.RENAME, user_id=ADMIN_ID)
    assert harness.session.last_text() == texts.RENAME_PROMPT
    await harness.send("   ", user_id=ADMIN_ID)
    assert harness.session.last_text() == texts.NAME_EMPTY
    await harness.send("Новое имя", user_id=ADMIN_ID)
    item = harness.pending.get(ADMIN_ID)
    assert item is not None and item.deck_name == "Новое имя"
    assert "Колода «Новое имя»" in harness.session.last_edit_text()


# ---------- Настройки и очередь ----------


async def test_choosing_a_type_shows_languages_without_last_when_no_prefs(
    harness: BotHarness,
) -> None:
    harness.loader.tables["deck.xlsx"] = make_table(("a", "б"), ("c", "д"), title="deck")
    await harness.send_document("deck.xlsx", user_id=ADMIN_ID)
    await harness.press(callbacks.note_type("basic-reversed"), user_id=ADMIN_ID)
    assert "Простая (с обратной карточкой)" in harness.session.last_edit_text()
    labels = harness.session.last_edit_labels()
    assert texts.BTN_LANG_DEFAULT in labels
    assert not any(label.startswith("Как в прошлый раз") for label in labels)


async def test_the_default_language_button_enqueues_and_saves_prefs(harness: BotHarness) -> None:
    harness.loader.tables["deck.xlsx"] = make_table(("a", "б"), ("c", "д"), title="deck")
    await harness.send_document("deck.xlsx", user_id=ADMIN_ID)
    chosen = DeckSettings(
        note_type_id="basic-reversed", lang_q="en", lang_a="ru", audio=AudioSide.QUESTION
    )
    await harness.press(callbacks.settings(chosen), user_id=ADMIN_ID)
    # Языки выбраны — остался шаг оформления, Задания в очереди ещё нет.
    assert "Оформление карточек" in harness.session.last_edit_text()
    assert "озвучен English" in harness.session.last_edit_text()
    labels = harness.session.last_edit_labels()
    assert texts.BTN_THEME_CARD in labels and texts.BTN_THEME_BOOK in labels
    assert harness.queue.load == 0

    await harness.press(callbacks.build(chosen), user_id=ADMIN_ID)
    request = await harness.take()
    assert request.build.deck_name == "deck"
    assert request.build.settings.note_type_id == "basic-reversed"
    assert request.build.settings.audio is AudioSide.QUESTION
    assert request.build.settings.theme is Theme.CARD
    assert len(request.build.table.rows) == 2
    assert harness.pending.get(ADMIN_ID) is None, "pending ends when the request is queued"
    assert texts.QUEUED in harness.session.last_edit_text()

    async with harness.sessionmaker() as s:
        saved = await prefs.get_last(s, ADMIN_ID)
    assert saved is not None and saved.lang_q == "en" and saved.theme is Theme.CARD


async def test_last_used_button_appears_and_reuses_languages_and_theme(
    harness: BotHarness,
) -> None:
    async with harness.sessionmaker() as s:
        await prefs.save_last(
            s,
            ADMIN_ID,
            DeckSettings(
                note_type_id="basic",
                lang_q="vi",
                lang_a="en",
                audio=AudioSide.BOTH,
                theme=Theme.BOOK,
            ),
        )
        await s.commit()
    harness.loader.tables["deck.xlsx"] = make_table(("a", "б"), title="deck")
    await harness.send_document("deck.xlsx", user_id=ADMIN_ID)
    await harness.press(callbacks.note_type("basic-typing"), user_id=ADMIN_ID)
    labels = harness.session.last_edit_labels()
    assert any(
        "Как в прошлый раз" in label and "Tiếng Việt" in label and "Учебник" in label
        for label in labels
    )

    # «Как в прошлый раз» — одна кнопка до очереди, без шага оформления.
    await harness.press(callbacks.last_used("basic-typing"), user_id=ADMIN_ID)
    request = await harness.take()
    assert request.build.settings.note_type_id == "basic-typing"
    assert request.build.settings.lang_q == "vi"
    assert request.build.settings.audio is AudioSide.BOTH
    assert request.build.settings.theme is Theme.BOOK


async def test_configure_walks_pairs_then_audio(harness: BotHarness) -> None:
    harness.loader.tables["deck.xlsx"] = make_table(("a", "б"), title="deck")
    await harness.send_document("deck.xlsx", user_id=ADMIN_ID)
    await harness.press(callbacks.configure("basic"), user_id=ADMIN_ID)
    assert "Язык вопроса → язык ответа" in harness.session.last_edit_text()
    await harness.press(callbacks.language_pair("basic", "de", "ru"), user_id=ADMIN_ID)
    assert "Deutsch → Русский" in harness.session.last_edit_text()
    assert texts.BTN_AUDIO_Q.format(lang="Deutsch") in harness.session.last_edit_labels()
    chosen = DeckSettings(
        note_type_id="basic", lang_q="de", lang_a="ru", audio=AudioSide.ANSWER, theme=Theme.BOOK
    )
    await harness.press(callbacks.settings(chosen), user_id=ADMIN_ID)
    assert "Оформление карточек" in harness.session.last_edit_text()
    assert texts.BTN_BACK in harness.session.last_edit_labels()
    await harness.press(callbacks.build(chosen), user_id=ADMIN_ID)
    request = await harness.take()
    assert request.build.settings == chosen


async def test_back_from_the_theme_step_returns_to_the_audio_step(harness: BotHarness) -> None:
    harness.loader.tables["deck.xlsx"] = make_table(("a", "б"), title="deck")
    await harness.send_document("deck.xlsx", user_id=ADMIN_ID)
    chosen = DeckSettings(note_type_id="basic", lang_q="de", lang_a="ru", audio=AudioSide.NONE)
    await harness.press(callbacks.settings(chosen), user_id=ADMIN_ID)
    await harness.press(callbacks.language_pair("basic", "de", "ru"), user_id=ADMIN_ID)
    assert "Что озвучить?" in harness.session.last_edit_text()


async def test_a_type_with_its_own_css_skips_the_theme_step(harness: BotHarness) -> None:
    """Вьетнамский тип не темизируется — выбор озвучки сразу ставит Задание в очередь."""
    harness.loader.tables["deck.xlsx"] = make_table(("a", "б"), title="deck")
    await harness.send_document("deck.xlsx", user_id=ADMIN_ID)
    chosen = DeckSettings(
        note_type_id="vietnamese", lang_q="vi", lang_a="en", audio=AudioSide.QUESTION
    )
    await harness.press(callbacks.settings(chosen), user_id=ADMIN_ID)
    request = await harness.take()
    assert request.build.settings == chosen
    assert texts.QUEUED in harness.session.last_edit_text()


async def test_fixes_and_skips_travel_with_the_request(harness: BotHarness) -> None:
    harness.loader.tables["p.xlsx"] = _table_with_problems()
    await harness.send_document("p.xlsx", user_id=ADMIN_ID)
    await harness.press(callbacks.PROBLEMS_FIX, user_id=ADMIN_ID)
    await harness.send("пёс", user_id=ADMIN_ID)
    await harness.send("/skip", user_id=ADMIN_ID)
    await harness.press(NO_AUDIO, user_id=ADMIN_ID)
    request = await harness.take()
    assert request.build.fixes[(None, 3)].answer == "пёс"
    assert request.build.skips == frozenset({(None, 4)})


async def test_a_full_queue_refuses_with_a_verdict(harness: BotHarness) -> None:
    harness.loader.tables["deck.xlsx"] = make_table(("a", "б"), title="deck")
    for _ in range(harness.queue.limit):
        await harness.send_document("deck.xlsx", user_id=ADMIN_ID)
        await harness.press(NO_AUDIO, user_id=ADMIN_ID)
    harness.session.clear()
    await harness.send_document("deck.xlsx", user_id=ADMIN_ID)
    await harness.press(NO_AUDIO, user_id=ADMIN_ID)
    assert harness.session.last_edit_text() == texts.QUEUE_FULL.format(limit=harness.queue.limit)


async def test_a_table_no_type_fits_is_explained(harness: BotHarness) -> None:
    rows = [make_row(2, "a", "б")]
    table = Table(sheets=(Sheet(name=None, columns=frozenset({"Q"}), rows=tuple(rows)),), title="x")
    harness.loader.tables["x.xlsx"] = table
    await harness.send_document("x.xlsx", user_id=ADMIN_ID)
    assert "Ни один тип записи не подходит" in harness.session.last_edit_text()
    assert harness.session.last_edit_labels() == []


async def test_a_stale_button_after_expiry_says_so(harness: BotHarness) -> None:
    harness.loader.tables["deck.xlsx"] = make_table(("a", "б"), title="deck")
    await harness.send_document("deck.xlsx", user_id=ADMIN_ID)
    item = harness.pending.get(ADMIN_ID)
    assert item is not None
    status_id = item.status_message_id
    harness.pending.pop(ADMIN_ID)
    harness.session.clear()
    await harness.press(callbacks.note_type("basic"), user_id=ADMIN_ID, message_id=status_id)
    assert "Таблица устарела" in harness.session.last_edit_text()


async def test_template_command_sends_a_workbook(harness: BotHarness) -> None:
    await harness.send("/template", user_id=ADMIN_ID)
    docs = harness.session.calls_of(SendDocument)
    assert len(docs) == 1 and docs[0].caption == texts.TEMPLATE_CAPTION


async def test_unknown_button_is_answered_not_left_spinning(harness: BotHarness) -> None:
    await harness.press("garbage:1", user_id=ADMIN_ID, message_id=7000)
    answers = harness.session.answered_callbacks()
    assert answers and answers[-1].text == texts.ERR_UNKNOWN_BUTTON


async def test_summary_mentions_duplicates_and_empty_sheets(harness: BotHarness) -> None:
    rows_a = [make_row(2, "cat", "кот", sheet="A"), make_row(3, "cat", "кошка", sheet="A")]
    table = Table(sheets=(make_sheet("A", rows_a), make_sheet("Пусто", [])), title="Двойники")
    harness.loader.tables["d.xlsx"] = table
    await harness.send_document("d.xlsx", user_id=ADMIN_ID)
    text = harness.session.last_edit_text()
    assert texts.SUMMARY_DUPLICATES.format(count=1) in text
    assert "«Пусто»" in text


async def test_a_button_from_an_older_status_message_is_refused(harness: BotHarness) -> None:
    """Старая клавиатура не должна управлять новой Таблицей (A3)."""
    harness.loader.tables["old.xlsx"] = make_table(("a", "б"), title="old")
    harness.loader.tables["new.xlsx"] = make_table(("c", "д"), ("e", "ё"), title="new")
    await harness.send_document("old.xlsx", user_id=ADMIN_ID)
    old_item = harness.pending.get(ADMIN_ID)
    assert old_item is not None
    old_status = old_item.status_message_id
    await harness.send_document("new.xlsx", user_id=ADMIN_ID)
    harness.session.clear()

    await harness.press(NO_AUDIO, user_id=ADMIN_ID, message_id=old_status)
    answers = harness.session.answered_callbacks()
    assert answers and answers[-1].text == texts.ERR_UNKNOWN_BUTTON
    assert harness.queue.load == 0, "the stale button must not enqueue anything"
    assert harness.pending.get(ADMIN_ID) is not None, "the new table stays pending"

    await harness.press(callbacks.PROBLEMS_CANCEL, user_id=ADMIN_ID, message_id=old_status)
    assert harness.pending.get(ADMIN_ID) is not None, "a stale cancel must not drop the new table"


async def test_max_notes_counts_fixed_rows_too(harness: BotHarness) -> None:
    """Правки в диалоге не обходят потолок MAX_NOTES."""
    from anki_deck_gen.domain import Table as _Table

    rows = [make_row(2, "ok", "да"), make_row(3, "one", ""), make_row(4, "two", "")]
    table = _Table(sheets=(make_sheet(None, rows),), title="Лимит")
    harness.loader.tables["limit.xlsx"] = table
    harness.dp["settings"] = harness.dp["settings"].model_copy(update={"max_notes": 2})
    await harness.send_document("limit.xlsx", user_id=ADMIN_ID)
    await harness.press(callbacks.PROBLEMS_FIX, user_id=ADMIN_ID)
    await harness.send("раз", user_id=ADMIN_ID)
    await harness.send("два", user_id=ADMIN_ID)
    item = harness.pending.get(ADMIN_ID)
    assert item is not None and item.notes == 3
    await harness.press(NO_AUDIO, user_id=ADMIN_ID)
    assert harness.queue.load == 0
    assert harness.session.last_edit_text() == texts.ERR_TOO_MANY_ROWS.format(count=3, limit=2)
    assert harness.pending.get(ADMIN_ID) is None


async def test_cancel_on_an_expired_table_also_closes_the_fix_dialog(harness: BotHarness) -> None:
    harness.loader.tables["p.xlsx"] = _table_with_problems()
    await harness.send_document("p.xlsx", user_id=ADMIN_ID)
    await harness.press(callbacks.PROBLEMS_FIX, user_id=ADMIN_ID)
    item = harness.pending.get(ADMIN_ID)
    assert item is not None
    status_id = item.status_message_id
    item.deadline = 0.0  # истёк
    harness.session.clear()
    await harness.press(callbacks.PROBLEMS_CANCEL, user_id=ADMIN_ID, message_id=status_id)
    assert "Таблица устарела" in harness.session.last_edit_text()
    harness.session.clear()
    # Диалог закрыт: текст идёт в fallback, а не в правку строк.
    await harness.send("пёс", user_id=ADMIN_ID)
    assert harness.session.last_text() == texts.ERR_UNSUPPORTED


async def test_a_stale_press_does_not_extend_the_current_table(harness: BotHarness) -> None:
    harness.loader.tables["old.xlsx"] = make_table(("a", "б"), title="old")
    harness.loader.tables["new.xlsx"] = make_table(("c", "д"), title="new")
    await harness.send_document("old.xlsx", user_id=ADMIN_ID)
    old_item = harness.pending.get(ADMIN_ID)
    assert old_item is not None
    old_status = old_item.status_message_id
    await harness.send_document("new.xlsx", user_id=ADMIN_ID)
    item = harness.pending.get(ADMIN_ID)
    assert item is not None
    from time import monotonic

    marker = monotonic() + 100.0  # живой, но короче полного TTL — продление заметно
    item.deadline = marker
    await harness.press(callbacks.note_type("basic"), user_id=ADMIN_ID, message_id=old_status)
    await harness.press(callbacks.PROBLEMS_FIX, user_id=ADMIN_ID, message_id=old_status)
    assert item.deadline == marker, "a refused press must not touch the TTL"
    await harness.press(callbacks.note_type("basic"), user_id=ADMIN_ID)
    assert item.deadline > marker, "an accepted press extends it"
