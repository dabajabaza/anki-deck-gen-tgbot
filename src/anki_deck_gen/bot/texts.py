"""Все строки, которые говорит бот, в одном месте.

По-русски и простым текстом — без HTML и Markdown: ответы цитируют то, что бот не
контролирует (имена листов, вопросы из таблицы, сообщения Google), и простой
текст — единственный формат, который они не могут сломать. Единственное
исключение — HELP: он статичный, идёт с parse_mode=HTML и несёт жирные
подзаголовки и ссылку словами; подставляемый в него URL экранируется.
tests/test_texts.py следит, чтобы разметки не появилось где-то ещё, а
плейсхолдеры совпадали с тем, что подставляют вызывающие.

Словарь — из CONTEXT.md и русской локализации Anki: Запись, Карточка, Колода,
Тип записи, Метка. Не «заметка», не «тег».
"""

import html

from anki_deck_gen.domain import AudioSide, DeckSettings, Problem, ProblemRow, Summary, Theme

# --- команды -----------------------------------------------------------------

CMD_HELP = "Как пользоваться"
CMD_TEMPLATE = "Шаблон таблицы"
CMD_INVITE = "Ссылка-приглашение"
CMD_ALLOW = "Допустить по id"
CMD_ACCESS = "Кто допущен"

# HTML: единственный текст с разметкой (см. докстринг модуля). Эмодзи — однотонные.
HELP = (
    "<b>Я делаю колоды Anki из таблиц.</b>\n\n"
    "Пришлите таблицу одним из трёх способов:\n"
    "1️⃣ файлом .xlsx или .csv;\n"
    "2️⃣ ссылкой на Google Таблицу — откройте доступ «всем, у кого есть ссылка»;\n"
    "3️⃣ текстом — все строки одним сообщением, по строке на карточку: «вопрос / ответ».\n\n"
    "<b>Заголовок</b> — первая строка таблицы: колонки Q и A (или Вопрос и Ответ).\n"
    "<b>Необязательные колонки:</b> Deck/Колода — подколода, Tags/Метки — метки через запятую.\n"
    "<b>Несколько листов</b> — каждый лист становится подколодой.\n\n"
    "Дальше я спрошу тип записи (как в Anki), языки для озвучки и оформление карточек — "
    "и пришлю файл .apkg, который открывается в Anki двойным щелчком.\n\n"
    "▫️ /template — шаблон таблицы для заполнения{example}"
)
HELP_EXAMPLE = '\n▫️ Пример готовой таблицы: <a href="{url}">открыть в Google Таблицах</a>'
WELCOME_INVITED = "Доступ открыт.\n\n"

TEMPLATE_FILENAME = "anki-template.xlsx"
TEMPLATE_CAPTION = (
    "Шаблон таблицы. Заполните листы и пришлите файл обратно — "
    "или загрузите его в Google Таблицы и пришлите ссылку."
)

# --- админ -------------------------------------------------------------------

INVITE_LINK = (
    "Одноразовая ссылка, действует {hours} ч:\n{link}\n\nПерешедший по ней получит доступ к боту."
)
ALLOW_USAGE = (
    "Использование: /allow ID — например, /allow 123456789\n"
    "Узнать id можно у @userinfobot. Для одноразовой ссылки — /invite."
)
ALLOWED = "Пользователь {user_id} допущен."
ACCESS_ADMINS = "Админы ({count}): {ids}"
ACCESS_GUESTS = "Гости ({count}):\n{rows}"
ACCESS_GUEST_ROW = "  {user_id}{username}"
ACCESS_NO_GUESTS = "Гости: пока никого."
ACCESS_INVITES = "Непогашенных приглашений: {count}"

# --- разбор таблицы ----------------------------------------------------------

READING = "⏳ Читаю таблицу…"
ASK_DECK_NAME = "Как назвать колоду? Пришлите имя одним сообщением."
RENAME_PROMPT = "Пришлите новое имя колоды одним сообщением."
NAME_EMPTY = "Имя пустое. Пришлите ещё раз."

SUMMARY_TITLE = "Колода «{deck}»"
SUMMARY_SHEETS = "Листов: {count}"
SUMMARY_NOTES = "Записей: {count}"
SUMMARY_PROBLEMS = "Проблемных строк: {count}"
SUMMARY_DUPLICATES = "Повторяющихся вопросов: {count} — Anki пометит их как дубли"
SUMMARY_EMPTY_SHEETS = "Листы без записей (пропущу): {names}"
SUMMARY_SEPARATOR = " · "

