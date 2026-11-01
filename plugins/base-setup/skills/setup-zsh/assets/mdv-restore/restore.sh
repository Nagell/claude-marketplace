#!/usr/bin/env bash
# herdr [[startup]] hook: reopen what ran in each pane before the server stopped. The
# `setup-zsh resume` block in ~/.zshrc records it per pane as {"cwd": ..., "argv": [...]}
# (nvim, btop, lazygit, mdv; nvim keeps the list of open files current). Panes that no
# longer exist are dropped. The leading space keeps the typed command out of zsh history
# (HIST_IGNORE_SPACE).
set -uo pipefail

herdr="${HERDR_BIN_PATH:-herdr}"
state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/mdv-restore/${HERDR_SOCKET_PATH//[^A-Za-z0-9._-]/_}"
[[ -d "$state_dir" ]] || exit 0

for f in "$state_dir"/*; do
  [[ -f "$f" ]] || continue
  pane="$(basename "$f")"
  cmd="$(jq -r 'select(.argv | length > 0) | "cd \(.cwd | @sh) && \(.argv | map(@sh) | join(" "))"' "$f" 2>/dev/null)"
  if [[ -z "$cmd" ]] || ! "$herdr" pane get "$pane" >/dev/null 2>&1; then
    rm -f "$f"
    echo "dropped $pane"
    continue
  fi
  "$herdr" pane run "$pane" " $cmd" && echo "reopened $pane: $cmd"
done
