#!/bin/sh
set -eu

LANG=en_US.UTF-8
LC_ALL=en_US.UTF-8
export LANG LC_ALL

NO_UV=0
ONLY=""
for arg in "$@"; do
  case "$arg" in
    --no-uv)
      NO_UV=1
      ;;
    --only=*)
      ONLY=${arg#--only=}
      ;;
    -h|--help)
      echo "Usage: install.sh [--no-uv] [--only=claude|codex|pi]"
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      echo "Usage: install.sh [--no-uv] [--only=claude|codex|pi]" >&2
      exit 2
      ;;
  esac
done

case "$ONLY" in
  ""|claude|codex|pi) ;;
  *)
    echo "Unknown --only value: $ONLY" >&2
    exit 2
    ;;
esac

DRY_RUN=${MTSD_DRY_RUN:-0}
SOURCE_DIR=${MTSD_SOURCE:-}
DEST=$HOME/.local/share/mark-the-stuff-down
RUNTIME_FILES="convert.py
SKILL.md
README.md
LICENSE"
TMP_SOURCE=""
TMPDIR_X=""

cleanup() {
  [ -z "$TMP_SOURCE" ] || rm -rf "$TMP_SOURCE"
  [ -z "$TMPDIR_X" ] || rm -rf "$TMPDIR_X"
}
trap cleanup EXIT HUP INT TERM

install_runtime_from_source() {
  src=$1
  rm -rf "$DEST"
  mkdir -p "$DEST"
  printf '%s\n' "$RUNTIME_FILES" | while IFS= read -r file; do
    [ -n "$file" ] || continue
    if [ ! -f "$src/$file" ]; then
      echo "ERROR: missing runtime file: $file" >&2
      exit 1
    fi
    cp "$src/$file" "$DEST/$file"
  done
}

if command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON=python
else
  echo "ERROR: Python 3.10+ is required" >&2
  exit 1
fi

if ! "$PYTHON" - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
then
  echo "ERROR: Python 3.10+ is required" >&2
  exit 1
fi

if [ -n "$SOURCE_DIR" ]; then
  install_runtime_from_source "$SOURCE_DIR"
else
  mkdir -p "$(dirname "$DEST")"
  TMP_SOURCE=$(mktemp -d)
  git clone --depth 1 https://github.com/strigov/mark-the-shit-down "$TMP_SOURCE"
  install_runtime_from_source "$TMP_SOURCE"
fi

CANDIDATES=""
append_candidate() {
  CANDIDATES=${CANDIDATES}${CANDIDATES:+'
'}$1
}

if [ -n "${MTSD_SKILL_TARGET:-}" ]; then
  append_candidate "$MTSD_SKILL_TARGET"
else
  if { [ -z "$ONLY" ] || [ "$ONLY" = "claude" ]; } && [ -d "$HOME/.claude/skills" ]; then
    append_candidate "$HOME/.claude/skills"
  fi
  if { [ -z "$ONLY" ] || [ "$ONLY" = "codex" ]; } && [ -d "$HOME/.agents/skills" ]; then
    append_candidate "$HOME/.agents/skills"
  fi
  if { [ -z "$ONLY" ] || [ "$ONLY" = "pi" ]; } && [ -d "$HOME/.config/pi/skills" ]; then
    append_candidate "$HOME/.config/pi/skills"
  fi
fi

if [ -z "$CANDIDATES" ]; then
  echo "No agent skill dir found. Create one of: ~/.claude/skills, ~/.agents/skills, ~/.config/pi/skills" >&2
  exit 1
fi

if [ "$NO_UV" -eq 0 ] && ! command -v uv >/dev/null 2>&1 && [ "$DRY_RUN" -eq 0 ]; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  PATH=$HOME/.local/bin:$HOME/.cargo/bin:$PATH
  export PATH
fi

printf '%s\n' "$CANDIDATES" | while IFS= read -r d; do
  [ -n "$d" ] || continue
  mkdir -p "$d"
  target=$d/mark-the-stuff-down
  if [ -L "$target" ] || [ -e "$target" ]; then
    rm -rf "$target"
  fi
  ln -s "$DEST" "$target"
  echo "Linked $target -> $DEST"
done

if [ "$DRY_RUN" -eq 0 ]; then
  if [ "$NO_UV" -eq 0 ] && command -v uv >/dev/null 2>&1; then
    if ! uv tool install markitdown \
      --with "markitdown[docx,xlsx,pdf,pptx,xls,rtf,html,epub]" \
      --with pymupdf4llm; then
      echo "ERROR: Failed to prewarm markitdown dependencies via uv. Run the installer again or check your internet connection." >&2
      exit 1
    fi
  else
    if ! "$PYTHON" -m pip install --user --quiet \
      "markitdown[docx,xlsx,pdf,pptx,xls,rtf,html,epub]" pymupdf4llm \
      pdfplumber pypdf python-docx openpyxl python-pptx beautifulsoup4; then
      echo "ERROR: Failed to prewarm pip dependencies. Run the installer again or check your internet connection." >&2
      exit 1
    fi
  fi

  "$PYTHON" "$DEST/convert.py" --version >/dev/null

  TMPDIR_X=$(mktemp -d)
  export TMPDIR_X
  "$PYTHON" - <<'PY'
import os
import zipfile

out = os.path.join(os.environ["TMPDIR_X"], "smoke.docx")
content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""
rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
doc = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:body><w:p><w:r><w:t>smoke</w:t></w:r></w:p></w:body></w:document>"""
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("[Content_Types].xml", content_types)
    z.writestr("_rels/.rels", rels)
    z.writestr("word/document.xml", doc)
PY
  if "$PYTHON" "$DEST/convert.py" "$TMPDIR_X/smoke.docx" >/dev/null; then
    echo "Smoke test OK"
  else
    echo "Smoke test FAILED" >&2
    exit 1
  fi
fi

echo "mark-the-stuff-down installed"
