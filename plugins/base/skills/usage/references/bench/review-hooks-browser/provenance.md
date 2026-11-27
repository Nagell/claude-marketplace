# Provenance

Each snapshot file under `snap/` and the commit of this repository (github.com/Nagell/claude-marketplace) whose copy of the file is byte-identical (checked with `git hash-object`). The snapshot keeps the repository paths of that time: the browser skill was later moved from `plugins/browser/` to `plugins/extras/skills/browser/`.

| File | Source commit | Note |
|---|---|---|
| `plugins/base/hooks/hooks.json` | `8ac9b24` | the commit that wrote this content, which stays until the fixes `0933c9f`, `fd405f0`, `5911c75` |
| `plugins/base/hooks/post-edit-format.sh` | `8ac9b24` | as above |
| `plugins/base/hooks/safety-guards.sh` | `8ac9b24` | as above |
| `plugins/extras/hooks/hooks.json` | `8ac9b24` | as above |
| `plugins/extras/hooks/refresh-mr-description.sh` | `8ac9b24` | as above |
| `plugins/coding-tutor/hooks/hooks.json` | `0dc4655` | |
| `plugins/coding-tutor/hooks/post-commit-nudge.sh` | `0dc4655` | |
| `plugins/browser/.claude-plugin/plugin.json` | `0dc4655` | parent of fix `05e0493` |
| `plugins/browser/README.md` | `0dc4655` | |
| `plugins/browser/skills/browser/SKILL.md` | `0dc4655` | |
| `plugins/browser/skills/browser/references/attach-chrome.md` | `0dc4655` | |
| `plugins/browser/skills/browser/references/credentials.md` | `0dc4655` | |
| `plugins/browser/skills/browser/references/mcp-servers.md` | `0dc4655` | |
| `plugins/browser/skills/browser/references/parallel.md` | `0dc4655` | |
| `plugins/browser/skills/browser/references/troubleshooting.md` | `0dc4655` | |
| `plugins/browser/skills/browser/scripts/attach-chrome.sh` | `0dc4655` | |
| `plugins/browser/skills/browser/scripts/common.sh` | `0dc4655` | |
| `plugins/browser/skills/browser/scripts/launch.sh` | `0dc4655` | |
| `plugins/browser/skills/browser/scripts/preflight.sh` | `0dc4655` | |
| `plugins/browser/skills/browser/scripts/pw.sh` | `0dc4655` | |

20 files, 2,905 lines. `history/` holds the briefs of runs B to F and H (`brief.md`, `brief-D-addendum.md`; H reused D's prompts); G and I used review-mr's `agent-brief.md` of PR #251, which stays in this repository's history. No setup uses them.

## Notes on the answer key

`answer-key.md` is not edited for these, because its hash is part of every stored result and an edit would mark them not comparable:

- The key is the chosen 14 bugs, not every defect in the snapshot. The snapshot has more (the `rm` and `.env` guard gaps fixed in `10fdc5b`, the `npx` probes fixed in `f8ce2b0`). A report that flags them scores as real extra findings, the same for every model.
- D2: the snapshot's sentence ("`fill` takes only literal text") was changed by `05e0493`; `992289b` fixed the wording that `05e0493` wrote. The key credits `992289b`.
- S1: the missing `export PLAYWRIGHT_MCP_SECRETS_FILE` belongs after `scripts/common.sh:13`; the key names `:12`.
