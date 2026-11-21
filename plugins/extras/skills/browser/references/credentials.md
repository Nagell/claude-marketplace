# Logging in

A session profile keeps a login alive across restarts, so the question is only
what happens the *first* time — and whether the user wants a password on disk at
all. Ask, explain, and take no for an answer.

## The three routes

Offer all three. They are ordered by how little the credentials travel, not by
how convenient they are.

### 1. The user fills the file

Create the template, tell them the path, let them type the values in their own
editor. Nothing passes through the conversation.

The keys come from the names the user gave, so put those in `names` and let the
pairs be generated — hardcoding `admin` and `editor` would hand someone who
asked for `eu` and `us` a file to rename by hand, and preflight would report the
two logins they never wanted. Create the file only when it is absent: a plain
`>` empties one that already holds working logins, and re-running setup is
exactly when that happens.

```bash
names="eu us"                   # lowercase, as the user named them
umask 077
if [ -e ~/.claude/browser-users.env ]; then
  echo "Already there - add keys by hand rather than overwriting."
else
  {
    cat <<'ENV'
# Browser logins.
# Key shape:  BROWSER_<NAME>_EMAIL  /  BROWSER_<NAME>_PASSWORD
#   <NAME> is uppercase letters and digits, lowercased for --login:
#   BROWSER_ADMIN_EMAIL  ->  scripts/launch.sh --login admin
#   An underscore inside the name hides the login from preflight.
#
# Keep every value inside its single quotes. Unquoted, a # starts a comment
# and silently cuts the password short.
#
# Two logins look like:
#   BROWSER_ADMIN_EMAIL='admin@example.com'
#   BROWSER_ADMIN_PASSWORD='p#ss$word'
#   BROWSER_EDITOR_EMAIL='editor@example.com'
#   BROWSER_EDITOR_PASSWORD='...'
ENV
    for n in $names; do
      upper=$(printf '%s' "$n" | tr '[:lower:]' '[:upper:]')
      printf "BROWSER_%s_EMAIL=''\nBROWSER_%s_PASSWORD=''\n" "$upper" "$upper"
    done
  } > ~/.claude/browser-users.env
fi
# Outside the branch: `umask` only covers a file it creates, so one that was
# already there keeps whatever mode it had.
chmod 600 ~/.claude/browser-users.env
```

A machine whose safety hooks stop a shell writing `.env` files will refuse that
write. Produce the same file with your file-editing tool and run the
`chmod 600` on its own — the mode is not optional either way.

Then say: "Filled in? I'll pick it up on the next launch."

### 2. The user tells you here

Quick, and the values land in the transcript. **Say that before they type**, not
after. If they still prefer it, write the file as above with the values in
place, `chmod 600`, and do not echo them back. The key names are yours to pick
here too, so ask what to call each login exactly as in route 1.

### 3. Nobody stores anything

Leave the browser on the login screen and let the user sign in. The session
profile keeps them signed in from then on, and no password exists in any file.

This is a real answer. Someone who does not want a plaintext password anywhere
is not being difficult, and a one-off login is a small price. Present it that
way.

## Asking again

If the user declines, ask again on a later run when credentials are still
missing — circumstances change and the offer costs one line. If they say never,
that sticks: record it and stop offering.

```bash
touch ~/.claude/browser-users.never-ask
```

Check for that file before offering.

## Where it lives, and why

`~/.claude/browser-users.env`, mode `600`. `BROWSER_CREDENTIALS` points
preflight at a different path.

- Outside any repository, so it cannot be committed by accident.
- In `~/.claude` but outside the plugin cache, so it survives plugin updates.
- Same path on Linux, macOS and WSL, which is more than can be said for a
  keychain.

Never write credentials into a repository file, a task list, or a log. Never
print a stored value back to the user — they already have it.

## More than one login

