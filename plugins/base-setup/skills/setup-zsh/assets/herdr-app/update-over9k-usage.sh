#!/usr/bin/env bash
set -euo pipefail

source_dir="$HOME/.local/src/herdr-over9k"
mod_dir="$HOME/.config/herdr-app/mods/over9k-usage"
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
settings="$HOME/.claude/settings.json"
wrapper_command="sh $HOME/.claude/statusline-over9k.sh $mod_dir/claude-statusline.sh"

mkdir -p "$HOME/.local/src" "$HOME/.config/herdr-app/mods" "$HOME/.claude"

if [ -d "$source_dir/.git" ]; then
  git -C "$source_dir" pull --ff-only
else
  git clone --depth 1 https://github.com/herunan/herdr-over9k "$source_dir"
fi

rsync -a --delete "$source_dir/over9k-usage/mods/over9k-usage/" "$mod_dir/"
if [ -f "$script_dir/statusline-over9k.sh" ]; then
  install -m 755 "$script_dir/statusline-over9k.sh" "$HOME/.claude/statusline-over9k.sh"
else
  curl -fsSL -o "$HOME/.claude/statusline-over9k.sh" \
    https://raw.githubusercontent.com/Nagell/claude-marketplace/main/plugins/base-setup/skills/setup-zsh/assets/herdr-app/statusline-over9k.sh
  chmod 755 "$HOME/.claude/statusline-over9k.sh"
fi

if [ ! -f "$settings" ]; then
  printf '{}\n' > "$settings"
fi

current_command=$(jq -r '.statusLine.command // empty' "$settings")
if [ "$current_command" != "$wrapper_command" ]; then
  cp "$settings" "$settings.bak-over9k-statusline"
  jq '.statusLine' "$settings" > "$HOME/.claude/.over9k-statusline-was.json"
  temp_settings=$(mktemp "${settings}.tmp.XXXXXX")
  jq --arg command "$wrapper_command" \
    '.statusLine = ((.statusLine // {}) + {type: "command", command: $command})' \
    "$settings" > "$temp_settings"
  mv "$temp_settings" "$settings"
fi

sh -n "$mod_dir/claude-statusline.sh" "$mod_dir/setup.sh" "$HOME/.claude/statusline-over9k.sh"
herdr-app check "$mod_dir"
printf '%s\n' 'Over9k Usage is installed. Send one Claude message to refresh its limits.'
