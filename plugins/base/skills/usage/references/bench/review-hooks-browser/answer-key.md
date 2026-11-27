# Answer key: review-hooks-browser

Not shown to review agents. 14 bugs, each closed by a later fix commit of this repository. Lines are in `snap/`; hunks are excerpts of the fixing commit (trimmed to the lines that matter; `...` marks a cut). The browser fixes in `992289b` touch `plugins/extras/skills/browser/`, the same files after the browser skill moved there.

Scoring: a key item is CAUGHT when a report states the mechanism, not only the file; PARTIAL when it names the right spot with a wrong or vague mechanism.

## Hooks (`plugins/base/hooks/safety-guards.sh`)

### H1 (high): push token looked up in the session's directory

Mechanism: the token is resolved with `git rev-parse --show-toplevel` from the hook's working directory, the session's, not the pushed repo, so `cd <repo> && git push` and `git -C <repo> push` are checked against the wrong place.
Location: `snap/plugins/base/hooks/safety-guards.sh:87`. Fix: `0933c9f`.

```diff
@@ -86,3 +86,16 @@
-  GIT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME")
+  # The hook runs in the session's directory, which is often not the repo being pushed,
+  # so resolve the repo from the command: `git -C <dir>`, else a leading `cd <dir>`.
+  PUSH_DIR=""
+  C_RE="git[[:space:]]+-C[[:space:]]+(\"[^\"]+\"|'[^']+'|[^[:space:];&|]+)"
+  CD_RE="^[[:space:]]*cd[[:space:]]+(\"[^\"]+\"|'[^']+'|[^[:space:];&|]+)"
+  ...
+  GIT_ROOT=$(git -C "${PUSH_DIR:-.}" rev-parse --show-toplevel 2>/dev/null || echo "$HOME")
```

### H2 (medium): force check misses forms of force push

Mechanism: `git\s+push\s+.*--force[^-]` needs a character after `--force`, so a bare or trailing `--force` passes; `git -C <dir> push -f` and `+ref` refspecs pass too.
Location: `snap/plugins/base/hooks/safety-guards.sh:102`. Fix: `fd405f0`.

```diff
-if echo "$COMMAND" | grep -qE 'git\s+push\s+.*--force[^-]'; then
-  if ! echo "$COMMAND" | grep -qE 'force-with-lease'; then
+while IFS= read -r SEGMENT; do
+  [[ $SEGMENT =~ $PUSH_RE ]] || continue
+  read -ra PUSH_ARGS <<<"${SEGMENT#*"${BASH_REMATCH[0]}"}"
+  for ARG in "${PUSH_ARGS[@]}"; do
+    case $ARG in
+      --force-with-lease* | --force-if-includes) continue ;;
+    esac
+    if [[ $ARG == --force || $ARG == --force=* || $ARG == +* || $ARG =~ ^-[[:alpha:]]*f[[:alpha:]]*$ ]]; then
```

### H3 (low): force check fires on text inside heredocs and quotes

Mechanism: the force check greps the raw `$COMMAND`, so `git push --force` written inside a heredoc or a quoted commit message blocks a harmless command.
Location: `snap/plugins/base/hooks/safety-guards.sh:102`. Fix: `fd405f0`.

```diff
+FORCE_TEXT=$(printf '%s\n' "$COMMAND" | sed 's/\\n/\n/g' |
+  awk 'term != "" { l = $0; sub(/^\t+/, "", l); if (l == term) term = ""; next }
+    match($0, /(^|[^<])<<-?[ \t]*["'\'']?[A-Za-z0-9_]+/) {
+      term = substr($0, RSTART, RLENGTH); sub(/^[^<]*<<-?[ \t]*["'\'']?/, "", term)
+    }
+    { print }' |
+  tr '\n' '\036' | sed "s/\"[^\"]*\"//g; s/'[^']*'//g" | tr '\036' '\n' |
+  sed -E 's/(&&|\|\||[;|&])/\n/g')
```

### H4 (medium): token spent before the force check

Mechanism: the token gate (lines 86-93) consumes `.claude-push-token` before the force check (line 102) runs, so a blocked force push still spends the user's approval.
Location: `snap/plugins/base/hooks/safety-guards.sh:86`. Fix: `fd405f0`.

```diff
@@ -76,0 +77,33 @@ fi
+# ============================================
+# BLOCK: Unsafe git force push
+# Runs before the push token gate below, so a blocked force push keeps the token.
+# ============================================
...
@@ -112,16 +146,0 @@ fi
-# ============================================
-# BLOCK: Unsafe git force push
-# ============================================
```

