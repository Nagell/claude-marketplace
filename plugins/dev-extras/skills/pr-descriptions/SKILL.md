---
name: pr-descriptions
description: Write clear, skimmable pull-request / merge-request descriptions in a consistent house style. Use whenever drafting, rewriting, or reviewing a PR or MR description / summary for reviewers — leading with the picture, bold-led bullets, a collapsed file map, tables over diagrams, and formatting that renders correctly on both GitHub and GitLab. Platform-agnostic; covers the description prose itself, not git-host CLI mechanics.
---

# Writing PR / MR descriptions (house style)

Write for a human reviewer skimming the page, not a changelog. Lead with the picture;
keep the mechanics collapsed. Works the same for a GitHub PR or a GitLab MR — "the
description" below means either.

## Shape

- **Title heading** — a `## Heading` naming the change.
- **Short prose intro** — one or two sentences on _what changed and why_, with the key
  idea in **bold**. Announce the change; keep flag names and inline code out of here.
- **A callout** for anything a reviewer must not miss (a coupled MR/PR in another repo, a
  data migration, a breaking change) — a lowercase alert (see formatting below). Omit it
  when there's nothing to flag.
- **Bold-led bullets** — each a small header then one tight line, e.g. "**Simpler
  pagination** — reads newline-delimited output instead of hand-stitched pages". Describe
  the effect ("~20 lines → 2"), not the line-by-line diff.
- **A collapsed file map** — a `<details>` block with an emoji + bold summary, one bullet
  per file leading with the `path/to/file` in code. Inline code belongs here, in the
  detail, not in the prose above.

**Prefer the simplest legible form.** Reach for a visual only when prose + bullets do not
carry the shape. For anything that is a matrix (options × attributes, format × helper,
state × behaviour), a **markdown table beats a diagram** — it is left-aligned, never wraps
mid-phrase, renders at full width, and skims faster than boxes.

## Diagrams

For genuine architecture / data flow / non-obvious control flow — several files that
depend on each other — add a Mermaid diagram of the shape (both GitHub and GitLab render a
fenced `mermaid` block); skip it for small, self-contained changes. When you do use one,
keep it legible:

- **Few nodes, no convergence.** A single node everything funnels back into creates
  crossing lines, and renderers shrink node-heavy graphs until the text is unreadable —
  fewer boxes render larger.
- **Colour carries meaning.** Use `classDef` (`fill` / `stroke` / `color`) to group nodes
  (e.g. green = new, grey = existing) so the rule reads at a glance; it degrades to plain
  boxes if a renderer ignores it.
- **You cannot left-align node text.** Mermaid centres labels and hosts strip the inline
  `style` / HTML needed to override it — another reason a table wins for left-aligned
  tabular content.
- **Control box width** when labels wrap awkwardly, with an init directive:
  `%%{init: {"flowchart": {"wrappingWidth": 320}}}%%`.

## Skeleton

```markdown
## <Title naming the change>

<One or two sentences; **bold** the key idea — what changed and why.>

> [!note]
> <Anything the reviewer must notice, or drop the callout entirely.>

- **<Header>** — <one line, effect-focused>.
- **<Header>** — <one line>.

<details><summary>📁 <b>Files touched</b></summary>

- `path/to/file` — what changed there.

</details>
```

## Formatting that renders on both GitHub and GitLab (both fail silently)

- **Alerts must be lowercase.** GitLab (GLFM, since 17.10) renders only `> [!note]`,
  `> [!tip]`, `> [!important]`, `> [!warning]`, `> [!caution]`. Uppercase `[!NOTE]`
  degrades to a plain quote on GitLab. GitHub is case-insensitive, so **lowercase is the
  one form that renders on both** — always use it. Syntax: `> [!warning]` on its own line,
  content on following `>` lines; add text after the tag for a custom title
  (`> [!warning] Data loss`). Alerts don't render when indented or nested inside a list.
- **Write the body to a file, never inline.** Pass the description via a file, not an
  inline `-m "...!..."`. The shell escapes `!` to `\!` and mangles backticks / `$`, so an
  alert becomes `[\!note]` and renders raw. Under zsh, even `--description "$(cat body.md)"`
  can re-trigger history expansion on `!`; the robust form is a tempfile read inside
  `bash -c 'set +H; ...'`.

  ```bash
  # GitHub
  gh pr create --title "..." --body-file body.md
  gh pr edit <number> --body-file body.md

  # GitLab
  glab mr update <iid> --description "$(cat body.md)"
  ```
