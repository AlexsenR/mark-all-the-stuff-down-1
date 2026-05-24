#requires -Version 5.1
param(
  [switch]$NoUv,
  [string]$Only = ""
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding
try { chcp 65001 | Out-Null } catch {}

function Assert-ExitCode {
  param(
    [string]$Action
  )
  if ($LASTEXITCODE -ne 0) {
    throw "$Action failed with exit code $LASTEXITCODE"
  }
}

$NoUvFlag = $NoUv.IsPresent -or ($args -contains "--no-uv")
$DryRun = $env:MTSD_DRY_RUN -eq "1"
$SourceOverride = $env:MTSD_SOURCE
$Dest = Join-Path $HOME ".local\share\mark-all-the-stuff-down"
$RuntimeFiles = @("convert.py", "ocr.py", "SKILL.md", "README.md", "LICENSE")

function Install-RuntimeFromSource {
  param(
    [string]$Source
  )

  if (Test-Path $Dest) {
    Remove-Item -Recurse -Force $Dest
  }
  New-Item -ItemType Directory -Force -Path $Dest | Out-Null

  foreach ($file in $RuntimeFiles) {
    $from = Join-Path $Source $file
    if (-not (Test-Path -Path $from -PathType Leaf)) {
      throw "ERROR: missing runtime file: $file"
    }
    Copy-Item -Force $from (Join-Path $Dest $file)
  }

  $tessdata_src = Join-Path $Source "tessdata"
  $tessdata_dst = Join-Path $Dest "tessdata"
  if (-not (Test-Path $tessdata_src)) {
    Write-Error "ERROR: missing tessdata directory"
    exit 1
  }
  Copy-Item -Recurse $tessdata_src $tessdata_dst

  foreach ($f in @("ocr.py", "tessdata\rus.traineddata", "tessdata\eng.traineddata", "tessdata\osd.traineddata")) {
    if (-not (Test-Path (Join-Path $Dest $f))) {
      Write-Error "post-install check failed; missing $Dest\$f"
      exit 1
    }
  }
}

try {
  python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
  Assert-ExitCode "python version check"
} catch {
  throw "ERROR: Python 3.10+ is required"
}

if ($Only -and @("claude", "codex", "pi") -notcontains $Only) {
  throw "Unknown -Only value: $Only"
}

if ($SourceOverride) {
  Install-RuntimeFromSource $SourceOverride
} else {
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Dest) | Out-Null
  $tmpSource = Join-Path ([System.IO.Path]::GetTempPath()) ("mtsd-src-" + [guid]::NewGuid())
  try {
    git clone --depth 1 https://github.com/strigov/mark-all-the-shit-down $tmpSource
    Assert-ExitCode "git clone"
    Install-RuntimeFromSource $tmpSource
  } finally {
    if (Test-Path $tmpSource) {
      Remove-Item -Recurse -Force $tmpSource -ErrorAction SilentlyContinue
    }
  }
}

$candidates = @()
if ($env:MTSD_SKILL_TARGET) {
  $candidates += $env:MTSD_SKILL_TARGET
} else {
  $known = @(
    @{ Name = "claude"; Path = Join-Path $HOME ".claude\skills" },
    @{ Name = "codex"; Path = Join-Path $HOME ".agents\skills" },
    @{ Name = "pi"; Path = Join-Path $HOME ".config\pi\skills" }
  )
  foreach ($item in $known) {
    if ((-not $Only -or $Only -eq $item.Name) -and (Test-Path $item.Path)) {
      $candidates += $item.Path
    }
  }
}

if ($candidates.Count -eq 0) {
  throw "No agent skill dir found. Create one of: ~\.claude\skills, ~\.agents\skills, ~\.config\pi\skills"
}

if (-not $NoUvFlag -and -not (Get-Command uv -ErrorAction SilentlyContinue) -and -not $DryRun) {
  irm https://astral.sh/uv/install.ps1 | iex
  $env:PATH = "$HOME\.local\bin;$HOME\.cargo\bin;$env:PATH"
}

foreach ($d in $candidates) {
  New-Item -ItemType Directory -Force -Path $d | Out-Null
  $target = Join-Path $d "mark-all-the-stuff-down"
  if (Test-Path $target) {
    Remove-Item -Recurse -Force $target
  }
  New-Item -ItemType Junction -Path $target -Target $Dest | Out-Null
  Write-Host "Linked $target -> $Dest"
}

if (-not $DryRun) {
  if (-not $NoUvFlag -and (Get-Command uv -ErrorAction SilentlyContinue)) {
    uv tool install markitdown `
      --with "markitdown[docx,xlsx,pdf,pptx,xls,rtf,html,epub]" `
      --with pymupdf4llm
    Assert-ExitCode "uv tool install"
  } else {
    python -m pip install --user --quiet `
      "markitdown[docx,xlsx,pdf,pptx,xls,rtf,html,epub]" pymupdf4llm `
      pdfplumber pypdf python-docx openpyxl python-pptx beautifulsoup4
    Assert-ExitCode "python -m pip install"
  }

  python (Join-Path $Dest "convert.py") --version | Out-Null
  Assert-ExitCode "python convert.py --version"

  $tmp = New-Item -ItemType Directory -Path (Join-Path $env:TEMP ("mtsd-" + [guid]::NewGuid()))
  $env:MTSD_SMOKE_OUT = Join-Path $tmp "smoke.docx"
  $pyScript = @'
import os
import zipfile

out = os.environ["MTSD_SMOKE_OUT"]
content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>"""
rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>"""
doc = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>smoke</w:t></w:r></w:p></w:body></w:document>"""
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("[Content_Types].xml", content_types)
    z.writestr("_rels/.rels", rels)
    z.writestr("word/document.xml", doc)
'@
  try {
    python -c $pyScript
    Assert-ExitCode "python smoke DOCX generation"
    python (Join-Path $Dest "convert.py") (Join-Path $tmp "smoke.docx") | Out-Null
    Assert-ExitCode "python smoke conversion"
    Write-Host "Smoke test OK"
  } finally {
    Remove-Item Env:MTSD_SMOKE_OUT -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
  }
}

Write-Host "mark-all-the-stuff-down installed"
