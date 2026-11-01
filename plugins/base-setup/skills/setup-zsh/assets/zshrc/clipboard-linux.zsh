_backspace_or_delete_region() {
  if (( REGION_ACTIVE )); then
    zle kill-region
  else
    zle backward-delete-char
  fi
}
zle -N _backspace_or_delete_region
bindkey '^?' _backspace_or_delete_region

_delete_or_delete_region() {
  if (( REGION_ACTIVE )); then
    zle kill-region
  else
    zle delete-char
  fi
}
zle -N _delete_or_delete_region
bindkey '^[[3~' _delete_or_delete_region
