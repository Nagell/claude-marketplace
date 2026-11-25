# Provenance

Each snapshot file under `snap/` and the commit of this repository (github.com/Nagell/claude-marketplace) whose copy of the file is byte-identical (checked with `git hash-object`). The snapshot keeps the repository paths of that time: the browser skill was later moved from `plugins/browser/` to `plugins/extras/skills/browser/`.

| File | Source commit | Note |
|---|---|---|
| `plugins/base/hooks/hooks.json` | `8ac9b24` | newest commit with this content; parent line of fixes `0933c9f`, `fd405f0`, `5911c75` |
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

20 files, 2,905 lines. `history/` holds the briefs of runs B to H (`brief.md`, `brief-D-addendum.md`); they are not used by any setup.