### H5 (high): push gate bypassed by common command shapes

Mechanism: the gate is anchored at start, `;`, `&&` or `||` and the command is cut at the first `<<` (lines 84-86), so a push on a new line, after `then`, inside `$(...)`, after `env X=1`, inside `bash -c`, or after a heredoc (the usual commit form) passes with no token.
Location: `snap/plugins/base/hooks/safety-guards.sh:84`. Fix: `5911c75`.

```diff
+HEREDOC_FREE=$(drop_heredocs)
+# PUSH_TEXT holds one shell command per line, from two sources:
+# 1. The command itself with quoted strings stripped, ...
+# 2. Code that runs even when it sits inside quotes: $(...), backticks and the
+#    string after sh -c, bash -lc, eval, --exec or -x. ...
+# Matching is unanchored (`env X=1 git push`, `then git push`, `rtk git push`
+# all count).
+TOP_TEXT=$(printf '%s\n' "$HEREDOC_FREE" |
+  tr '\n' '\036' | sed "s/\"[^\"]*\"//g; s/'[^']*'//g" | tr '\036' '\n' |
+  sed -E 's/(&&|\|\||[;|&()`])/\n/g')
+PUSH_RE='(^|[[:space:]/])git([[:space:]]+-{1,2}[^[:space:]]+([[:space:]]+[^[:space:]-][^[:space:]]*)?)*[[:space:]]+push([^[:alnum:]_-]|$)'
```

## Browser scripts (`plugins/browser/skills/browser/`)

### S1 (high): stored logins filled by literal password value

Mechanism: the docs tell the agent to source the logins file and `fill` with `"$BROWSER_ADMIN_PASSWORD"`, so the secret passes through the model, the transcript and `ps`, instead of a fill by key name through `PLAYWRIGHT_MCP_SECRETS_FILE`.
Location: `snap/plugins/browser/skills/browser/references/credentials.md:158` (also `scripts/common.sh:12`, where the secrets file is never exported). Fix: `05e0493`.

```diff
--- a/plugins/browser/skills/browser/scripts/common.sh
@@ -13,0 +14,8 @@ PW_CLI_PKG="@playwright/cli@0.1.23"
+BROWSER_CRED_FILE="${BROWSER_CREDENTIALS:-$HOME/.claude/browser-users.env}"
+if [ -f "$BROWSER_CRED_FILE" ]; then
+  export PLAYWRIGHT_MCP_SECRETS_FILE="$BROWSER_CRED_FILE"
+fi
--- a/plugins/browser/skills/browser/references/credentials.md
-set -a && . ~/.claude/browser-users.env && set +a
-bash "${CLAUDE_SKILL_DIR}/scripts/pw.sh" -s="$S" fill e2 "$BROWSER_ADMIN_EMAIL"
-bash "${CLAUDE_SKILL_DIR}/scripts/pw.sh" -s="$S" fill e3 "$BROWSER_ADMIN_PASSWORD"
+bash "${CLAUDE_SKILL_DIR}/scripts/pw.sh" -s="$S" fill e2 BROWSER_ADMIN_EMAIL
+bash "${CLAUDE_SKILL_DIR}/scripts/pw.sh" -s="$S" fill e3 BROWSER_ADMIN_PASSWORD
```

### S2 (medium): `--stop '*'` stops the default session

Mechanism: the name is sanitised before the wildcard check, so `*` becomes an empty name; an empty `-s=` is the CLI's default session, which then gets stopped.
Location: `snap/plugins/browser/skills/browser/scripts/launch.sh:178`. Fix: `05e0493`.

```diff
@@ -178 +178,0 @@ case "$action" in
-    session=$(sanitize "$session")
@@ -183,0 +185,2 @@ case "$action" in
+    session=$(sanitize "$session")
+    [ -n "$session" ] || die "--stop needs a session name of letters, digits or dashes."
```

### S3 (low): `--url` ignored when a session is reused

Mechanism: a running session with the same name returns early, before the URL is opened.
Location: `snap/plugins/browser/skills/browser/scripts/launch.sh:284`. Fix: `05e0493`.

```diff
@@ -284,0 +288,3 @@ start_one() {
+    if [ -n "$url" ]; then
+      pw -s="$name" goto "$url"
+    fi
```

### S4 (medium): attach-chrome trusts any browser on the port

Mechanism: it only checks that a debug Chrome process runs (`pgrep -f -- "$PROFILE_RE"`), not that it owns port 9222, so another browser on the port is treated as the dedicated one.
Location: `snap/plugins/browser/skills/browser/scripts/attach-chrome.sh:114`. Fix: `05e0493`.

```diff
+port_is_ours() {
+  local pid
+  pid=$(port_owner_pid || true)
+  if [ -n "$pid" ]; then
+    ps -o args= -p "$pid" 2>/dev/null | grep -Eq -- "user-data-dir=$PROFILE_RE"
...
-  if ! pgrep -f -- "$PROFILE_RE" >/dev/null 2>&1; then
+  if ! port_is_ours; then
```

### S5 (low): preflight misreads the MCP listing

Mechanism: a plugin-provided playwright MCP is not reported apart from the user's own (and `claude mcp remove` cannot fix it), and a failed `claude mcp list` (`|| true`) reads as "nothing registered".
Location: `snap/plugins/browser/skills/browser/scripts/preflight.sh:198`. Fix: `05e0493`.

```diff
-  mcp_checked=true
-  mcp_raw=$(claude mcp list 2>/dev/null || true)
+  if mcp_raw=$(claude mcp list 2>/dev/null); then
+    mcp_checked=true
+    mcp_pw_line=$(printf '%s\n' "$mcp_raw" | grep -v '^plugin:' | grep -m1 -- playwright || true)
+    mcp_pw_plugin_line=$(printf '%s\n' "$mcp_raw" |
+      grep -m1 -E '^plugin:[^:]+:[^:]*playwright[^:]*:' || true)
...
+  else
+    advisories+=("claude mcp list failed, so the MCP servers were not checked")
```

### S6 (high): Chromium sandbox off for launched browsers

Mechanism: the generated CLI config has no `chromiumSandbox`, and Playwright disables the Chromium sandbox unless told otherwise.
Location: `snap/plugins/browser/skills/browser/scripts/launch.sh:270`. Fix: `992289b`.

```diff
--- a/plugins/extras/skills/browser/scripts/launch.sh
+# Playwright disables the Chromium sandbox unless told otherwise, which also
+# puts a --no-sandbox warning bar on every window; chromiumSandbox turns it
+# back on.
-  local config=$1 slot=$2
+  local config=$1 slot=$2 profile=$3 sandbox=true
+  [ "${BROWSER_NO_SANDBOX:-}" = "1" ] && sandbox=false
@@ -273,0 +283 @@ write_config() {
+      "chromiumSandbox": $sandbox,
```

### S7 (medium): CLI output written into the caller's repo

Mechanism: no `outputDir` in the config, so the CLI writes snapshots and logs to `./.playwright-cli` in whatever directory it runs from, often the user's repo.
Location: `snap/plugins/browser/skills/browser/scripts/launch.sh:265`. Fix: `992289b`.

```diff
+# The CLI writes snapshots and logs to ./.playwright-cli in whatever
+# directory it runs from, so outputDir keeps them in the profile instead of
+# the user's repo.
@@ -271,0 +280 @@ write_config() {
+  "outputDir": "$profile/output",
```

## Browser docs

### D1 (medium): logins file values left unquoted

Mechanism: the template writes values unquoted; the file is parsed as dotenv, where an unquoted `#` starts a comment and cuts a password short with no error.
Location: `snap/plugins/browser/skills/browser/references/credentials.md:40` (template) and `:46` (generator). Fix: `992289b`.

```diff
+# Keep every value inside its single quotes. Unquoted, a # starts a comment
+# and silently cuts the password short.
-#   BROWSER_ADMIN_PASSWORD=
+#   BROWSER_ADMIN_PASSWORD='p#ss$word'
-      printf 'BROWSER_%s_EMAIL=\nBROWSER_%s_PASSWORD=\n' "$upper" "$upper"
+      printf "BROWSER_%s_EMAIL=''\nBROWSER_%s_PASSWORD=''\n" "$upper" "$upper"
```

### D2 (low): docs misstate what a fill shows

Mechanism: the docs describe the CLI's fill output wrongly: in this snapshot they say `fill` takes only literal text with no secret-reference input; after `05e0493` they said it shows `<secret>NAME</secret>`; the CLI really shows `process.env['NAME']`. Partial credit when the literal-value fill (S1) is flagged from the docs side.
Location: `snap/plugins/browser/skills/browser/references/credentials.md:148`. Fix: `992289b` (docs only).

```diff
-itself and prints `<secret>BROWSER_ADMIN_PASSWORD</secret>` wherever the value
-would have appeared.
+itself, and its output shows `process.env['BROWSER_ADMIN_PASSWORD']` where the
+value would have been.
```