PROBLEM_HEADER = "Проблемные строки:"
PROBLEM_LINE = "строка {number}{sheet}: {reason}"
PROBLEM_SHEET = ", лист «{sheet}»"
PROBLEM_MORE = "…и ещё {count}"
PROBLEM_EMPTY_QUESTION = "пустой вопрос"
PROBLEM_EMPTY_ANSWER = "пустой ответ"
PROBLEM_NO_SEPARATOR = "нет разделителя «вопрос / ответ»"
PROBLEM_QUESTION = "Что делаем с проблемными строками?"

BTN_FIX = "Исправить здесь"
BTN_SKIP = "Пропустить плохие"
BTN_CANCEL = "Отменить"
BTN_RENAME = "Переименовать"

FIX_PROMPT_ANSWER = (
    "Строка {number}{sheet}: вопрос «{question}» — ответ пустой.\n"
    "Пришлите ответ. /skip — пропустить строку, /cancel — прервать."
)
FIX_PROMPT_QUESTION = (
    "Строка {number}{sheet}: ответ «{answer}» — вопрос пустой.\n"
    "Пришлите вопрос. /skip — пропустить строку, /cancel — прервать."
)
FIX_PROMPT_SEPARATOR = (
    "Строка {number}: «{line}» — не вижу разделителя.\n"
    "Пришлите строку вида «вопрос / ответ». /skip — пропустить, /cancel — прервать."
)
FIX_STILL_NO_SEPARATOR = (
    "Всё ещё не вижу разделителя. Формат: «вопрос / ответ», слэш с пробелами. /skip — пропустить."
)
FIX_DONE = "Все строки разобраны."
FIX_CANCELLED = "Правка прервана."
CANCELLED = "Отменено. Поправьте таблицу и пришлите снова."

# --- настройки колоды --------------------------------------------------------

CHOOSE_NOTE_TYPE = "Выберите тип записи:"
NO_COMPATIBLE_TYPES = (
    "Ни один тип записи не подходит к колонкам этой таблицы.\n{needs}\n\n"
    "Поправьте заголовок и пришлите таблицу снова."
)
NOTE_TYPE_NEEDS = "• {label}: нужны колонки {columns}"
CHOOSE_LANGUAGES = "Тип записи: {label}.\nЯзыки и озвучка:"
CHOOSE_PAIR = "Тип записи: {label}.\nЯзык вопроса → язык ответа:"
CHOOSE_AUDIO = "Тип записи: {label}. Языки: {pair}.\nЧто озвучить?"
CHOOSE_THEME = "Тип записи: {label}. {description}.\nОформление карточек:"

BTN_LANG_DEFAULT = "English → Русский, озвучен English"
BTN_LANG_NONE = "Без озвучки"
BTN_LANG_LAST = "Как в прошлый раз: {description}"
BTN_LANG_CONFIGURE = "Настроить…"
BTN_AUDIO_NONE = "Ничего"
BTN_AUDIO_Q = "Вопрос ({lang})"
BTN_AUDIO_A = "Ответ ({lang})"
BTN_AUDIO_BOTH = "Обе стороны"
BTN_BACK = "← Назад"
BTN_THEME_CARD = "Карточка — светлая карточка на сером фоне"
BTN_THEME_BOOK = "Учебник — книжный шрифт на бумажном фоне"
THEME_CARD = "Карточка"
THEME_BOOK = "Учебник"

LANG_NAMES = {
    "en": "English",
    "ru": "Русский",
    "vi": "Tiếng Việt",
    "de": "Deutsch",
    "fr": "Français",
    "es": "Español",
    "it": "Italiano",
}
# Пары, предлагаемые в «Настроить…»: вопрос → ответ.
LANGUAGE_PAIRS = (
    ("en", "ru"),
    ("ru", "en"),
    ("vi", "en"),
    ("de", "ru"),
    ("fr", "ru"),
    ("es", "ru"),
)
DEFAULT_SETTINGS_LANGS = ("en", "ru")

# --- очередь и сборка --------------------------------------------------------

QUEUED = "⏳ Собираю колоду…"
QUEUED_POSITION = "⏳ В очереди: {position}. Соберу, как освобожусь."
QUEUE_FULL = "Очередь полна ({limit} заданий). Попробуйте через несколько минут."
BUILDING = "⏳ Собираю колоду…"
BUILDING_PROGRESS = "⏳ Собираю колоду… озвучено {done}/{total}"
SENDING = "⏳ Отправляю файл…"
DONE_FALLBACK = "Готово — файл выше."

