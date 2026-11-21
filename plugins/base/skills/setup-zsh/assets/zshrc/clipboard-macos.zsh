_cut_to_clipboard() {
  zle kill-region
  echo -n "$CUTBUFFER" | pbcopy 2>/dev/null
}
zle -N _cut_to_clipboard

_paste_from_clipboard() {
  local paste
  paste=$(pbpaste 2>/dev/null)
  LBUFFER+=$paste
}
zle -N _paste_from_clipboard

bindkey '^X' _cut_to_clipboard
bindkey '^V' _paste_from_clipboard

_backspace_or_delete_region() {
  if (( REGION_ACTIVE )); then
    zle kill-region
    echo -n "$CUTBUFFER" | pbcopy 2>/dev/null
  else
    zle backward-delete-char
  fi
}
zle -N _backspace_or_delete_region
bindkey '^?' _backspace_or_delete_region

_delete_or_delete_region() {
  if (( REGION_ACTIVE )); then
    zle kill-region
    echo -n "$CUTBUFFER" | pbcopy 2>/dev/null
  else
    zle delete-char
  fi
}
zle -N _delete_or_delete_region
bindkey '^[[3~' _delete_or_delete_region
