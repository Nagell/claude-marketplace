# >>> setup-zsh resume >>>
# Programs that come back after a herdr (TUI) server restart or a Herdr app reboot. Each runs
# through _resumable, which records the folder and the exact command while it runs and removes
# the record once it ends with the shell still alive, however it was quit. A restart or reboot
# kills the shell too, so the record stays for the restore:
# - Herdr app (HC_TERMINAL_ID): a `cmd-resume` label on the terminal, read by the
#   `setup-zsh herdr-app` block in the restored shell.
# - herdr TUI (HERDR_PANE_ID): a JSON file per pane under ~/.local/state/mdv-restore/, read by
#   the mdv-restore herdr plugin when the server starts.
# SETUP_ZSH_RESUME tells the program it was started this way; nvim uses it to keep the record
# in step with the files it has open (~/.config/nvim/lua/config/resume.lua).
# To make another program resumable, add its name to the list below.
if [[ -o interactive && ( -n $HC_TERMINAL_ID || -n $HERDR_PANE_ID ) ]]; then
  _resume_record() {  # _resume_record '<json>' writes the record; no argument removes it
    if [[ -n $HC_TERMINAL_ID ]]; then
      hc label "$HC_TERMINAL_ID" "cmd-resume=$1" &>/dev/null
    else
      local f="${XDG_STATE_HOME:-$HOME/.local/state}/mdv-restore/${HERDR_SOCKET_PATH//[^A-Za-z0-9._-]/_}/${HERDR_PANE_ID//\//_}"
      if [[ -n $1 ]]; then mkdir -p "${f:h}" && print -r -- "$1" >| "$f"; else rm -f "$f"; fi
    fi
  }
  _resumable() {
    # Only when reading from the terminal: `some-command | mdv` has nothing to reopen.
    # The arguments reach jq NUL-separated on stdin; on its command line jq would take
    # the program's own options (`nvim -c ...`) as its own.
    [[ -t 0 ]] && _resume_record "$(printf '%s\0' "$@" \
      | jq -Rsc --arg cwd "$PWD" '{cwd: $cwd, argv: (split("\u0000") | .[:-1])}')"
    SETUP_ZSH_RESUME=1 command "$@"
    local rc=$?
    _resume_record
    return $rc
  }
  for _resume_cmd in nvim btop lazygit mdv; do
    eval "$_resume_cmd() { _resumable $_resume_cmd \"\$@\" }"
  done
  unset _resume_cmd
fi
# <<< setup-zsh resume <<<
