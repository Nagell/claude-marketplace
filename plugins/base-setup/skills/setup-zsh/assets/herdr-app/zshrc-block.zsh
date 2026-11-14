# >>> setup-zsh herdr-app >>>
# Herdr app (herdr-core) terminals. A lost terminal (reboot, core restart) comes back as a
# fresh shell with its labels intact, and this block brings back what ran there:
# - `agent-resume` label (herdr-agent-resume mod, Claude Code / Codex): the first such shell
#   runs one resume pass in the background, the same pass as Ctrl+Shift+R. The lock keeps
#   shells restored together from typing twice; the pass waits for the others and skips
#   sessions that were quit on purpose. Before that, agent-resume-fallback.py (setup-zsh)
#   points a label back at the conversation a Claude Code restart replaced, when the new
#   session never got a message: first for this shell's terminal (its `here` reads the
#   label), then in the pass for all of them.
# - `cmd-resume` label (the `setup-zsh resume` block: nvim, btop, lazygit, mdv): the restored
#   shell types `cd <folder> && <command>` once the line editor is up (p10k's instant prompt
#   still owns the terminal during the first precmd); the leading space keeps it out of
#   history.
# Otherwise new shells start in ~/<WORK_DIR> instead of ~.
if [[ -o interactive && -n $HC_TERMINAL_ID ]]; then
  _hc_labels=$(hc get "$HC_TERMINAL_ID" --json 2>/dev/null | jq -c '.labels // {}' 2>/dev/null)
  _hc_resume=~/.config/herdr-app/mods/agent-resume/agent_resume.py
  _hc_fallback=~/.local/bin/agent-resume-fallback.py
  rmdir ~/.cache/herdr-agent-resume.lock(N/mm+2) 2>/dev/null  # left by a pass that was cut off
  if [[ $_hc_labels == *'"agent-resume"'* && -f $_hc_fallback ]]; then
    python3 -I "$_hc_fallback" "$HC_TERMINAL_ID" >/dev/null 2>&1
  fi
  if [[ $_hc_labels == *'"agent-resume"'* && -f $_hc_resume ]] \
    && mkdir ~/.cache/herdr-agent-resume.lock 2>/dev/null; then
    ( [[ -f $_hc_fallback ]] && python3 -I "$_hc_fallback" >/dev/null 2>&1
      python3 "$_hc_resume" resume >/dev/null 2>&1; rmdir ~/.cache/herdr-agent-resume.lock ) &!
  fi
  _hc_cmd=$(jq -r '.["cmd-resume"] // empty | fromjson | select(.argv | length > 0)
    | "cd \(.cwd | @sh) && \(.argv | map(@sh) | join(" "))"' <<<"$_hc_labels" 2>/dev/null)
  unset _hc_labels _hc_resume _hc_fallback
  if [[ -n $_hc_cmd ]]; then
    _hc_reopen_cmd=" $_hc_cmd"
    _hc_reopen() {
      add-zle-hook-widget -d line-init _hc_reopen
      BUFFER=$_hc_reopen_cmd
      unset _hc_reopen_cmd
      zle accept-line
    }
    autoload -Uz add-zle-hook-widget
    add-zle-hook-widget line-init _hc_reopen
  elif [[ $PWD == $HOME && -d $HOME/<WORK_DIR> ]]; then
    cd $HOME/<WORK_DIR>
  fi
  unset _hc_cmd
fi
# <<< setup-zsh herdr-app <<<
