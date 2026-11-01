# >>> setup-zsh claude-pulse >>>
# Claude Code voice: record through the PulseAudio server on Windows
# (%APPDATA%\pulseaudio-wsl) when it runs; WSLg's microphone link hangs.
claude() {
  local pa=tcp:127.0.0.1:4713
  if timeout 1 pactl --server=$pa info >/dev/null 2>&1; then
    PULSE_SERVER=$pa command claude "$@"
  else
    command claude "$@"
  fi
}
# <<< setup-zsh claude-pulse <<<
