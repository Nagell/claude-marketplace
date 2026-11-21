# >>> setup-zsh agent-resume-line-init >>>
# The agent-resume block above starts the agent from the first precmd, where p10k's instant
# prompt still redirects stdin/stdout, so Claude falls into --print mode and exits. Run it
# once the line editor owns the terminal instead, only where a session is recorded.
if [[ -o interactive && -n $HC_TERMINAL_ID ]] && (( ${+functions[__agent_resume]} )); then
  add-zsh-hook -d precmd __agent_resume
  if [[ $(hc get "$HC_TERMINAL_ID" --json 2>/dev/null) == *'"agent-resume"'* ]]; then
    _agent_resume_line_init() {
      add-zle-hook-widget -d line-init _agent_resume_line_init
      [[ -n $BUFFER ]] && return  # the herdr-app block is already reopening a program here
      BUFFER=' __agent_resume'
      zle accept-line
    }
    autoload -Uz add-zle-hook-widget
    add-zle-hook-widget line-init _agent_resume_line_init
  else
    unfunction __agent_resume
  fi
fi
# <<< setup-zsh agent-resume-line-init <<<
