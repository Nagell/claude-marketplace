#!/usr/bin/env bash
# Install a Nerd Font for the current user: install-font.sh <meslo|fira>
#
# Detects MACOS / WSL / LINUX the same way as Step 1 of the skill, skips files that
# are already present with a valid size, downloads the rest, verifies every file,
# refreshes the font cache on Linux and registers the fonts in HKCU on WSL (no admin).
# Exits non-zero and lists the missing/invalid files if the install is incomplete.
#
# Bash 3.2 compatible (macOS /bin/bash): no associative arrays.
set -euo pipefail

CHOICE="${1:-}"
if [[ "$CHOICE" != "meslo" && "$CHOICE" != "fira" ]]; then
  echo "usage: $0 <meslo|fira>" >&2
  exit 2
fi

if [[ "$(uname)" == "Darwin" ]]; then ENV=MACOS; elif grep -qi microsoft /proc/version 2>/dev/null; then ENV=WSL; else ENV=LINUX; fi
echo "Environment: ${ENV}"

case "$ENV" in
  WSL)
    # Fonts must be on the Windows host for VS Code / Windows Terminal to use them.
    WINUSER=$(cmd.exe /c "echo %USERNAME%" 2>/dev/null | tr -d '\r')
    FONTDIR="/mnt/c/Users/${WINUSER}/AppData/Local/Microsoft/Windows/Fonts"
    WINFONTDIR="C:\\Users\\${WINUSER}\\AppData\\Local\\Microsoft\\Windows\\Fonts"
    ;;
  LINUX) FONTDIR="$HOME/.local/share/fonts" ;;
  MACOS) FONTDIR="$HOME/Library/Fonts" ;;
esac
mkdir -p "${FONTDIR}"

filesize() {
  if [[ "$ENV" == "MACOS" ]]; then stat -f%z "$1" 2>/dev/null || echo 0; else stat -c%s "$1" 2>/dev/null || echo 0; fi
}

DOWNLOADED=0
MISSING=0

if [[ "$CHOICE" == "meslo" ]]; then
  # Four files, each >1MB when valid.
  for font in "Regular" "Bold" "Italic" "Bold Italic"; do
    filepath="${FONTDIR}/MesloLGS NF ${font}.ttf"
    if [[ -f "$filepath" ]] && [[ $(filesize "$filepath") -gt 1000000 ]]; then
      echo "Already installed: MesloLGS NF ${font}.ttf"
    else
      curl -fsSL -o "$filepath" "https://github.com/romkatv/powerlevel10k-media/raw/master/MesloLGS%20NF%20${font// /%20}.ttf" \
        || echo "Download failed: MesloLGS NF ${font}.ttf"
      DOWNLOADED=1
    fi
  done

  for font in "Regular" "Bold" "Italic" "Bold Italic"; do
    filepath="${FONTDIR}/MesloLGS NF ${font}.ttf"
    if [[ -f "$filepath" ]]; then
      size=$(filesize "$filepath")
      if [[ $size -gt 1000000 ]]; then
        echo "OK: MesloLGS NF ${font}.ttf (${size} bytes)"
      else
        echo "INVALID (too small): MesloLGS NF ${font}.ttf (${size} bytes)"
        MISSING=$((MISSING+1))
      fi
    else
      echo "MISSING: MesloLGS NF ${font}.ttf"
      MISSING=$((MISSING+1))
    fi
  done
else
  # The zip holds ~20 TTFs in three variants (standard, Mono, Propo); the pattern
  # FiraCodeNerdFont-*.ttf extracts only the ~6 standard ones.
  filepath="${FONTDIR}/FiraCodeNerdFont-Regular.ttf"
  if [[ -f "$filepath" ]] && [[ $(filesize "$filepath") -gt 100000 ]]; then
    echo "Already installed: FiraCodeNerdFont-Regular.ttf"
  else
    TMPFONT=$(mktemp -d)
    if curl -fsSL -o "${TMPFONT}/FiraCode.zip" "https://github.com/ryanoasis/nerd-fonts/releases/download/v3.4.0/FiraCode.zip"; then
      unzip -j -q -o "${TMPFONT}/FiraCode.zip" "FiraCodeNerdFont-*.ttf" -d "${FONTDIR}" || echo "Unzip failed: FiraCode.zip"
    else
      echo "Download failed: FiraCode.zip"
    fi
    rm -rf "${TMPFONT}"
    DOWNLOADED=1
  fi

  if [[ -f "$filepath" ]]; then
    size=$(filesize "$filepath")
    if [[ $size -gt 100000 ]]; then echo "OK: FiraCodeNerdFont-Regular.ttf (${size} bytes)"; else echo "INVALID (too small): ${size} bytes"; MISSING=1; fi
  else
    echo "MISSING: FiraCodeNerdFont-Regular.ttf"
    MISSING=1
  fi
fi

echo "Missing fonts: ${MISSING}"
if [[ $MISSING -gt 0 ]]; then
  echo "Font install incomplete: retry, or download the files listed above manually into ${FONTDIR}" >&2
  exit 1
fi

# Linux: refresh the font cache so the fonts are available immediately.
# macOS picks up ~/Library/Fonts by itself.
if [[ "$ENV" == "LINUX" && $DOWNLOADED -eq 1 ]]; then
  fc-cache -fv
fi

# WSL: register in the current user's registry hive so Windows discovers the fonts.
# /f overwrites, so re-running is harmless.
if [[ "$ENV" == "WSL" ]]; then
  if [[ "$CHOICE" == "meslo" ]]; then
    for font in "Regular" "Bold" "Italic" "Bold Italic"; do
      regname="MesloLGS NF ${font} (TrueType)"
      regpath="${WINFONTDIR}\\MesloLGS NF ${font}.ttf"
      reg.exe add "HKCU\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Fonts" /v "$regname" /t REG_SZ /d "$regpath" /f
    done
  else
    for f in "${FONTDIR}"/FiraCodeNerdFont-*.ttf; do
      [[ -f "$f" ]] || continue
      fname=$(basename "$f")
      reg.exe add "HKCU\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Fonts" /v "${fname%.ttf} (TrueType)" /t REG_SZ /d "${WINFONTDIR}\\${fname}" /f
    done
  fi
fi

echo "Font install complete: ${CHOICE} (${ENV})"