Ask how many before the file is written, not after — `SKILL.md` folds it into
the same question as where the credentials go. More than one, and ask what to
call them as well: you pick the key names under both storing routes, and a
rename by hand afterwards is what this avoids.

Several users at once is the normal case for parallel work: two agents sharing
one account fight over that account's saved state, notifications and
preferences. Per-user state such as an active organisation or workspace bites
first where the application stores it against the user and not the browser:
switch it in one session and every other session on that account follows.

```
BROWSER_ADMIN_EMAIL=…
BROWSER_ADMIN_PASSWORD=…
BROWSER_EDITOR_EMAIL=…
BROWSER_EDITOR_PASSWORD=…
BROWSER_VIEWER_EMAIL=…
BROWSER_VIEWER_PASSWORD=…
```

The key shape is `BROWSER_<NAME>_EMAIL` / `BROWSER_<NAME>_PASSWORD`; `<NAME>`
uppercase letters and digits, no underscore inside it. Preflight lists what it
found under `credentials.logins` — a name with an underscore in it matches
nothing there and disappears without an error, so the login looks unstored.

```bash
bash scripts/launch.sh --session admin-work --login admin --allow-install
```

If a requested name is not there, list the ones that are and ask which to use —
or whether to add it. Do not guess at a near match; logging in as the wrong user
wastes more time than the question.

## Handing credentials to the browser

**Playwright MCP** takes the file directly and fills fields without the values
entering your context:

```bash
claude mcp add -s user playwright \
  -- npx -y @playwright/mcp@latest --sandbox \
     --secrets="$HOME/.claude/browser-users.env"
```

**The CLI fills by key name.** The scripts hand the CLI the same file
(`PLAYWRIGHT_MCP_SECRETS_FILE`, set in `scripts/common.sh` whenever the file
exists), so `fill` takes the key name, not the value. The CLI looks the value up
itself, and its output shows `process.env['BROWSER_ADMIN_PASSWORD']` where the
value would have been. The value stays out of the conversation, out of the
CLI's output files and out of `ps`. The file is parsed as dotenv, not run as
shell: a `$` stays a `$`, but an unquoted `#` starts a comment and cuts the
value short without an error, so every value goes in single quotes.

```bash
S=admin-work                    # the session name you launched with
bash "${CLAUDE_SKILL_DIR}/scripts/pw.sh" -s="$S" fill e2 BROWSER_ADMIN_EMAIL
bash "${CLAUDE_SKILL_DIR}/scripts/pw.sh" -s="$S" fill e3 BROWSER_ADMIN_PASSWORD
```

- The session reads the file when it starts. A session launched before the file
  existed or was filled in has to be stopped and launched again.
- A key the file does not have is typed as literal text, which is the key
  name. A login that fails right after a fill by name usually means a
  misspelled key.
- Never pass the value itself (`"$BROWSER_ADMIN_PASSWORD"`): `fill` echoes
  literal text back as generated code, which puts the password in the
  transcript.
- A login that fails although the key is right usually means an unquoted value
  with a `#` in it. Ask the user to quote it; never read the file to check.
- Verified on CLI 0.1.23 (WSL): neither value appeared in the tool output or
  the files it writes. If a later CLI ever shows a value, stop, tell the user,
  and drive the login through Playwright MCP with `--secrets` instead.

**Saved session state** is the third option and a complement, not a store. It
holds no password, but it is a live session token — anyone who can read the file
is logged in, and `state-save` does not restrict the mode itself.

```bash
install -d -m 700 ~/.cache/claude-browser
umask 077
bash "${CLAUDE_SKILL_DIR}/scripts/pw.sh" -s="$S" state-save ~/.cache/claude-browser/auth-admin.json
chmod 600 ~/.cache/claude-browser/auth-admin.json
```

## When the login fails

Say which login name you used and that the credentials appear wrong. Do not
retry a password in a loop — most applications lock the account after a few
attempts, and locking a shared test user blocks everyone else too.
