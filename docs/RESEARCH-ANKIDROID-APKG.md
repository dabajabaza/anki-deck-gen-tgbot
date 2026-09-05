# Открытие .apkg из Telegram на Android

Дата исследования: 2026-09-05. Исследование по первичным источникам, без изменения кода бота и без запуска на телефоне. Исходный [handoff в Obsidian](obsidian://open?vault=Obsidian%20Vault&file=Troubleshooting%2FAnkiDroid%20%D0%BD%D0%B5%20%D0%BE%D1%82%D0%BA%D1%80%D1%8B%D0%B2%D0%B0%D0%B5%D1%82%20.apkg%20%D0%B8%D0%B7%20%D1%87%D0%B0%D1%82%D0%B0%20Telegram). Пользователь описывает версии приложений как «самые свежие»; точные номера и канал установки телефона неизвестны.

## Вывод и рабочий обход

Наиболее вероятная причина — бинарный пакет попадает в текстовый CSV-импортер AnkiDroid. В актуальных исходниках найдена вся цепочка, которая это допускает: Telegram при неизвестном MIME открывает документ с `text/plain`, AnkiDroid выбирает CSV по этому MIME раньше проверки имени файла, а CSV-backend читает файл как строку. Это согласуется с наблюдением из handoff: один и тот же файл не открывается из чата, но импортируется после сохранения. Сам Android Intent с телефона пока не снят, поэтому совпадение конкретного запуска с этой цепочкой остаётся выводом по симптомам и коду, а не измерением устройства. [Telegram openForView][telegram-open], [AnkiDroid getLaunchType][launch], [CSV metadata][csv-core].

Рабочий способ сейчас: сохранить документ из Telegram в локальную папку, открыть его через системные «Файлы»/«Мои файлы» и выбрать AnkiDroid. Этот путь уже подтверждён пользователем в handoff. Дополнительный путь для проверки: AnkiDroid → Импорт → пакет колоды `.apkg` → выбрать именно сохранённый локальный файл. Меню импорта использует системный выбор документов; оно не гарантирует обход ошибочного MIME, если снова выбрать источник, который сообщает текстовый тип. [Исходник выбора файла][picker], [обработчики импорта][import-entry], [повторная классификация ImportUtils][import-utils].

Предлагаемый текст подсказки пользователю бота: «Если AnkiDroid показывает ошибку UTF-8, сохраните файл на телефон и откройте его через приложение “Файлы”. Либо выберите сохранённый файл в AnkiDroid → Импорт → пакет колоды (.apkg)». Это предложение для последующей реализации; в этом исследовании подсказки бота не менялись.

## Что уже наблюдалось, а что подтверждено исходниками

Из handoff, без повторного воспроизведения в этой сессии:

- Ошибка экрана Import: `500: Failed to read 'data/user/0/com.ichi2.anki/cache/anki-template.apkg': stream did not contain valid UTF-8`.
- Тот же сохранённый файл импортируется из файловой системы; ASCII-переименование не помогло открытию из чата.
- В Anki Python 26.08.1 `import_anki_package` прошёл, а `get_csv_metadata` для того же APKG воспроизвёл ошибку.
- Пробы multipart `sendDocument` с `application/vnd.anki`, `application/octet-stream`, `application/zip` возвращали правильный `file_name`, но `mime_type: null`.

Эти сведения — локальные наблюдения предыдущей сессии, не результаты upstream issue. Ошибка чтения UTF-8 сама по себе не доказывает потерю кодировки имени: CSV API действительно читает содержимое целиком через `read_to_string(path)`, и бинарный APKG закономерно не является UTF-8-текстом. [Anki get_csv_metadata][csv-core].

### Решающий путь прямого открытия

1. `Telegram AndroidUtilities.openForView` берёт MIME из расширения Android, затем из метаданных сообщения; если тип пустой, задаёт `text/plain`. После ошибки запуска предусмотрен ещё один запуск с `text/plain`. [Код Telegram][telegram-open].
2. В AnkiDroid `IntentUtil.resolveMimeType()` предпочитает уже заданный `intent.type`; `IntentHandler.getLaunchType()` относит текстовые MIME, включая `text/plain`, к `TEXT_IMPORT`. Имя `.apkg` в этой развилке не проверяется. [resolveMimeType][mime-resolve], [getLaunchType][launch], [список MIME][text-mimes].
3. Ветка `TEXT_IMPORT` сразу вызывает `onSelectedCsvForImport`, минуя `ImportUtils.handleContentProviderFile`. Файл копируется в кэш, открывается `CsvImporter`; его страница `import-csv` вызывает `getCsvMetadata`. Backend читает бинарный пакет как текст. [Запуск TEXT_IMPORT][launch-dispatch], [копирование и переход][import-entry], [CsvImporter][csv-ui], [вызов frontend][csv-page], [чтение backend][csv-core].

Есть и второй независимый путь ошибочной классификации: в `ImportUtils.handleContentProviderFile` проверка текстового MIME предшествует `isValidPackageName(filename)`. Здесь используется **`ContentResolver.getType(uri)`**, а не `intent.type`. Стандартный AndroidX FileProvider определяет тип по расширению и использует `application/octet-stream` при неизвестном типе; поэтому MIME Intent и MIME provider могут различаться. `application/octet-stream` не входит в текстовый список AnkiDroid. Нельзя объяснять прямой тап только функцией ImportUtils или считать, что Telegram FileProvider обязательно возвращает `text/plain`. [ImportUtils][import-utils], [AndroidX FileProvider][fileprovider], [Telegram manifest][telegram-provider].

Manifest AnkiDroid принимает `.apkg` и несколько MIME Anki/данных, а также `text/plain`. Проблема рассматриваемого случая возникает после выбора приложения, при выборе импортера. [Manifest AnkiDroid][manifest].

## Есть ли версия с исправлением

На дату проверки опубликованы стабильная [2.24.1 от 2026-08-31][stable] и предварительная [2.25.0alpha4 от 2026-09-03][alpha]. В проверенных исходниках актуального main и alpha4 сохраняется ранний выбор `TEXT_IMPORT`; в стабильной 2.24.1 и alpha4 сохраняется и текстовая ветка ImportUtils перед проверкой имени. Подтверждённой версии, исправляющей рассматриваемый путь, не найдено; обновление до «последней» нельзя обещать как решение. [main IntentHandler][launch], [alpha4 IntentHandler][alpha-launch], [2.24.1 ImportUtils][stable-utils], [alpha4 ImportUtils][alpha-utils].

Близкий [issue #21430][issue] открыт, помечен Needs Author Reply/Needs Triage, связанного PR или milestone нет. Автор сообщил AnkiDroid 2.24.0 / Android 16 и ошибку UTF-8 даже при выборе через меню. Единственный доступный комментарий сопровождающего просит пример файла и сведения о предыдущих версиях. Это похожий симптом, а не подтверждение нашей причины или доказательство специфического бага Android 16. [Комментарий сопровождающего][issue-comment].

Связанные изменения не следует выдавать за исправление этого случая: [PR #17867][pr-csv] добавлял MIME CSV/TSV, [PR #17874][pr-txt] — поддержку передачи TXT; свежие [санитизация имени][sanitize-fix] и [сохранение URI-encoded cache path][uri-fix] решают другие задачи. В текущем коде после них MIME-маршрутизация остаётся прежней.

Для защиты от устаревшего веб-кэша проверены исходники по фиксированным коммитам через GitHub API/raw. AnkiDroid main: `887495541f910355d0e4109b8410c9c1d3d21f19` (2026-09-04 23:14 UTC), Anki main: `5edc31694f07487266bb8c4725508f6c5f5c198d` (2026-09-04). Эти версии исходников не приравниваются к установленным версиям телефона.

## Что можно исправить со стороны бота

Повторная смена multipart Content-Type в `sendDocument` не выглядит полезным следующим шагом: документированный метод не имеет отдельного параметра MIME; реализация Bot API передаёт путь временного файла, а затем TDLib `inputMessageDocument`/`inputDocument`, без multipart MIME. TDLib вычисляет MIME документа по расширению имени. Поэтому наблюдение `mime_type: null` согласуется с кодом и не доказывает порчу APKG. [Bot API sendDocument][bot-docs], [Client.get_input_file][bot-file], [Client.process_send_document_query][bot-send], [TDLib MIME][td-mime].

Фраза из handoff «Telegram вообще не хранит MIME / ботом никак невозможно» слишком категорична. В MTProto у `inputMediaUploadedDocument` явно есть `mime_type`, и Telegram Android может использовать MIME сообщения. Но переход на MTProto, повторное использование корректно типизированного server-side документа или альтернативная доставка требуют отдельной проверки на телефоне; это не подтверждённые исправления текущего Bot API сценария. Наличие `file_id` само по себе не меняет уже сохранённые метаданные документа. [MTProto uploaded document][mtproto], [Telegram MIME fallback][telegram-open], [Bot API sendDocument][bot-docs].

Наименьшее изменение продукта — добавить описанную выше инструкцию сохранения. Если нужен другой канал доставки, можно отдельно испытать скачивание через браузер с сохранением имени `.apkg`; пока это непроверенная альтернатива. Менять внутренний формат колоды, кодировку карточек или переводить APKG в текст оснований нет: в handoff package-импорт того же файла уже проходит.

В репозитории [CLAUDE.md](../CLAUDE.md) и [ARCHITECTURE.md, A16](ARCHITECTURE.md#a16-имена-файлов--только-ascii-метки-и-имя-колоды--нет) ошибочно объясняют UTF-8-сбой потерей кодировки имени. Следующим отдельным изменением нужно исправить это обоснование: ASCII-переименование не устраняет MIME-маршрутизацию. Из этого не следует необходимость удалять существующую транслитерацию или менять имена кэша; такие изменения не входят в исследование.

## Устойчивое исправление upstream

Предлагаемая правка AnkiDroid, ещё не реализованная и не опубликованная:

1. Устранить ранний выбор CSV для URI файла в `IntentHandler.getLaunchType`. Сохранить отдельную обработку обычного текста `EXTRA_TEXT` без файла. Файлы с известным именем `.apkg`/`.colpkg` должны попадать в пакетный импорт даже при текстовом MIME. Имя нужно получать через `OpenableColumns.DISPLAY_NAME`, с подходящим fallback, поскольку URI провайдера может не содержать расширение. Альтернатива реализации — направить файловые Intent в общий классификатор, который уже имеет Context и доступ к provider. Одна перестановка условий в ImportUtils не исправит прямой тап, пока этот ранний TEXT_IMPORT остаётся. Основание предложения: [обход ImportUtils][launch-dispatch], [классификация Intent][launch].
2. В `ImportUtils.handleContentProviderFile` дать распознанному имени пакета приоритет над текстовым MIME, сохранив текущие проверки безопасного имени/пути и обычный импорт CSV/TSV/TXT. Это прикроет второй вход, включая выбор через меню. Не достаточно проверять `intent.type`: здесь отдельно используется MIME provider. Основание предложения: [существующий код][import-utils].
3. Проверять содержимое пакета пакетным backend. Расширение определяет выбор обработчика, но не делает произвольный ZIP корректным Anki-пакетом. Если понадобится распознавание файлов без имени, различать структуру APKG и произвольный ZIP; одного заголовка `PK` недостаточно. Это рекомендация по дизайну исправления, а не описание уже слитого upstream решения.

Альтернативный upstream fix Telegram — использовать `application/octet-stream` вместо `text/plain` для неизвестного бинарного документа, включая повторный запуск после исключения. Это исправляет соответствующий источник неверного Intent MIME; защита в AnkiDroid всё равно нужна для других отправителей. Основание предложения: [оба fallback Telegram][telegram-open], [поддерживаемые типы AnkiDroid][manifest].

## Минимальная матрица проверки

В каждом запуске сохранять точные версии Telegram/AnkiDroid/Android, действие Intent, `intent.type`, URI authority, `DISPLAY_NAME`, `ContentResolver.getType(uri)`, выбранный `LaunchType` и результат. Для реальных файлов сравнить SHA-256 оригинала и сохранённой копии. Не публиковать персональные карточки/полный URI; для upstream воспроизводителя достаточно маленькой обезличенной колоды. Матрица ниже — план, не отчёт о выполненных тестах.

| Вход | Имя / данные | MIME Intent / provider | Ожидаемый результат после правки |
|---|---|---|---|
| Тап по документу Telegram | Валидный `deck.apkg` | `text/plain` / `application/octet-stream` | Пакетный импорт; основной регрессионный тест IntentHandler |
| Файловый Intent или меню | Валидный `deck.apkg` | любой / `text/plain` | Пакетный импорт; отдельный тест ImportUtils |
| Файловый Intent | Валидный `deck.apkg` | `application/vnd.anki`, `application/octet-stream` или null | Пакетный импорт, обычные случаи не ломаются |
| Intent с непрозрачным URI | DISPLAY_NAME=`deck.apkg`, URI без расширения | `text/plain` | Пакетный импорт по имени provider |
| Контроль имён | Та же колода: ASCII, кириллица, `.APKG` | Те же значения MIME | Одинаковый выбор импортера |
| Контроль collection | Валидный `.colpkg` / `collection.apkg` | `text/plain` | Существующее подтверждение замены коллекции, не CSV |
| Контроль текста | Валидный CSV/TSV/TXT | Соответствующий текстовый MIME | Текстовый импорт сохраняется |
| Обычная передача текста | EXTRA_TEXT, без URI/EXTRA_STREAM | `text/plain` | Существующее создание заметки, не пакетный импорт |
| Повреждённый пакет | Произвольный ZIP с именем `.apkg` | `text/plain` | Ошибка пакетного формата; никаких попыток читать как CSV |
| Телефон, контроль обхода | Один APKG из чата и локальной папки | Зафиксировать реальные значения | Локальный импорт проходит; после правки проходит и тап из чата |

Для окончательного диагноза телефона нужен прежде всего первый реальный Intent и точная версия AnkiDroid. Самый полезный upstream reproducer: валидный небольшой APKG, DISPLAY_NAME с `.apkg`, `ACTION_VIEW` и `type=text/plain`. Успех package-импорта плюс вызов CSV при таком Intent отделяет ошибку маршрутизации от проблемы архива.

[telegram-open]: https://github.com/DrKLO/Telegram/blob/62b56a07ca7e30e39f7fd00a6728d6bbd716ca1c/TMessagesProj/src/main/java/org/telegram/messenger/AndroidUtilities.java#L4271-L4319
[telegram-provider]: https://github.com/DrKLO/Telegram/blob/62b56a07ca7e30e39f7fd00a6728d6bbd716ca1c/TMessagesProj/src/main/AndroidManifest.xml#L598-L606
[launch]: https://github.com/ankidroid/Anki-Android/blob/887495541f910355d0e4109b8410c9c1d3d21f19/AnkiDroid/src/main/java/com/ichi2/anki/IntentHandler.kt#L396-L408
[launch-dispatch]: https://github.com/ankidroid/Anki-Android/blob/887495541f910355d0e4109b8410c9c1d3d21f19/AnkiDroid/src/main/java/com/ichi2/anki/IntentHandler.kt#L80-L89
[mime-resolve]: https://github.com/ankidroid/Anki-Android/blob/887495541f910355d0e4109b8410c9c1d3d21f19/AnkiDroid/src/main/java/com/ichi2/utils/IntentUtil.kt#L89-L95
[text-mimes]: https://github.com/ankidroid/Anki-Android/blob/887495541f910355d0e4109b8410c9c1d3d21f19/AnkiDroid/src/main/java/com/ichi2/anki/utils/MimeTypeUtils.kt#L20-L27
[import-utils]: https://github.com/ankidroid/Anki-Android/blob/887495541f910355d0e4109b8410c9c1d3d21f19/AnkiDroid/src/main/java/com/ichi2/utils/ImportUtils.kt
[import-entry]: https://github.com/ankidroid/Anki-Android/blob/887495541f910355d0e4109b8410c9c1d3d21f19/AnkiDroid/src/main/java/com/ichi2/anki/Import.kt#L42-L66
[picker]: https://github.com/ankidroid/Anki-Android/blob/887495541f910355d0e4109b8410c9c1d3d21f19/AnkiDroid/src/main/java/com/ichi2/anki/dialogs/ImportFileSelectionFragment.kt#L129-L169
[csv-ui]: https://github.com/ankidroid/Anki-Android/blob/887495541f910355d0e4109b8410c9c1d3d21f19/AnkiDroid/src/main/java/com/ichi2/anki/pages/CsvImporter.kt
[csv-page]: https://github.com/ankitects/anki/blob/5edc31694f07487266bb8c4725508f6c5f5c198d/ts/routes/import-csv/%5B...path%5D/%2Bpage.ts#L8-L18
[csv-core]: https://github.com/ankitects/anki/blob/5edc31694f07487266bb8c4725508f6c5f5c198d/rslib/src/import_export/text/csv/metadata.rs#L40-L56
[fileprovider]: https://cs.android.com/androidx/platform/frameworks/support/+/androidx-main:core/core/src/main/java/androidx/core/content/FileProvider.java
[manifest]: https://github.com/ankidroid/Anki-Android/blob/887495541f910355d0e4109b8410c9c1d3d21f19/AnkiDroid/src/main/AndroidManifest.xml#L253-L269
[stable]: https://github.com/ankidroid/Anki-Android/releases/tag/v2.24.1
[alpha]: https://github.com/ankidroid/Anki-Android/releases/tag/v2.25.0alpha4
[alpha-launch]: https://github.com/ankidroid/Anki-Android/blob/v2.25.0alpha4/AnkiDroid/src/main/java/com/ichi2/anki/IntentHandler.kt#L396-L408
[stable-utils]: https://github.com/ankidroid/Anki-Android/blob/v2.24.1/AnkiDroid/src/main/java/com/ichi2/utils/ImportUtils.kt#L232-L235
[alpha-utils]: https://github.com/ankidroid/Anki-Android/blob/v2.25.0alpha4/AnkiDroid/src/main/java/com/ichi2/utils/ImportUtils.kt#L237-L240
[issue]: https://github.com/ankidroid/Anki-Android/issues/21430
[issue-comment]: https://github.com/ankidroid/Anki-Android/issues/21430#issuecomment-5227358259
[pr-csv]: https://github.com/ankidroid/Anki-Android/pull/17867
[pr-txt]: https://github.com/ankidroid/Anki-Android/pull/17874
[sanitize-fix]: https://github.com/ankidroid/Anki-Android/commit/5bb5a826a878470ea521fb6195e783ff85058692
[uri-fix]: https://github.com/ankidroid/Anki-Android/commit/25f6adfbfa21b77602db61584368ba3827e40d2e
[bot-docs]: https://core.telegram.org/bots/api#senddocument
[bot-file]: https://github.com/tdlib/telegram-bot-api/blob/e3e9dd8e5b3d7ab8537cd5a10dc31d5ffa8f82d1/telegram-bot-api/Client.cpp#L10796-L10799
[bot-send]: https://github.com/tdlib/telegram-bot-api/blob/e3e9dd8e5b3d7ab8537cd5a10dc31d5ffa8f82d1/telegram-bot-api/Client.cpp#L14057-L14070
[td-mime]: https://github.com/tdlib/td/blob/d1085f9cebc5a62379991ae1652673954f229c1f/td/telegram/MessageContent.cpp#L4765-L4780
[mtproto]: https://core.telegram.org/constructor/inputMediaUploadedDocument
