"""Вставленный текст: строка = запись, номера как в окне ввода, детектор осторожный."""

from anki_deck_gen.tables.parse import NO_SEPARATOR_MARK, looks_like_text_table, parse_text


def test_slash_and_tab_separators_split_once() -> None:
    table = parse_text("How are you? / Как дела?\nBye / Пока\nTab\tТаб")
    assert [(r.question, r.answer) for r in table.rows] == [
        ("How are you?", "Как дела?"),
        ("Bye", "Пока"),
        ("Tab", "Таб"),
    ]


def test_only_the_first_separator_splits() -> None:
    table = parse_text("a / b / c\nx / y")
    assert table.rows[0].answer == "b / c"


def test_a_dash_is_no_longer_a_separator_so_phrases_keep_theirs() -> None:
    """Тире живёт внутри фраз, поэтому разделителем быть перестало."""
    table = parse_text("Москва — столица России / Moscow is the capital")
    assert table.rows[0].question == "Москва — столица России"
    assert table.rows[0].answer == "Moscow is the capital"


def test_a_slash_without_spaces_is_not_a_separator() -> None:
    table = parse_text("120 км/ч / 120 km/h")
    assert table.rows[0].question == "120 км/ч"
    assert table.rows[0].answer == "120 km/h"


def test_line_numbers_count_blank_lines_like_an_editor() -> None:
    table = parse_text("a / b\n\n\nc / d")
    assert [row.number for row in table.rows] == [1, 4]


def test_a_line_without_separator_is_marked_not_dropped() -> None:
    table = parse_text("a / b\njust words here")
    marked = table.rows[1]
    assert marked.question == "just words here"
    assert marked.answer == ""
    assert marked.extra[NO_SEPARATOR_MARK] == "1"


def test_one_line_with_a_separator_is_already_a_table() -> None:
    """Слэш с пробелами в обычной фразе не встречается — одной строки достаточно."""
    assert looks_like_text_table("вопрос / ответ")
    assert looks_like_text_table("a / b\nc / d")


def test_prose_is_not_a_table() -> None:
    assert not looks_like_text_table("просто фраза без разделителя")
    assert not looks_like_text_table("hello - world"), "тире больше не разделитель"
    assert not looks_like_text_table("a / b\nno separator\nnor here"), "меньше половины строк"
    assert not looks_like_text_table("")
