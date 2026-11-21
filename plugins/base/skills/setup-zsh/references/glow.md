# glow reference

Step 14 sends you here after the glow binary is installed. glow 3.x word-wraps at a
hard-coded 80 columns and never reads the real terminal size, so this sets up a wide
style, a config file and the `glow()` / `glowide()` zsh functions that pass the width on
every call. Run the sections in order.

## Build the wide style

This is the upstream dark style with two changes: the 2-column document margin dropped (buys back 4 columns of table), and box-drawing table separators instead of ASCII `|` and `-`.

Starting from the full upstream file is not optional — a hand-written partial JSON throws away every colour in the theme, since custom styles replace the built-in theme rather than merge into it.

```bash
mkdir -p ~/.config/glow
curl -fsSL https://raw.githubusercontent.com/charmbracelet/glamour/master/styles/dark.json \
  | jq '.document.margin = 0
        | .table = {center_separator:"┼", column_separator:"│", row_separator:"─"}' \
  > ~/.config/glow/glow-wide.json
```

Requires `jq`. If it is missing, `sudo apt install jq -y` or `brew install jq`.

Verify the file is valid and patched:

```bash
jq -e '.document.margin == 0 and (.table.column_separator == "│") and (.heading | length > 0)' \
  ~/.config/glow/glow-wide.json && echo "style OK"
```

The `.heading` check is the one that matters — it confirms the upstream theme survived rather than getting replaced by a two-key stub.

This pins rendering to the dark theme, giving up glow's `auto` light/dark detection. On a dark terminal `auto` already resolves to `dark`, so it costs nothing there. On a light terminal, skip this section and drop the `-s` flag from the functions in `assets/zshrc/glow.zsh` before appending them.

## Write the glow config

Use the Write tool to create `~/.config/glow/glow.yml`:

```yaml
# style name or JSON path (default "auto")
style: "auto"
# mouse support (TUI-mode only)
mouse: false
# use pager to display markdown
pager: false
# word-wrap at width. Fallback only, for scripts and non-zsh shells. The glow()
# function in ~/.zshrc passes -w $COLUMNS on every interactive call and wins.
width: 120
# show all files, including hidden and ignored.
all: true
```

Do not set `width: 80` here — that is glow's own default and it is the thing that shreds tables.

## Configure ~/.zshrc

Read `~/.zshrc` using the Read tool. If it already contains `# >>> setup-zsh glow >>>`, the block is configured - skip this section.

Otherwise Read `<this-skill-dir>/assets/zshrc/glow.zsh` and use the Edit tool to append its content at the end of `~/.zshrc`. These are function definitions, so unlike the keybinding blocks they do not need to land before the p10k sourcing line.

Notes on the shape of this block, since each part is load-bearing:

- **Functions, not aliases.** `alias glow='glow -w $COLUMNS'` also works in zsh, but a function composes with the `-s` guard and reads better.
- **`command glow`** stops the function recursing into itself.
- **`${COLUMNS:-100}`** is re-evaluated per call, so it tracks window resizes. zsh maintains `COLUMNS` automatically. The `100` fallback covers the case where the function is called from a script with no tty.
- **The `-r` guard on the style file** keeps glow working if `glow-wide.json` is missing or unreadable, rather than failing on a bad `-s` path.
- **`-X` on less** keeps the rendered table in scrollback after quitting instead of wiping it.
- TUI mode is unaffected. Bare `glow` with no file argument still opens the browser UI; the extra flags are accepted and ignored there.

## Verify

```bash
printf '| a | b | c |\n|---|---|---|\n| %s | %s | %s |\n' \
  "$(head -c 120 /dev/urandom | base64 | tr -d '\n')" "short" "also short" > /tmp/glowtest.md
zsh -i -c 'glow /tmp/glowtest.md' | head -5
```

The table should fill the terminal width rather than stopping at 78 columns. For an exact check:

```bash
zsh -i -c 'glow /tmp/glowtest.md' | sed 's/\x1b\[[0-9;]*m//g' \
  | awk '{ if (length($0) > m) m = length($0) } END { print "widest line:", m }'
```

Compare that number against `tput cols`. They should match. If it prints 78 or 80, the function is not loaded or `command glow` is picking up a `width: 80` from `glow.yml`.
