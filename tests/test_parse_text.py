"""Вставленный текст: строка = запись, номера как в окне ввода, детектор осторожный."""

from anki_deck_gen.tables.parse import NO_SEPARATOR_MARK, looks_like_text_table, parse_text


def test_dash_and_tab_separators_split_once() -> None:
    table = parse_text("How are you? — Как дела?\nBye - Пока\nOne – Один\nTab\tТаб")
    assert [(r.question, r.answer) for r in table.rows] == [
        ("How are you?", "Как дела?"),
        ("Bye", "Пока"),
        ("One", "Один"),
        ("Tab", "Таб"),
    ]


def test_only_the_first_separator_splits() -> None:
    table = parse_text("a — b — c\nx — y")
    assert table.rows[0].answer == "b — c"


def test_hyphen_inside_a_word_is_not_a_separator() -> None:
    table = parse_text("crow's-feet — гусиные лапки\nСанкт-Петербург — St. Petersburg")
    assert table.rows[0].question == "crow's-feet"
    assert table.rows[1].question == "Санкт-Петербург"


def test_line_numbers_count_blank_lines_like_an_editor() -> None:
    table = parse_text("a — b\n\n\nc — d")
    assert [row.number for row in table.rows] == [1, 4]


def test_a_line_without_separator_is_marked_not_dropped() -> None:
    table = parse_text("a — b\njust words here")
    marked = table.rows[1]
    assert marked.question == "just words here"
    assert marked.answer == ""
    assert marked.extra[NO_SEPARATOR_MARK] == "1"


def test_text_table_needs_two_lines_each_with_a_separator() -> None:
    assert looks_like_text_table("a — b\nc — d")
    assert not looks_like_text_table("a — b")
    assert not looks_like_text_table("a — b\nno separator here")
    assert not looks_like_text_table("hello - world")
