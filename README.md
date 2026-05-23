# mark-the-stuff-down

Лёгкий конвертер офисных документов в Markdown — скилл для AI-агентов (Claude Code, Codex CLI, pi.dev, Claude.ai).

## Зачем

Чтобы агент не сжирал 200 КБ договора целиком в контекст: документ конвертируется в Markdown один раз, дальше агент читает фрагментами через `Read offset/limit` или `grep`.

## Поддерживаемые форматы

DOCX, PDF (с текстовым слоем), XLSX, XLS, PPTX, RTF, HTML, EPUB. Лимит 50 МБ.

## Требования

- Python 3.10, 3.11 или 3.12.
- macOS/Linux: `uv` рекомендуется; установщик поставит его при необходимости.
- Windows: достаточно Python и `pip`.

## Установка

**macOS / Linux:**
```sh
curl -LsSf https://raw.githubusercontent.com/strigov/mark-the-shit-down/main/install.sh | sh
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/strigov/mark-the-shit-down/main/install.ps1 | iex
```

Установщик кладёт в каталог скилла только runtime-файлы (`SKILL.md`, `convert.py`, `README.md`, `LICENSE`). Тесты, fixtures и dev-файлы остаются только в репозитории.

**Claude.ai (UI):** скачать последний `mark-the-stuff-down-vX.Y.Z.skill` из [Releases](https://github.com/strigov/mark-the-shit-down/releases) и загрузить в Settings → Capabilities → Skills.

## Использование

Агент вызывает скрипт автоматически, когда вы прикладываете документ. Вручную:
```sh
python convert.py file.docx
# → /абсолютный/путь/file.md (47.3 KB)
```

Несколько файлов можно передать за один запуск; они конвертируются параллельно:
```sh
python convert.py --jobs 4 file1.docx file2.pdf file3.xlsx
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
| `ERROR scanned-pdf` | PDF без текстового слоя. Скилл намеренно не делает OCR/vision и не ставит tesseract — попросите отправителя дать текстовую версию или явно запустите отдельный OCR-пайплайн |
| `ERROR too-large` | Лимит 50 МБ; разделите файл |
| `ERROR install-failed: <format>` | Нет интернета и формат не в pre-installed bundle; запустите `install.sh` ещё раз |
| `ERROR protected` | Защищённый XLSX; попросите копию без защиты |
| `ERROR unsupported: .doc legacy` | Пересохраните в `.docx` |

## Лицензия

AGPL-3.0
