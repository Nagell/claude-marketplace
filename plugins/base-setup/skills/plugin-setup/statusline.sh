#!/bin/bash
# Single-line lean statusline (p10k-inspired).
#
# Segments: 󰫢 model    folder    branch  󰓅 bar pct  $cost
# Context % uses Claude Code's pre-calculated remaining_percentage,
# which accounts for compaction reserves. 100% = compaction fires.

# Read stdin (Claude Code passes JSON data via stdin)
stdin_data=$(cat)

# Single jq call - extract all values at once
# Prefer pre-calculated remaining_percentage (100 - remaining = used toward compact)
# Fall back to manual calc from raw tokens if not available
IFS=$'\t' read -r current_dir model_name cost lines_added lines_removed duration_ms ctx_used cache_pct < <(
    echo "$stdin_data" | jq -r '[
        .workspace.current_dir // "unknown",
        .model.display_name // "Unknown",
        (try (.cost.total_cost_usd // 0 | . * 100 | floor / 100) catch 0),
        (.cost.total_lines_added // 0),
        (.cost.total_lines_removed // 0),
        (.cost.total_duration_ms // 0),
        (try (
            if (.context_window.remaining_percentage // null) != null then
                100 - (.context_window.remaining_percentage | floor)
            elif (.context_window.context_window_size // 0) > 0 then
                (((.context_window.current_usage.input_tokens // 0) +
                  (.context_window.current_usage.cache_creation_input_tokens // 0) +
                  (.context_window.current_usage.cache_read_input_tokens // 0)) * 100 /
                 .context_window.context_window_size) | floor
            else "null" end
        ) catch "null"),
        (try (
            (.context_window.current_usage // {}) |
            if (.input_tokens // 0) + (.cache_read_input_tokens // 0) > 0 then
                ((.cache_read_input_tokens // 0) * 100 /
                 ((.input_tokens // 0) + (.cache_read_input_tokens // 0))) | floor
            else 0 end
        ) catch 0)
    ] | @tsv'
)

# Bash-level fallback: if jq crashed entirely, extract fields individually
if [ -z "$current_dir" ] && [ -z "$model_name" ]; then
    current_dir=$(echo "$stdin_data" | jq -r '.workspace.current_dir // .cwd // "unknown"' 2>/dev/null)
    model_name=$(echo "$stdin_data" | jq -r '.model.display_name // "Unknown"' 2>/dev/null)
    cost=$(echo "$stdin_data" | jq -r '(.cost.total_cost_usd // 0)' 2>/dev/null)
    lines_added=$(echo "$stdin_data" | jq -r '(.cost.total_lines_added // 0)' 2>/dev/null)
    lines_removed=$(echo "$stdin_data" | jq -r '(.cost.total_lines_removed // 0)' 2>/dev/null)
    duration_ms=$(echo "$stdin_data" | jq -r '(.cost.total_duration_ms // 0)' 2>/dev/null)
    ctx_used=""
    cache_pct="0"
    : "${current_dir:=unknown}"
    : "${model_name:=Unknown}"
    : "${cost:=0}"
    : "${lines_added:=0}"
    : "${lines_removed:=0}"
    : "${duration_ms:=0}"
fi

# Git info
if cd "$current_dir" 2>/dev/null; then
    git_branch=$(git -c core.useBuiltinFSMonitor=false branch --show-current 2>/dev/null)
    git_root=$(git -c core.useBuiltinFSMonitor=false rev-parse --show-toplevel 2>/dev/null)
fi

# Build repo path display (folder name only for brevity)
if [ -n "$git_root" ]; then
    repo_name=$(basename "$git_root")
    if [ "$current_dir" = "$git_root" ]; then
        folder_name="$repo_name"
    else
        folder_name=$(basename "$current_dir")
    fi
else
    folder_name=$(basename "$current_dir")
fi

# Generate visual progress bar for context usage
progress_bar=""
bar_width=12

if [ -n "$ctx_used" ] && [ "$ctx_used" != "null" ]; then
    filled=$((ctx_used * bar_width / 100))
    # Show at least 1 filled cell when context is used at all
    if [ "$ctx_used" -gt 0 ] && [ "$filled" -eq 0 ]; then
        filled=1
    fi
    empty=$((bar_width - filled))

    # Uniform bar: white filled, dim-white empty (no traffic-light coloring)
    progress_bar='\033[97m'
    for ((i=0; i<filled; i++)); do
        progress_bar="${progress_bar}▰"
    done
    progress_bar="${progress_bar}\033[37;2m"
    for ((i=0; i<empty; i++)); do
        progress_bar="${progress_bar}▱"
    done
    progress_bar="${progress_bar}\033[0m"

    ctx_pct="${ctx_used}%"
else
    ctx_pct=""
fi

# Strip "(1M context)" and "Claude X.Y " prefix from model name
short_model=$(echo "$model_name" | sed -E 's/ \(1M context\)//; s/Claude [0-9.]+ //; s/^Claude //')

# Style: white text everywhere, single cyan accent for icons + $.
GAP="  "
ACCENT='\033[96m'   # bright cyan — for icons and $
TEXT='\033[97m'     # bright white — for all text
RESET='\033[0m'

# 󰛄 model — accent icon, white text
seg_model=$(printf '%b󰛄 %b%s%b' "$ACCENT" "$TEXT" "$short_model" "$RESET")

# 󰉋 folder — accent icon, white text
seg_folder=$(printf '%b󰉋 %b%s%b' "$ACCENT" "$TEXT" "$folder_name" "$RESET")

# 󰘬 branch — accent icon, white text
if [ -n "$git_branch" ]; then
    seg_branch=$(printf '%b󰘬 %b%s%b' "$ACCENT" "$TEXT" "$git_branch" "$RESET")
else
    seg_branch=""
fi

# 󰓅 gauge + bar + pct — accent icon, neutral bar, white pct
if [ -n "$progress_bar" ] && [ -n "$ctx_pct" ]; then
    seg_ctx=$(printf '%b󰓅%b %b %b%s%b' "$ACCENT" "$RESET" "$progress_bar" "$TEXT" "$ctx_pct" "$RESET")
else
    seg_ctx=""
fi

# $ cost — accent $, space, white number
seg_cost=$(printf '%b$ %b%s%b' "$ACCENT" "$TEXT" "$cost" "$RESET")

# Assemble — skip empty segments cleanly
line="$seg_model$GAP$seg_folder"
[ -n "$seg_branch" ] && line="$line$GAP$seg_branch"
[ -n "$seg_ctx" ] && line="$line$GAP$seg_ctx"
line="$line$GAP$seg_cost"

printf '%b' "$line"
