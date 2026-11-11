#!/bin/sh
# Claude Code's status line with Over9k's limits (setup-zsh). Over9k's claude-statusline.sh
# ($1) runs in the background with its output dropped: it saves Claude's 5-hour and weekly
# limits for Herdr's Usage strip (~/.cache/over9k/usage/claude.json). What shows is the
# status line you had before, kept in ~/.claude/.over9k-statusline-was.json; Over9k's own
# off switch (setup.sh status off) puts that one back from the same file.
# $1 also stays in settings.json's command, which is how the strip sees it is on.
in=$(cat)
[ -f "${1:-}" ] && (printf '%s' "$in" | sh "$1" >/dev/null 2>&1 &)
was=$(jq -r '.command // empty' "$HOME/.claude/.over9k-statusline-was.json" 2>/dev/null)
# A saved command that is this wrapper again would call itself without end.
case "$was" in *statusline-over9k.sh*) was= ;; esac
if [ -n "$was" ]; then printf '%s' "$in" | sh -c "$was"; fi
