# clip.exe reads UTF-16LE and PowerShell writes the console code page by default;
# convert both ways or non-ASCII text (ä, ż, —) gets mangled.
_to_win_clipboard() { iconv -f UTF-8 -t UTF-16LE | clip.exe 2>/dev/null }

_cut_to_clipboard() {
  zle kill-region
  echo -n "$CUTBUFFER" | _to_win_clipboard
}
zle -N _cut_to_clipboard

_paste_from_clipboard() {
  local paste
  paste=$(powershell.exe -NoLogo -NoProfile -Command '[Console]::OutputEncoding = [Text.Encoding]::UTF8; [Console]::Out.Write(([string](Get-Clipboard -Raw)) -replace "`r", "")' 2>/dev/null)
  LBUFFER+=$paste
}
zle -N _paste_from_clipboard

bindkey '^X' _cut_to_clipboard
bindkey '^V' _paste_from_clipboard

_backspace_or_delete_region() {
  if (( REGION_ACTIVE )); then
    zle kill-region
    echo -n "$CUTBUFFER" | _to_win_clipboard
  else
    zle backward-delete-char
  fi
}
zle -N _backspace_or_delete_region
bindkey '^?' _backspace_or_delete_region

_delete_or_delete_region() {
  if (( REGION_ACTIVE )); then
    zle kill-region
    echo -n "$CUTBUFFER" | _to_win_clipboard
  else
    zle delete-char
  fi
}
zle -N _delete_or_delete_region
bindkey '^[[3~' _delete_or_delete_region
