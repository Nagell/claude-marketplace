# >>> setup-zsh prefix-history >>>
# Prefix history search: Up/Down cycle through history entries beginning with
# the already-typed text (matching what zsh-autosuggestions shows in grey).
autoload -Uz up-line-or-beginning-search down-line-or-beginning-search
zle -N up-line-or-beginning-search
zle -N down-line-or-beginning-search
bindkey '^[[A' up-line-or-beginning-search   # Up, normal cursor mode
bindkey '^[[B' down-line-or-beginning-search # Down, normal cursor mode
bindkey '^[OA' up-line-or-beginning-search   # Up, application cursor mode
bindkey '^[OB' down-line-or-beginning-search # Down, application cursor mode
# <<< setup-zsh prefix-history <<<
