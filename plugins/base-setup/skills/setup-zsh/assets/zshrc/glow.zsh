# >>> setup-zsh glow >>>
# glow 3.x word-wraps at a hard-coded 80 columns and never reads the real
# terminal size, so wide markdown tables get shredded to one character per
# line. The width has to be passed on every call. glow-wide.json is the
# built-in dark style with the 2-column document margin dropped and
# box-drawing table separators; both functions fall back to the built-in
# style if that file is missing.
glow() {
  local -a style
  [[ -r $HOME/.config/glow/glow-wide.json ]] && style=(-s "$HOME/.config/glow/glow-wide.json")
  command glow "${style[@]}" -w "${COLUMNS:-100}" "$@"
}

# For tables too wide to wrap readably: render unwrapped and scroll sideways
# with the arrow keys. less -R keeps the colours, -S chops lines instead of
# wrapping them.
glowide() {
  local -a style
  [[ -r $HOME/.config/glow/glow-wide.json ]] && style=(-s "$HOME/.config/glow/glow-wide.json")
  PAGER='less -RSX' command glow "${style[@]}" -p -w 0 "$@"
}
# <<< setup-zsh glow <<<
