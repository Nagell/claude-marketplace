# >>> setup-zsh keys >>>
# zsh-shift-select binds Option+Shift on macOS and Ctrl+Shift elsewhere; bind Ctrl+Shift
# explicitly so it selects by word / to the buffer ends on every platform.
for _seq _widget in '^[[1;6D' backward-word '^[[1;6C' forward-word \
                    '^[[1;6H' beginning-of-buffer '^[[1;6F' end-of-buffer; do
  bindkey -M emacs "$_seq" shift-select::$_widget
  bindkey -M shift-select "$_seq" shift-select::$_widget
done
unset _seq _widget

# Keys zsh's emacs keymap leaves unbound; each has several sequences depending on the terminal.
for _seq in '^[[H' '^[[1~' '^[OH'; do bindkey -M emacs "$_seq" beginning-of-line; done
for _seq in '^[[F' '^[[4~' '^[OF'; do bindkey -M emacs "$_seq" end-of-line; done
bindkey -M emacs '^[[1;5D' backward-word     # Ctrl+Left (on macOS only if Spaces doesn't take it)
bindkey -M emacs '^[[1;5C' forward-word      # Ctrl+Right
bindkey -M emacs '^[[3;5~' kill-word         # Ctrl+Delete
bindkey -M emacs '^[[3;3~' kill-word         # Alt/Option+Delete
bindkey -M emacs '^U' backward-kill-line     # Cmd+Backspace (Ghostty sends ^U): to line start, as on macOS
unset _seq
# <<< setup-zsh keys <<<
