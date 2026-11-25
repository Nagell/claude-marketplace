# Addendum for this run (read after brief.md)

## Keep your context small
You own a SMALL slice. Read your slice's files whole, but do not read other files whole: use `grep -n` / `sed -n 'a,bp'` for the specific lines you need from elsewhere. Do not re-read a file you already read. Keep tool output short (pipe through head, print only what you need).

## Extra lens: what the code does NOT set (apply it to every file in your slice)
Many real bugs are absent settings, not wrong lines. For every external tool this code runs or configures (Playwright CLI and its JSON config, Chromium/Chrome, npm/npx, git, curl, gh/glab, python, shells):
1. List the options/flags/config keys the code passes.
2. Ask which important options it does NOT pass, and what the tool's DEFAULT is for each (security: sandboxing, where output/logs/caches are written, network/proxy, auto-install/download, permissions; behaviour: what happens on error, what is persisted where).
3. If unsure about a default or about what a tool can or cannot do, check the tool's own documentation or source (WebFetch/WebSearch, or `npx --yes` is NOT allowed; read docs on the web or local node_modules only). Do NOT trust this repo's own docs about what a tool can or cannot do: verify the claim against the tool.
4. Report an unsafe or surprising default that the code silently inherits as a finding, with the default cited.

Also look for errors that are swallowed (`|| true`, `2>/dev/null`, empty fallbacks) and turn a failure into a misleading "nothing there" result, and for checks that wrongly BLOCK legitimate input (false positives), not only for things that get through.