VERDICT = "Колода «{deck}»: {parts}."
VERDICT_SKIPPED = "пропущено строк: {count}"
VERDICT_DUPLICATES = "повторяющихся вопросов: {count}"
VERDICT_IMPORT_HINT = "\n\nОткройте файл в Anki — колода добавится в коллекцию."

# --- отказы ------------------------------------------------------------------

ERR_UNSUPPORTED = (
    "Не могу сделать из этого колоду. Пришлите файл .xlsx или .csv, ссылку на Google Таблицу "
    "или текст «вопрос / ответ» по строке. /help — подробнее."
)
ERR_FILE_TOO_LARGE = "Файл слишком большой ({size}), потолок — {limit} MB."
ERR_TABLE_UNREADABLE = "Не разобрал таблицу. {detail}"
ERR_SHEET_NOT_SHARED = (
    "Google Таблица закрыта. Откройте доступ: «Настройки доступа» → "
    "«Все, у кого есть ссылка» → «Читатель», и пришлите ссылку снова."
)
ERR_SHEET_UNREACHABLE = "Не удалось скачать Google Таблицу — Google не отвечает. Попробуйте позже."
ERR_TOO_MANY_ROWS = "В таблице {count} записей, потолок — {limit}. Разбейте на несколько таблиц."
ERR_MISSING_COLUMNS = "Типу записи «{label}» нужны колонки {columns} — в таблице их нет."
ERR_TTS = (
    "Озвучка недоступна: Google TTS не отвечает. Колоду без озвучки молча не собираю — "
    "попробуйте позже или пришлите таблицу снова и выберите «Без озвучки»."
)
ERR_TIMED_OUT = (
    "Не успел за {minutes} минут — слишком много фраз для озвучки. Попробуйте таблицу поменьше."
)
ERR_BUILD_FAILED = "Не получилось собрать колоду. Подробности в логе бота."
ERR_EXPIRED = "Таблица устарела — прошло больше {minutes} минут. Пришлите её снова."
ERR_SEND_FAILED = "Колоду собрал, но отправить файл не удалось. Пришлите таблицу ещё раз."
ERR_UNKNOWN_BUTTON = "Эта кнопка уже не действует. Пришлите таблицу снова."

# --- склонения ---------------------------------------------------------------


def plural(n: int, one: str, few: str, many: str) -> str:
    """«1 запись», «2 записи», «5 записей» — по правилам русского."""
    n_abs = abs(n)
    if n_abs % 10 == 1 and n_abs % 100 != 11:
        form = one
    elif 2 <= n_abs % 10 <= 4 and not 12 <= n_abs % 100 <= 14:
        form = few
    else:
        form = many
    return f"{n} {form}"


def notes_word(n: int) -> str:
    return plural(n, "запись", "записи", "записей")


def cards_word(n: int) -> str:
    return plural(n, "карточка", "карточки", "карточек")


def subdecks_word(n: int) -> str:
    return plural(n, "подколода", "подколоды", "подколод")


def files_word(n: int) -> str:
    return plural(n, "аудиофайл", "аудиофайла", "аудиофайлов")


# --- сборка текстов ----------------------------------------------------------


def lang_name(code: str) -> str:
    return LANG_NAMES.get(code, code)


def pair_label(lang_q: str, lang_a: str) -> str:
    return f"{lang_name(lang_q)} → {lang_name(lang_a)}"


def note_type_button(label: str) -> str:
    """Подпись кнопки Типа записи: пояснение в скобках — со следующей строки.

    «Простая (с вводом ответа в обе стороны)» в одну строку на телефон не влезает,
    и Telegram обрезает её посередине. Перенос в подписи кнопки разрешён, так что
    ставим его сами. В остальных текстах label остаётся однострочным.
    """
    return label.replace(" (", "\n(", 1)


def theme_name(theme: Theme) -> str:
    return THEME_CARD if theme is Theme.CARD else THEME_BOOK


def theme_button(theme: Theme) -> str:
    return BTN_THEME_CARD if theme is Theme.CARD else BTN_THEME_BOOK


