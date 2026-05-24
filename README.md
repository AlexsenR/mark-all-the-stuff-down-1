# mark-all-the-stuff-down

Лёгкий конвертер офисных документов и изображений в Markdown — скилл для AI-агентов (Claude Code, Codex CLI, pi.dev, Claude.ai).

## Зачем

Чтобы агент не сжирал 200 КБ договора целиком в контекст: документ конвертируется в Markdown один раз, дальше агент читает фрагментами через `Read offset/limit` или `grep`.

## Поддерживаемые форматы

DOCX, PDF, XLSX, XLS, PPTX, RTF, HTML, EPUB, PNG, JPG, JPEG, TIFF, TIF, BMP, WEBP. Лимит 50 МБ.

## OCR

Сканированные PDF и изображения конвертируются локально через `tesseract` с языками `rus+eng`. Файлы `tessdata/rus.traineddata`, `tessdata/eng.traineddata` и `tessdata/osd.traineddata` поставляются вместе со скиллом, поэтому системный `tessdata` не нужен. Для `.webp` используется runtime fallback через Pillow; если Pillow отсутствует, конвертация `.webp` завершается понятной ошибкой `ERROR install-failed`.

## Требования

- Python 3.10, 3.11 или 3.12.
- `tesseract` на `PATH` для OCR.
- `pdftoppm` для OCR сканированных PDF.
- macOS/Linux: `uv` рекомендуется; установщик поставит его при необходимости.
- Windows: достаточно Python и `pip`.

## Установка

**macOS / Linux:**
```sh
curl -LsSf https://raw.githubusercontent.com/strigov/mark-all-the-shit-down/main/install.sh | sh
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/strigov/mark-all-the-shit-down/main/install.ps1 | iex
```

Установщик кладёт в каталог скилла только runtime-файлы (`SKILL.md`, `convert.py`, `ocr.py`, `README.md`, `LICENSE`, `tessdata/`). Тесты, fixtures и dev-файлы остаются только в репозитории.

**Claude.ai (UI):** скачать последний `mark-all-the-stuff-down-vX.Y.Z.skill` из [Releases](https://github.com/strigov/mark-all-the-shit-down/releases) и загрузить в Settings -> Capabilities -> Skills.

## Использование

Агент вызывает скрипт автоматически, когда вы прикладываете документ. Вручную:
```sh
python convert.py file.docx
# -> /абсолютный/путь/file.md (47.3 KB)
```

Несколько файлов можно передать за один запуск; они конвертируются параллельно:
```sh
python convert.py --jobs 4 file1.docx file2.pdf file3.xlsx
```

Для сканированных PDF и изображений OCR может идти дольше дефолтного таймаута
командного инструмента агента. Если инструмент поддерживает timeout, ставьте
минимум 300000 мс; если нет — запускайте тяжёлые OCR-файлы последовательно:
```sh
python convert.py --jobs 1 scan1.pdf scan2.pdf
```

Скрипт создаёт Markdown рядом с исходными файлами и печатает одну строку на каждый успешный файл:
`<путь-к-markdown> (<размер>)`.

## Переменные окружения

| Переменная | Значение |
|---|---|
| `MTSD_LOG=1` | включает JSON-логи метаданных в `~/.cache/mtsd/log.jsonl` (macOS/Linux) или `%LOCALAPPDATA%\mtsd\log.jsonl` (Windows) |
| `MTSD_LOG_VERBOSE=1` | добавляет в лог полный путь (требует `MTSD_LOG=1`) |
| `MTSD_FORCE_PREINSTALLED=1` | имитирует sandbox без uv и сети (для CI) |

## Известные ошибки

| stderr | Что делать |
|---|---|
| `WARN ocr-low-confidence` | OCR завершился, но медианная уверенность ниже 60%; проверьте Markdown перед использованием |
| `ERROR ocr-failed` | Не найден/упал `tesseract` или `pdftoppm`, либо отсутствует bundled `tessdata/`; проверьте установку |
| `ERROR install-failed: webp requires Pillow` | Для `.webp` нет Pillow; установите Pillow или используйте другой формат изображения |
| `ERROR too-large` | Лимит 50 МБ; разделите файл |
| `ERROR install-failed: <format>` | Нет интернета и формат не в pre-installed bundle; запустите `install.sh` ещё раз |
| `ERROR protected` | Защищённый файл; попросите копию без защиты |
| `ERROR unsupported: .doc legacy` | Пересохраните в `.docx` |

## Лицензия

AGPL-3.0
