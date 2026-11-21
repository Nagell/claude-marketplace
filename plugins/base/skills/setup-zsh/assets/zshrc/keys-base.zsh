# Windows-like keybindings
_select_all() {
  MARK=0
  CURSOR=${#BUFFER}
  REGION_ACTIVE=1
  # zsh-shift-select's keymap: arrows deselect, Backspace/Delete remove the selection.
  zle -K shift-select
}
zle -N _select_all
bindkey '^A' _select_all
bindkey '^Z' undo
bindkey '^Y' redo