def audio_description(settings: DeckSettings) -> str:
    """Языки и озвучка словами: «English → Русский, озвучен English»."""
    pair = pair_label(settings.lang_q, settings.lang_a)
    if settings.audio is AudioSide.NONE:
        return f"{pair}, без озвучки"
    if settings.audio is AudioSide.BOTH:
        return f"{pair}, озвучены обе стороны"
    voiced = settings.lang_q if settings.audio is AudioSide.QUESTION else settings.lang_a
    return f"{pair}, озвучен {lang_name(voiced)}"


def settings_description(settings: DeckSettings) -> str:
    """Короткое описание Настроек для кнопки «Как в прошлый раз»."""
    return f"{audio_description(settings)} · {theme_name(settings.theme)}"


def problem_reason(problem: Problem) -> str:
    if problem is Problem.EMPTY_QUESTION:
        return PROBLEM_EMPTY_QUESTION
    if problem is Problem.EMPTY_ANSWER:
        return PROBLEM_EMPTY_ANSWER
    return PROBLEM_NO_SEPARATOR


def sheet_suffix(sheet: str | None) -> str:
    return PROBLEM_SHEET.format(sheet=sheet) if sheet else ""


def problem_lines(problems: list[ProblemRow], *, limit: int = 10) -> str:
    lines = [
        PROBLEM_LINE.format(
            number=p.row.number, sheet=sheet_suffix(p.row.sheet), reason=problem_reason(p.problem)
        )
        for p in problems[:limit]
    ]
    if len(problems) > limit:
        lines.append(PROBLEM_MORE.format(count=len(problems) - limit))
    return "\n".join(lines)


def fix_prompt(problem: ProblemRow) -> str:
    row = problem.row
    if problem.problem is Problem.NO_SEPARATOR:
        return FIX_PROMPT_SEPARATOR.format(number=row.number, line=_short(row.question))
    if problem.problem is Problem.EMPTY_QUESTION:
        return FIX_PROMPT_QUESTION.format(
            number=row.number, sheet=sheet_suffix(row.sheet), answer=_short(row.answer)
        )
    return FIX_PROMPT_ANSWER.format(
        number=row.number, sheet=sheet_suffix(row.sheet), question=_short(row.question)
    )


def _short(text: str, limit: int = 80) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def summary(
    *,
    deck_name: str,
    sheets: int,
    notes: int,
    problems: list[ProblemRow],
    duplicates: int,
    empty_sheets: list[str],
) -> str:
    """Сводка после разбора: что увидели и что предстоит решить."""
    facts = []
    if sheets > 1:
        facts.append(SUMMARY_SHEETS.format(count=sheets))
    facts.append(SUMMARY_NOTES.format(count=notes))
    if problems:
        facts.append(SUMMARY_PROBLEMS.format(count=len(problems)))
    lines = [SUMMARY_TITLE.format(deck=deck_name), SUMMARY_SEPARATOR.join(facts)]
    if duplicates:
        lines.append(SUMMARY_DUPLICATES.format(count=duplicates))
    if empty_sheets:
        lines.append(SUMMARY_EMPTY_SHEETS.format(names=", ".join(f"«{n}»" for n in empty_sheets)))
    if problems:
        lines.append("")
        lines.append(PROBLEM_HEADER)
        lines.append(problem_lines(problems))
        lines.append("")
        lines.append(PROBLEM_QUESTION)
    return "\n".join(lines)


def verdict(result: Summary) -> str:
    parts = []
    if len(result.subdecks) > 1:
        parts.append(subdecks_word(len(result.subdecks)))
    parts.append(notes_word(result.notes))
    parts.append(cards_word(result.cards))
    if result.media_files:
        parts.append(files_word(result.media_files))
    if result.skipped:
        parts.append(VERDICT_SKIPPED.format(count=result.skipped))
    if result.duplicates:
        parts.append(VERDICT_DUPLICATES.format(count=result.duplicates))
    return VERDICT.format(deck=result.deck_name, parts=", ".join(parts)) + VERDICT_IMPORT_HINT


def help_message(example_url: str | None) -> str:
    """HELP с примером таблицы, если он настроен. URL — единственная подстановка в HTML."""
    example = HELP_EXAMPLE.format(url=html.escape(example_url, quote=True)) if example_url else ""
    return HELP.format(example=example)


def human_size(size_bytes: int) -> str:
    megabytes = size_bytes / 1024 / 1024
    if megabytes >= 1:
        return f"{megabytes:.1f} MB"
    return f"{size_bytes / 1024:.0f} KB"
