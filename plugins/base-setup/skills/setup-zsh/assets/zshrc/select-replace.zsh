# >>> setup-zsh select-replace >>>
# Typing or pasting over a Shift-selection replaces it, as in a GUI text field;
# zsh-shift-select alone deselects and inserts, and drops non-ASCII keys.
_shift_select_replace() {
  zle kill-region -w
  zle -K main
  zle -U "$KEYS"
}
zle -N _shift_select_replace
bindkey -M shift-select -R ' '-'~' _shift_select_replace
bindkey -M shift-select -R '\M-^@'-'\M-^?' _shift_select_replace

_shift_select_paste() {
  zle kill-region -w
  zle -K main
  zle bracketed-paste -w
}
zle -N _shift_select_paste
bindkey -M shift-select '^[[200~' _shift_select_paste
# <<< setup-zsh select-replace <<<
