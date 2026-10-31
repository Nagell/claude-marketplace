#!/usr/bin/env bash
# herdr [[startup]] hook: reopen mdv in every pane the mdv launcher recorded before the
# server stopped. Panes that no longer exist are dropped. The leading space keeps the
# typed command out of zsh history (HIST_IGNORE_SPACE).
set -uo pipefail

herdr="${HERDR_BIN_PATH:-herdr}"
state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/mdv-restore/${HERDR_SOCKET_PATH//[^A-Za-z0-9._-]/_}"
[[ -d "$state_dir" ]] || exit 0

for f in "$state_dir"/*; do
  [[ -f "$f" ]] || continue
  argv=()
  while IFS= read -r -d '' a; do argv+=("$a"); done <"$f"
  pane="$(basename "$f")"
  if (( ${#argv[@]} < 2 )) || ! "$herdr" pane get "$pane" >/dev/null 2>&1; then
    rm -f "$f"
    echo "dropped $pane"
    continue
  fi
  "$herdr" pane run "$pane" " $(printf '%q ' "${argv[@]}")" && echo "reopened $pane: ${argv[*]:1}"
done
