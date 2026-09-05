# Opening a valid .apkg from Telegram, WhatsApp fails with a UTF-8 error; text/plain Intent selects CSV import

### Checked for duplicates?

- [ ] This issue is not a duplicate

Related: https://github.com/ankidroid/Anki-Android/issues/21430 reports the same UTF-8 error, but its steps use the import menu. This report provides a Telegram (WhatsApp)-specific reproduction and a source-code explanation for direct file opening. The underlying cause may overlap; please consolidate if appropriate.

### Does it also happen in the desktop version?

- [ ] This bug does not occur in the latest version of Anki Desktop

The file imports successfully on desktop. Separately, Anki's Python package `anki==26.08.1` successfully imports the same file with the package importer.

### What are the steps to reproduce this bug?

1. Receive a valid `.apkg` document from a Telegram (WhatsApp) for Android. The affected example is named `anki-template.apkg`.
2. Download the document inside Telegram (WhatsApp) and tap it directly in the chat. Choose AnkiDroid if Android asks which application to use.
3. In Telegram, AnkiDroid opens the Import screen and displays the error shown below. In WhatsApp, no error message is shown; the .apkg file is simply ignored when opened.
4. As a control, save that same document to local storage using Telegram's **Save to Downloads** action, then open the saved file through Android's file manager and select AnkiDroid. This import succeeds.

The failure was reproduced with both Cyrillic and ASCII filenames. Renaming the document to ASCII did not fix direct opening from Telegram.

### Expected behaviour

Expected: opening a valid `.apkg` from Telegram (WhatsApp) should launch package import and succeed, as opening the saved copy does. A generic or incorrect text MIME from the sending application should not override a recognized package filename.

Actual: direct opening fails with:

```text
500: Failed to read 'data/user/0/com.ichi2.anki/cache/anki-template.apkg': stream did not contain valid UTF-8
```

Workaround: save the document to local storage and open it from the file manager.

### Debug info

```text
AnkiDroid Version = 2.24.0 (ebcf8e0e34921628b9b8a496c66ffd4adbb3705f)  
Backend Version = 0.1.64-anki25.09.2 (25.09.2 3890e12c9e48c028c3f12aa58cb64bd9f8895e30)  
Android Version = 17 (SDK 37)  
ProductFlavor = play  
Device Info = Google | google | panther | panther | Pixel 7 | panther  
WebView Info = [com.google.android.webview | 792219903]: Mozilla/5.0 (Linux; Android 17; Pixel 7 Build/CP2A.260705.006; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/151.0.7922.199 Mobile Safari/537.36  
ACRA UUID = 35550205-d32e-46fa-985e-4ef3bc381504  
FSRS = 5.1.0 (Enabled: false)  
Crash Reports Enabled = true
Telegram Version = 12.10.1 (versionCode 70382)
Telegram installer = Google Play (com.android.vending)
WhatsApp Messenger Version = 2.26.33.76
WhatsApp Messenger Installer = Google Play (com.android.vending)
AnkiDroid installer = Google Play (com.android.vending)
```

### (Optional) Anything else you want to share?

> [!NOTE]
The same APKG successfully imports through `Collection.import_anki_package()` using `anki==26.08.1`. Passing that file to `Collection.get_csv_metadata()` instead reproduces `stream did not contain valid UTF-8`. This supports incorrect importer selection rather than an invalid package or a filename-encoding problem.

<details>
<summary>Source-code analysis and suggested fix</summary>

The direct-open path has an early MIME-based decision:

1. Telegram's [`AndroidUtilities.openForView`](https://github.com/DrKLO/Telegram/blob/62b56a07ca7e30e39f7fd00a6728d6bbd716ca1c/TMessagesProj/src/main/java/org/telegram/messenger/AndroidUtilities.java#L4271-L4319) uses `text/plain` when neither Android's extension lookup nor the document metadata provides a MIME type. It also retries with `text/plain` after a launch exception.
2. AnkiDroid's [`Intent.resolveMimeType()`](https://github.com/ankidroid/Anki-Android/blob/887495541f910355d0e4109b8410c9c1d3d21f19/AnkiDroid/src/main/java/com/ichi2/utils/IntentUtil.kt#L89-L95) prefers an explicit `intent.type`. [`IntentHandler.getLaunchType()`](https://github.com/ankidroid/Anki-Android/blob/887495541f910355d0e4109b8410c9c1d3d21f19/AnkiDroid/src/main/java/com/ichi2/anki/IntentHandler.kt#L396-L408) maps text MIME types to `TEXT_IMPORT` without checking whether the file is an APKG.
3. The [`TEXT_IMPORT` branch](https://github.com/ankidroid/Anki-Android/blob/887495541f910355d0e4109b8410c9c1d3d21f19/AnkiDroid/src/main/java/com/ichi2/anki/IntentHandler.kt#L80-L89) calls `onSelectedCsvForImport()` directly, bypassing the package-name checks in `ImportUtils`. Anki's [CSV metadata reader](https://github.com/ankitects/anki/blob/5edc31694f07487266bb8c4725508f6c5f5c198d/rslib/src/import_export/text/csv/metadata.rs#L40-L56) then reads the binary package as text.

This explains the observed symptom if Telegram supplied `type=text/plain`; the actual Intent still needs to be captured to confirm that condition on the affected phone. The same early routing is present in the inspected [2.25.0alpha4 source](https://github.com/ankidroid/Anki-Android/blob/v2.25.0alpha4/AnkiDroid/src/main/java/com/ichi2/anki/IntentHandler.kt#L396-L408). This is source inspection, not an on-device alpha test.

Suggested fix: for file-bearing Intents, recognize `.apkg`/`.colpkg` before selecting CSV from a text MIME. Resolve the filename through the content provider's `OpenableColumns.DISPLAY_NAME` when necessary; the URI itself may not contain an extension. Preserve the existing behavior for shared text without a file and for real CSV/TSV/TXT files.

There is also a separate text-MIME-before-package-name decision in [`ImportUtils.handleContentProviderFile`](https://github.com/ankidroid/Anki-Android/blob/887495541f910355d0e4109b8410c9c1d3d21f19/AnkiDroid/src/main/java/com/ichi2/utils/ImportUtils.kt). It uses `ContentResolver.getType(uri)`, which can differ from `intent.type`. Giving recognized package names priority there would cover the other import entry point, but changing **only** ImportUtils would leave the direct `TEXT_IMPORT` path above unchanged.

Suggested regression cases, not yet executed:

- A valid APKG with `ACTION_VIEW`, `intent.type=text/plain`, provider MIME `application/octet-stream`, and `DISPLAY_NAME=deck.apkg` selects package import.
- A valid APKG with provider MIME `text/plain` also selects package import through ImportUtils.
- A URI without an extension works when its display name ends in `.apkg`.
- Genuine CSV/TSV/TXT import and plain `EXTRA_TEXT` sharing retain their existing behavior.

</details>

### Research

- [ ] I have checked the [manual](https://docs.ankidroid.org/) and the [FAQ](https://github.com/ankidroid/Anki-Android/wiki/FAQ) and could not find a solution to my issue
- [ ] (Optional) I have confirmed the issue is not resolved in the latest alpha release ([instructions](https://docs.ankidroid.org/manual.html#betaTesting))

The manual and FAQ were consulted during the investigation. The [documented file-opening workflow](https://docs.ankidroid.org/manual.html#_open_the_file_using_android) and the local-file workaround do not resolve direct opening from Telegram (WhatsApp). Check the confirmations above after reviewing them; an alpha build has not been tested on the affected device.
