# The brief for the run-it agent

Paste this into the run-it agent's prompt after the "Where you are" part of
`agent-brief.md` (paths, `RUN_TMP`, read-only rules). It replaces that brief's
lens and slice parts. The run-it agent does not read for bugs. It runs the
changed code and compares what happens with what the docs promise.

---

## Your job

Run the runnable things this MR adds or changes: `<list of scripts, CLIs,
hooks and skill scripts, with their paths>`. For each one, collect every
promise made about it in the docs, its `--help` and the MR description. Then
run it in a throwaway environment and record whether the behaviour matches.

## Build the throwaway environment first

Everything lives under one root you create in the run's temp dir:

```bash
R=$(mktemp -d -p "$RUN_TMP" runit.XXXXXX)
mkdir -p "$R/home" "$R/tmp" "$R/xdg/config" "$R/xdg/cache" "$R/xdg/data" \
  "$R/xdg/state" "$R/stubs" "$R/out"
```

- **Clean environment.** Run every command under `env -i` with only what it
  needs: `HOME="$R/home"`, `TMPDIR="$R/tmp"`, `XDG_CONFIG_HOME`,
  `XDG_CACHE_HOME`, `XDG_DATA_HOME` and `XDG_STATE_HOME` under `$R/xdg`, and a
  short `PATH="$R/stubs:/usr/bin:/bin"`. A browser profile, if the code starts
  a browser, points into `$R` too. The real environment must not leak in.
- **Fake credentials.** Any token, key or password the code wants gets an
  obviously fake value, such as `GITLAB_TOKEN=fake-token-for-review`. Never a
  real one, never one read from the real `HOME`.
- **Stubs first on `PATH`.** Put stub `git`, `gh`, `glab`, `curl`, `npx`,
  `npm`, `pnpm`, `wget` and any other tool that would touch the network or a
  remote into `$R/stubs`. Each stub appends its arguments to
  `$R/out/calls.log` and prints canned output that fits the case you test:

  ```bash
  printf '#!/bin/sh\necho "$0 $*" >> %s/out/calls.log\necho "{}"\n' "$R" \
    > "$R/stubs/curl"; chmod +x "$R/stubs/curl"
  ```

  A stub that needs real local behaviour (`git` on a throwaway repo in `$R`)
  may call the real binary by absolute path, but never against a real remote
  or the review checkout.
- **Copies, not the checkout.** Copy what you run into `$R` (or run it by
  absolute path from the reviews worktree with `$R` as the working directory).
  Never write into the reviews worktree or the primary checkout.

## Never

- push, open an MR or post anything
- create a real push token or any file that a guard hook reads as permission
  (such as `.claude-push-token`) outside `$R`
- use a real credential, or read one from the real `HOME`
- call a real network service: answer it with a stub and record the arguments.
  Run the code under test with the network cut off, `unshare -rn <command>`,
  so a tool the stubs missed fails instead of reaching a server. Where
  `unshare` is not available, keep `/usr/bin` and `/bin` off that `PATH` and
  link in only the plain tools you need (`sh`, `cat`, `grep`, `sed` and the
  like), never `gh`, `glab`, `curl`, `wget`, `git`, `npm` or `npx`.
- install a package (`npm install`, `pip install`, `npx --yes` and the like)
- write outside `$R`, except the one report file below
- leave a process running

## Keep it small

The "Keep your context small" rules of the main brief apply. Every run writes
to a file in `$R/out`, and you `tail` or `grep` that file.

## What you report

Write the report to `<report path>` and reply with only that path. Writing
this one report file is required, and it is allowed: it is the only file you
write outside `$R`.

### 1. Promises versus behaviour

One row per promise, no exceptions:

```
| # | promise (source) | command run | what happened | result |
| 1 | "blocks git push without a token" (README.md:40) | `printf '{"tool_input":{"command":"git push"}}' \| hooks/guard.sh` | exit 2, "push blocked" | match |
| 2 | "--help lists --dry-run" (scripts/x.sh --help) | `scripts/x.sh --help` | no --dry-run line | mismatch |
| 3 | "works offline" (MR description) | not run | needs a real proxy | not run: why |
```

### 2. Findings

Each mismatch is a finding, with the same fields as in the main brief (id
`runit-<n>`, severity, `file:line`, mechanism, introduced or not, confidence).
Mark it measured, and quote the command and the output. A stub can mislead, so
say which stub answered and what it returned. Refutation still checks it.

Add a short **checked and found sound** list for the promises that held.

### 3. Leftovers

Delete `$R` before you reply, also when you stop early. Write the delete with
the folder's literal path, such as `rm -rf /tmp/claude-1000/.../runit.Ab12Cd`,
not `rm -rf "$R"`: a permission allow rule matches the command text, and it
cannot match a shell variable. The report's last line
is `Leftovers: none`, or each path you could not delete and why. If a guard
blocks the delete, list the path and do not work around the guard.
