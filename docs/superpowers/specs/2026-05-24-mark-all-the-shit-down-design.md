# mark-all-the-shit-down — дизайн-спецификация

**Дата:** 2026-05-24
**Статус:** утверждено к реализации
**Версия скилла:** v0.1.0
**Базис:** форк `mark-the-shit-down` v0.1.1

---

## Обзор

`mark-all-the-shit-down` — форк скилла `mark-the-shit-down` (Python-скрипт для Claude Code, конвертирует офисные документы в Markdown). Форк добавляет OCR-поддержку:

- сканированные PDF (ранее завершались ошибкой `scanned-pdf`);
- изображения (`.png`, `.jpg`, `.jpeg`, `.tiff`, `.tif`, `.bmp`, `.webp`).

`.webp` поддерживается через runtime-fallback: если в окружении доступен Pillow (как правило — да, он предустановлен в большинстве sandbox'ов), `.webp` конвертируется в PNG **в памяти/во временном файле** перед вызовом tesseract. Это **не** требует root, apt, интернета или специально собранного `tesseract` с WebP. Если Pillow недоступен — ошибка `install-failed` с понятным сообщением.

OCR работает локально через предустановленный в Claude Cowork sandbox `tesseract` с языками `rus+eng`. Все три файла тренировочных данных (`rus`, `eng`, `osd`) поставляются в репозитории скилла — скилл self-contained и **не зависит** от системного `tessdata` вообще. Обоснование:

- `eng.traineddata` и `osd.traineddata` судя по одному наблюдаемому session log в Claude Cowork sandbox присутствуют в системе, но это **не задокументированная гарантия** — выборка из одной сессии, не контракт окружения.
- Структура файловой системы Cowork sandbox непрозрачна для скилла в рантайме: системные пути к `tessdata` варьируются между дистрибутивами и версиями (`/usr/share/tesseract-ocr/4.00/tessdata/`, `/usr/share/tesseract-ocr/5/tessdata/`, `/usr/local/share/tessdata/`, и т.д.). Probing этих путей в рантайме был бы хрупким и добавил бы сложности без выигрыша.
- Egress-прокси sandbox ненадёжен для скачивания недостающих файлов в рантайме.
- Поэтому: все три файла лежат в `tessdata/` репозитория, а `--tessdata-dir <skill-root>/tessdata` указывает **исключительно** на bundled-каталог. Никаких fallback'ов на системный `tessdata`, никаких symlink'ов на системные файлы.

## Цели

1. Снять ограничение «scanned-pdf — это ошибка»: сканы PDF должны конвертироваться в Markdown.
2. Поддержать конвертацию изображений в Markdown через OCR.
3. Сохранить полную обратную совместимость для всех уже поддерживаемых форматов и контракта CLI исходного скилла.
4. Не зависеть от сетевых ресурсов в рантайме (всё нужное — в репозитории или предустановлено в sandbox).

## Ограничения среды (Claude Cowork sandbox)

- `/usr/bin/tesseract` предустановлен. Состав системного `tessdata` (наличие/расположение `eng`, `osd`, `rus`) не является документированным контрактом окружения, поэтому скилл не полагается на него: все необходимые `*.traineddata` (`rus`, `eng`, `osd`) поставляются в репозитории скилла и используются через `--tessdata-dir <skill-root>/tessdata` (см. раздел про OCR выше).
- `pdftoppm` (poppler-utils) предустановлен.
- Нет root, нет sudo, нет apt-get.
- Egress-прокси блокирует GitHub и большинство внешних URL → pip/uvx ненадёжны для новых пакетов; OCR-стек не должен зависеть от сети.
- Максимальный размер входного файла: 50 MB (как в исходном скилле).

## Контракт CLI (без изменений)

- `python convert.py "<absolute-path>"` → `<output.md> (<size>)` в stdout, exit 0.
- При ошибке: `ERROR <type>: <reason>` в stderr, exit 1.
- Результат: `.md` рядом с источником, первая строка — cache-маркер.
- Формат маркера: `<!-- mark-all-the-shit-down v0.1.0 | source: X | source_id: Y | src_mtime: Z | mtime: W | backend: B -->`.

**Стиль заголовков страниц.** Для согласованности с существующим контрактом вывода (читается агентами, а не людьми) везде используется английский заголовок `## Page N` — как в исходном PDF-to-markdown пайплайне. Русский вариант `## Страница N` **не** используется.

## Архитектура

### 1. Структура репозитория

```
mark-all-the-shit-down/
├── convert.py          # форк оригинала (~1150 строк, ~30 строк диффа)
├── ocr.py              # новый модуль (~200 строк)
├── tessdata/
│   ├── rus.traineddata  # ~4 MB (fast)
│   ├── eng.traineddata  # ~4 MB (fast)
│   └── osd.traineddata  # ~10 MB (fast)
├── SKILL.md
├── README.md
├── install.sh
├── install.ps1
├── requirements-dev.txt
├── tests/
│   ├── conftest.py
│   ├── test_ocr.py
│   └── ... (все исходные тесты)
└── .github/
    └── workflows/ci.yml
```

**Диффы к `convert.py` относительно оригинала (полный список).**

В оригинале строка `"mark-the-stuff-down"` встречается в 4 местах (проверено `grep -n "mark-the-stuff-down" convert.py`):

| Стр. | Что | Было | Стало |
|---|---|---|---|
| 2 | docstring модуля | `"""mark-the-stuff-down - convert office docs to Markdown."""` | `"""mark-all-the-shit-down - convert office docs to Markdown (with OCR)."""` |
| 11 (рядом) | `__version__` | `"0.1.1"` | `"0.1.0"` (форк начинает свою нумерацию) |
| 23 | `MARKER_PREFIX` | `"<!-- mark-the-stuff-down v"` | `"<!-- mark-all-the-shit-down v"` |
| 147 | `marker_line()` — **хардкод, не читает `MARKER_PREFIX`** | `f"<!-- mark-the-stuff-down v{__version__} | "` | `f"{MARKER_PREFIX}{__version__} | "` (перевести на константу) |
| 1043 | CLI `--version` | `f"mark-the-stuff-down {__version__}"` | `f"mark-all-the-shit-down {__version__}"` |
| — | `SUPPORTED_EXTS` | — | расширен: `+{".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}` |
| ~604 | `dispatch()` | — | добавить ветку для изображений → `ocr.convert_image(src)` (включая `.webp` — см. `ocr.py`, runtime Pillow-fallback) |
| ~635 | Ветка scanned PDF | `raise ConversionError("scanned-pdf", ...)` | `ocr.convert_pdf_scanned(src, info.total_pages)` (см. п. 2 ниже) |
| — | Сообщения об ошибках / internal-error URL | любые упоминания `mark-the-stuff-down` | заменить на `mark-all-the-shit-down` |
| ~1095 | internal-error URL (старый repo slug) | `"github.com/strigov/mark-the-shit-down/issues"` | `"github.com/strigov/mark-all-the-shit-down/issues"` (NB: это **другой** литерал — repo slug, а не имя скилла; `mark-the-shit-down` ≠ `mark-the-stuff-down`) |
| top of file | импорт нового модуля `ocr` | — | Добавить новую секцию «local-module imports» после блока stdlib-импортов (в оригинале её нет). **Top-level импорт не используется**: чтобы избежать import-time side effects и упростить тестирование, в `_do_pdf` (ветка scanned PDF) и в image-ветке `dispatch()` ставится **локальный** `from ocr import convert_pdf_scanned, convert_image, OcrError` непосредственно перед вызовом. |

**Замечание по `_parse_marker_version()` (стр. 153)** и `is_up_to_date()` (стр. 165): они уже читают `MARKER_PREFIX` (см. `if not line.startswith(MARKER_PREFIX)`), поэтому отдельных правок **не требуют** — после изменения константы они автоматически корректно опознают новый маркер. Это в отличие от `marker_line()`, которая в оригинале хардкодит литерал и **требует** явной правки (см. строку таблицы выше).

**Grep-инварианты** после применения диффа (проверяются в тестах `test_marker_prefix`, `test_grep_no_old_name` + явный `grep`-шаг в CI):

1. `grep -n "mark-the-stuff-down\|0.1.1" convert.py` — должен возвращать пусто (старое имя скилла + старая версия).
2. `grep -n "mark-the-shit-down" convert.py` — должен возвращать пусто (старый repo slug; **не путать** с новым именем `mark-all-the-shit-down`, в котором `mark-the-shit-down` не является подстрокой). Применяется **только** к `convert.py`, так как в других файлах репо (документация, история коммитов, сравнение с upstream) законные упоминания старого репо допустимы.

Чтобы grep корректно отличал старый slug от нового имени, использовать `grep -E "(^|[^-])mark-the-shit-down"` или эквивалентный `\bmark-the-shit-down\b` — слово `mark-all-the-shit-down` не должно матчиться.

Весь прочий код `convert.py` не меняется.

### 2. OCR-пайплайн (`ocr.py`)

**Публичный интерфейс:**

```python
def convert_pdf_scanned(src: Path, total_pages: int) -> tuple[str, str]:
    """Возвращает (markdown_body, "tesseract-ocr").
    total_pages пробрасывается вызывающей стороной из уже выполненного pdf-probe."""

def convert_image(src: Path) -> tuple[str, str]:
    """Возвращает (markdown_body, "tesseract-ocr").
    Поддерживает .png/.jpg/.jpeg/.tiff/.tif/.bmp напрямую; .webp — через Pillow-fallback (см. ниже)."""
```

Возвращаемый `backend` идёт в cache-маркер. Для текстовых PDF поведение исходника сохраняется (`pdfplumber`/`pymupdf4llm`).

**Передача `total_pages`.** В `convert.py`, в `_do_pdf()`, к моменту классификации PDF как «сканированный» уже выполнен `_pdf_probe()` и доступен объект `info` с полем `info.total_pages`. Диспетчер передаёт его явно: `ocr.convert_pdf_scanned(src, info.total_pages)` — `ocr.py` не делает повторный probe.

**Пайплайн для сканированных PDF (постранично, по одной странице за раз):**

```
1. total_pages приходит аргументом от вызывающей стороны (см. интерфейс выше).
2. Для N = 1..total_pages:
     pdftoppm -f N -l N -r 300 -gray <input.pdf> <tmpdir>/page
        → ровно один файл <tmpdir>/page-NNN.pgm
        (важно: -gray даёт grayscale Netpbm с расширением .pgm, не .ppm)
     tesseract <tmpdir>/page-NNN.pgm stdout
               --tessdata-dir <skill>/tessdata
               -l rus+eng --psm 1 tsv
        → TSV stdout
     удалить <tmpdir>/page-NNN.pgm немедленно
     TSV → группировка по block/par/line → текст страницы N
     результат:
         ## Page N
         <!-- ocr page=N conf=87 words=412 -->
         <text>
```

- `tempfile.TemporaryDirectory` оборачивает весь цикл; внутри в любой момент времени существует **не более одного** PGM-файла.
- `pdftoppm` вызывается отдельно на каждую страницу с `-f N -l N` (рендерится только страница N), а не один раз на весь документ.
- Имя выходного файла подсчитывается реализацией как `page-<N с padding>.pgm` (padding по умолчанию pdftoppm — длина десятичного представления `total_pages`). Чтобы избежать угадывания паддинга, реализация после вызова `pdftoppm` ищет в `tmpdir` единственный файл по маске `page-*.pgm`.
- `tesseract` вызывается **ровно один раз** на страницу (режим `tsv`). Текст и confidence извлекаются из одной TSV.
- `--psm 1` — автосегментация страницы с OSD.
- Путь к тренировочным данным: `--tessdata-dir <path>/tessdata` (`<path>` — каталог скилла, определяется относительно `ocr.py`).
- Пиковое потребление диска ограничено **одной растеризованной страницей за раз**; абсолютное значение зависит от размера страницы и разрешения (300 DPI grayscale), конкретные «~2 MB» не гарантируются.

**Пайплайн для изображений:**

```
image.{png,jpg,...} → tesseract <file> stdout --tessdata-dir ./tessdata
                                          -l rus+eng --psm 1 tsv
                    → <!-- ocr conf=91 words=234 -->
                    → <text>            # без заголовка страницы
```

Заголовок `## Page N` для одиночных изображений не выставляется (заголовок есть только в многостраничном PDF-OCR).

**WebP fallback через Pillow (runtime-detected, без root и без интернета).**

`.webp` НЕ передаётся tesseract напрямую: даже там, где Leptonica собрана с WebP, поведение варьируется между сборками. Вместо этого `ocr.py` использует runtime-проверку Pillow:

```python
def _materialize_for_tesseract(src: Path, tmpdir: Path) -> Path:
    if src.suffix.lower() != ".webp":
        return src
    try:
        from PIL import Image  # runtime-import, не top-level
    except ImportError as e:
        raise ConversionError(
            "install-failed",
            "webp requires Pillow; not available in this environment"
        ) from e
    out = tmpdir / (src.stem + ".png")
    with Image.open(src) as im:
        im.convert("RGB").save(out, format="PNG")
    return out
```

- Pillow обычно предустановлен (входит в зависимости `markitdown[pdf]` и popular sandbox-образов).
- Конвертация идёт во временный файл внутри `tempfile.TemporaryDirectory`, рядом с тем же tmpdir, что используется для tesseract; PNG удаляется автоматически после выхода из контекста.
- Никаких `apt`, `convert`/ImageMagick, сетевых запросов, root-прав не требуется. Это чистый Python.
- Если Pillow отсутствует — `ConversionError("install-failed", ...)`, exit 1. Пользователь получает понятное сообщение, что нужно для `.webp`.

**Сборка текста из TSV:**

- Группировка слов по ключу `(page_num, block_num, par_num, line_num)`.
- Слова с `conf < 30` отбрасываются (шум).
- Внутри строки слова склеиваются через пробел; строки в параграфе — через `\n`; параграфы — через `\n\n`.
- Пустые строки/параграфы (после фильтрации) пропускаются.

**Сигналы качества:**

- На каждую страницу/изображение: HTML-комментарий с медианной confidence и числом слов.
- Медианная confidence вычисляется **после** фильтрации `conf < 30` — то есть только по словам, которые реально вошли в выводимый текст (а не по всем словам из исходного TSV). `words=` в HTML-комментарии — это количество тех же отфильтрованных слов. Если после фильтрации не осталось ни одного слова, confidence пишется как `conf=0` и `words=0`.
- Если медианная confidence страницы `< 60`: в stderr выводится строка `WARN ocr-low-confidence: page N conf=<value>` (для изображения — без `page N`). Это **не** прерывает конвертацию.
- В cache-маркере итогового `.md` поле `backend=tesseract-ocr` для OCR-результатов; текстовые PDF и прочие форматы сохраняют свои бэкенды.

**Контракт ошибок между `ocr.py` и `convert.py`.**

`ConversionError` определён в `convert.py`, который запускается как `__main__`. Прямой импорт `from convert import ConversionError` в `ocr.py` создал бы проблему идентичности класса (`convert.ConversionError` ≠ `__main__.ConversionError`), из-за чего `except ConversionError` в `main()` не поймал бы исключение, поднятое из `ocr.py`. Также это породило бы циклическую зависимость (`convert.py` импортирует `ocr`, `ocr` импортировал бы `convert`).

Решение — собственный класс ошибок в `ocr.py` и трансляция в точках вызова:

```python
# ocr.py — не импортирует ничего из convert.py
class OcrError(Exception):
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message
```

`ocr.py` поднимает `OcrError("install-failed", ...)` (Pillow отсутствует для `.webp`) и `OcrError("ocr-failed", ...)` (tesseract не найден / упал / `tessdata` недоступен). Никаких других kind'ов в v0.1.0 не используется.

В `convert.py`, в двух точках диспетчеризации (`_do_pdf` ветка scanned PDF, image-ветка `dispatch()`), `OcrError` оборачивается в `ConversionError` с сохранением `kind`/`message` и chained-причиной:

```python
# в _do_pdf, ветка scanned:
from ocr import convert_pdf_scanned, OcrError  # локальный импорт
try:
    body, backend = convert_pdf_scanned(src, info.total_pages)
except OcrError as e:
    raise ConversionError(e.kind, e.message) from e

# в image-ветке dispatch():
from ocr import convert_image, OcrError  # локальный импорт
try:
    body, backend = convert_image(src)
except OcrError as e:
    raise ConversionError(e.kind, e.message) from e
```

Это гарантирует, что `except ConversionError` в `main()` ловит исключение корректно (один и тот же класс из `__main__`), а `ocr.py` остаётся изолированным модулем без зависимостей от `convert.py`.

**NB:** в коде самого `ocr.py` (см. пример `_materialize_for_tesseract` выше) `raise ConversionError(...)` нужно заменить на `raise OcrError(...)` — это уже учтено в контракте и отражено в финальной реализации, в спецификации выше пример приведён в иллюстративном виде до введения `OcrError`.

### 3. Установка и упаковка (installer + skill bundle)

Существующие `install.sh` и `install.ps1` форка скопированы из оригинала и копируют только `convert.py`, `SKILL.md`, `README.md`, `LICENSE`, и при этом содержат хардкод имени **`mark-the-stuff-down`** в destination paths, symlink-целях, git clone URL и финальных сообщениях. Их нужно: (а) переименовать в новое имя скилла, (б) расширить копированием `ocr.py` и `tessdata/`.

**Переименование (`mark-the-stuff-down` → `mark-all-the-shit-down`).**

В `install.sh` (проверено `grep -n`):

| Стр. | Что | Действие |
|---|---|---|
| 40 | `DEST=$HOME/.local/share/mark-the-stuff-down` | переименовать каталог в `mark-all-the-shit-down` |
| 91 | `git clone ... https://github.com/strigov/mark-the-shit-down "$TMP_SOURCE"` | заменить URL на новый репозиторий: `https://github.com/strigov/mark-all-the-shit-down` |
| 129 | `target=$d/mark-the-stuff-down` | переименовать имя симлинка в `mark-all-the-shit-down` |
| 189 | `echo "mark-the-stuff-down installed"` | заменить на `mark-all-the-shit-down installed` |

В `install.ps1` (проверено `grep -n`):

| Стр. | Что | Действие |
|---|---|---|
| 23 | `$Dest = Join-Path $HOME ".local\share\mark-the-stuff-down"` | переименовать в `mark-all-the-shit-down` |
| 62 | `git clone ... https://github.com/strigov/mark-the-shit-down $tmpSource` | заменить URL на `https://github.com/strigov/mark-all-the-shit-down` |
| 99 | `$target = Join-Path $d "mark-the-stuff-down"` | переименовать симлинк-имя в `mark-all-the-shit-down` |
| 150 | `Write-Host "mark-the-stuff-down installed"` | заменить на `mark-all-the-shit-down installed` |

Переменные окружения `MTSD_*` (`MTSD_DRY_RUN`, `MTSD_SOURCE`, `MTSD_SKILL_TARGET`, `MTSD_SMOKE_OUT`) и временные префиксы (`mtsd-src-`, `mtsd-`) можно **оставить без изменений** в v0.1.0 — это внутренний контракт инсталлятора, не зависящий от пользовательских скриптов. Их переименование (например, в `MATSD_*`) — отдельная косметическая задача, не блокер для релиза.

Замечание: GitHub remote URL и имя репозитория `mark-all-the-shit-down` — это **новый репозиторий форка**, отдельный от `mark-the-shit-down`. Никакого rewrite истории/remote'ов на уже клонированной рабочей копии не требуется; правки выше — только в исходных текстах скриптов.

**Функциональные изменения (`install.sh`):**

- Добавить `ocr.py` в список `RUNTIME_FILES`.
- Скопировать каталог `tessdata/` целиком (`cp -R "$src/tessdata" "$DEST/tessdata"`) в директорию назначения скилла, рядом с `convert.py`. Перед копированием проверить существование `"$src/tessdata"`; иначе — fail.
- Пост-проверка: `[ -f "$DEST/ocr.py" ] && [ -f "$DEST/tessdata/rus.traineddata" ] && [ -f "$DEST/tessdata/eng.traineddata" ] && [ -f "$DEST/tessdata/osd.traineddata" ]`; иначе — fail с понятным сообщением.

**Функциональные изменения (`install.ps1`):**

- То же самое: добавить `ocr.py` в `$runtimeFiles`, рекурсивно скопировать `tessdata\` (`Copy-Item -Recurse "$src\tessdata" "$Dest\tessdata"`).
- Аналогичная пост-проверка существования файлов.

**Skill bundle (что попадает в архив для Claude Cowork / релиз):**

Бандл скилла **обязан** содержать:

- `convert.py`
- `ocr.py`
- `tessdata/rus.traineddata`
- `tessdata/eng.traineddata`
- `tessdata/osd.traineddata`
- `SKILL.md`, `README.md`, `LICENSE`

**CI-проверка целостности бандла (`.github/workflows/ci.yml`):**

Отдельный шаг (job или step) `verify-bundle`, который запускается на каждом PR и в релизном пайплайне. Проверка идёт **на собранном бандле** (staging-каталог или распакованный zip-артефакт), не на рабочем дереве — это ловит ошибки упаковки/`.gitignore`/`MANIFEST`, а не только наличие файлов в репо:

```bash
# 1) Собрать бандл (staging dir) ровно так, как делает release:
BUNDLE=$(mktemp -d)
RUNTIME_FILES="convert.py ocr.py SKILL.md README.md LICENSE"
for f in $RUNTIME_FILES; do cp "$f" "$BUNDLE/"; done
cp -R tessdata "$BUNDLE/tessdata"

# 2) Опционально упаковать в zip и распаковать в новый каталог:
( cd "$BUNDLE" && zip -r ../bundle.zip . ) && \
  unzip -q bundle.zip -d "$BUNDLE.unpacked"
CHECK_ROOT="$BUNDLE.unpacked"

# 3) Проверить наличие всех ожидаемых файлов В БАНДЛЕ:
for f in convert.py ocr.py SKILL.md README.md LICENSE \
         tessdata/rus.traineddata tessdata/eng.traineddata tessdata/osd.traineddata; do
  test -f "$CHECK_ROOT/$f" || { echo "MISSING IN BUNDLE: $f"; exit 1; }
done
```

Если какой-либо файл отсутствует в собранном бандле — CI падает. Это страхует от регрессии при правках installer-скриптов, `.gitignore`, либо логики упаковки релизного workflow.

**CI artifact / job naming.** Имя релизного артефакта — `mark-all-the-shit-down-v0.1.0.zip` (или `.tar.gz`). Job names в `ci.yml` — `mark-all-the-shit-down / test`, `mark-all-the-shit-down / verify-bundle`, и т.п. Любые упоминания `mark-the-stuff-down` в скопированном из оригинала `ci.yml` должны быть переименованы.

### 4. SKILL.md, обработка ошибок, тесты

**Изменения в `SKILL.md`:**

- `name`: `mark-all-the-shit-down`.
- `description`: упомянуть OCR (`rus+eng`) для сканированных PDF и изображений.
- `paths`: добавить `*.png`, `*.jpg`, `*.jpeg`, `*.tiff`, `*.tif`, `*.bmp`, `*.webp`.
- Новое правило: `WARN ocr-low-confidence` — медианная confidence < 60%; не прерывать, сообщить пользователю.
- Новое правило: `ERROR ocr-failed` — `tesseract` недоступен или `tessdata` не найдены; exit 1.
- Новое правило: `ERROR install-failed` для `.webp` без Pillow — сообщить пользователю, что для `.webp` нужен Pillow в окружении.
- Удалить правило: `ERROR scanned-pdf` (больше не ошибка).

**Тесты (`tests/test_ocr.py`):**

- `test_tsv_parsing` — юнит: фейковый TSV → проверить сборку текста и фильтрацию `conf < 30`.
- `test_confidence_aggregation` — юнит: расчёт медианной confidence.
- `test_convert_image_smoke` — интеграция (помечена `@pytest.mark.ocr`): если `tesseract` доступен локально, сконвертировать простой PNG с текстом, проверить непустой Markdown.
- `test_scanned_pdf_no_longer_errors` — проверить, что `ConversionError("scanned-pdf", ...)` больше не возбуждается.
- `test_marker_prefix` — проверить, что cache-маркер (через реальный вызов `marker_line()`) содержит `mark-all-the-shit-down` и **не** содержит `mark-the-stuff-down` ни в одной строке. Это покрывает п. строки 147 в convert.py (хардкод `marker_line()` — основной риск регрессии).
- `test_webp_pillow_fallback` — юнит/интеграция: если Pillow доступен, маленький `.webp` конвертируется без ошибки; если Pillow отсутствует (моки или фейк-import), возбуждается `ConversionError("install-failed", ...)`.
- `test_grep_no_old_name` — runtime-grep по содержимому `convert.py`: подстроки `mark-the-stuff-down` и `0.1.1` не встречаются (инвариант из секции «диффы»).

Интеграционные тесты, требующие реального `tesseract`, помечаются `@pytest.mark.ocr` и скипаются, если бинарь недоступен.

**CI (`.github/workflows/ci.yml`):**

- Шаг установки tesseract на Linux-runner'ах (под условием `if: runner.os == 'Linux'`): `sudo apt-get install -y tesseract-ocr tesseract-ocr-rus`. Если matrix включает macOS / Windows runner'ы, для них используется `brew install tesseract tesseract-lang` / `choco install tesseract` соответственно, либо `@pytest.mark.ocr` тесты пропускаются автоматически (по детекту бинаря).
- Запуск всех тестов, включая `@pytest.mark.ocr`, на Linux. На остальных платформах `ocr`-маркированные тесты могут скипаться, но юнит-тесты (`test_tsv_parsing`, `test_confidence_aggregation`, `test_marker_prefix`) обязаны проходить везде.

## Открытые вопросы

Нет. Все решения зафиксированы выше.

## Вне области (out of scope)

- Дополнительные языки OCR кроме `rus+eng` (можно добавить позднее — расширением `tessdata/`).
- Распознавание таблиц, формул и рукописного текста (Tesseract `tsv` не умеет; layout-структура за пределами абзацев не восстанавливается).
- Альтернативные OCR-движки (PaddleOCR, EasyOCR, облачные API).
- Изменение бэкендов для текстовых (не сканированных) PDF и других форматов.
- Параллелизация обработки страниц PDF (последовательная обработка, по одной странице).
- Предобработка изображений (deskew, denoise, бинаризация) — полагаемся на встроенные эвристики Tesseract.
- Изменение лимита 50 MB на входной файл.
- Поддержка `.webp` **в окружении без Pillow**. v0.1.0 поддерживает `.webp` через runtime-fallback на Pillow (PIL → PNG → tesseract); если Pillow в окружении нет — выдаётся `ERROR install-failed` с понятным сообщением. Альтернативные пути (например, сборка `tesseract` с WebP-поддержкой Leptonica, ImageMagick `convert`, или bundling Pillow в скилл) — вне области v0.1.0.
