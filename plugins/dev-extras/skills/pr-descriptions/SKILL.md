---
name: pr-descriptions
description: Write clear, skimmable pull-request / merge-request descriptions in a consistent house style. Use whenever drafting, rewriting, or reviewing a PR or MR description / summary for reviewers — title and the author's own note, a short intro, real before/after sample tables, bold-led bullets for a busy reader, diagrams for changed flows, a file map only when it earns its fold, and the auto-refresh markers. Platform-agnostic; covers the description itself, not git-host CLI mechanics.
---

# Writing PR / MR descriptions (house style)

Write for a human reviewer skimming the page, not a changelog. Lead with the picture,
then **show the change instead of describing it** — a table of real before/after samples
carries more than any paragraph about what the code now does. "The description" below
means a GitHub PR or a GitLab MR alike.

## Shape

- **Title heading** — a `## Heading` naming the change.
- **Author's note** — the author's own words on what the change is for, quoted and signed
  under the title. See below.
- **Short prose intro** — one or two sentences on _what changed and why_, with the key
  idea in **bold**. Announce the change; keep flag names and inline code out of here.
- **A callout** for anything a reviewer must not miss (a coupled PR in another repo, a
  data migration, a breaking change) — an alert such as `> [!warning]` on its own line,
  content on the following `>` lines. Omit it when there's nothing to flag.
- **A sample table** whenever the change alters what something renders, returns or
  stores. This is the part most descriptions are missing; see below.
- **Bold-led bullets** — each a small header then **one short sentence**, e.g.
  "**Simpler pagination** — reads newline-delimited output instead of hand-stitched
  pages". Describe the effect ("~20 lines → 2"), not the line-by-line diff.
- **A diagram** when the change alters a flow: steps, their order, or a decision that
  sends work one way or another. See below.
- **A collapsed file map** — only for five or more files, and only when each entry tells
  the reviewer something the diff view doesn't. See below.

## Author's note

A few words from the human author about what the whole change is for, quoted directly
under the title and signed with their `git config user.name`:

```markdown
## <Title>

> <the author's own words, verbatim>
>
> — <git config user.name>
```

- **Ask once, when you first write the description.** If there is no note yet, ask with
  AskUserQuestion, e.g. "Want to add a line in your own words about what this is for?",
  and offer a skip. A skip means no note, and you don't ask again.
- **Never write it yourself.** Use the answer exactly as given: no rewording, shortening
  or fixing. When you rewrite the description later, keep the note byte-for-byte.

## Write for a busy reader

A reviewer reads a dozen of these a day. Every bullet is one plain sentence, about 20
words at most, saying what is different now.

- **The result, not the work.** How it was built, checked or researched stays out.
- **No reasons unless one prevents a wrong review comment.** Mechanisms, trade-offs and
  rejected options go in the code or the commit message.
- **Plain words.** Name the thing the reader knows, not the internal term for it.
- **At most five bullets; one is fine for a small change.** Housekeeping such as an
  updated pointer or a rename is not a bullet.
- **Say each thing once.** A bullet that repeats a table row or a diagram goes.

Too much: "**Sample tables:** a new section asking for one row per representative
case, including the input that deliberately does not change, with every cell produced
by running the real helper rather than written from memory."

Enough: "**Sample tables:** show real before/after values, including one that stays
the same."

## Show the change: sample tables

For anything that alters how a value renders, one row per representative case beats a
paragraph:

| Stored value | Before | After |
| --- | --- | --- |
| `1234.5` | `1234.5` | `1 234,5` |
| `ABC-1234` | `ABC-1234` | `ABC-1234` |

- **Three to five rows, a few words per cell.** One row per kind of change, not per
  test case.
- **Include the input that deliberately does _not_ change.** That is where a reviewer
  suspects a bug, and the identical row is what closes the question.
- **Produce every cell by executing the real helper** and paste what it printed. Never
  hand-write an expected output — a wrong cell is worse than no table.
- **Drop a row you cannot show honestly** rather than guess at it, such as an output
  containing a non-breaking space or another invisible character.

When the same shape repeats — surface × helper, option × attribute, state × behaviour —
collapse the bullets into a table too. It skims faster and makes a missing cell visible.

## The file map that earns its fold

**Skip it below five files** — the diff view already lists the paths, and a bare list goes
stale on the next push. What makes the fold worth opening is a short note beside each
entry: what the file does now, often against what it did before.

- **Say something the path doesn't, in one line.** "Updated the formatter" adds nothing;
  "now reads the locale instead of a hard-coded `.`" does.
- **Group related files.** Where a whole directory got the same treatment, that is one
  entry naming the group.
- **Keep it in `<details>`** with an emoji + bold summary. Inline code belongs here, not
  in the prose above.

## Diagrams

**Reach for one whenever the change alters a flow** — steps, their order, or a decision
that sends work one way or another. A small `flowchart` of the new flow, with the changed
step highlighted, replaces the bullets that would describe it; so does an **invariant**
prose states weakly. A restatement of the bullets in boxes is worse than nothing. GitHub
and GitLab both render a fenced `mermaid` block.

- **Few nodes, no convergence.** A node everything funnels back into creates crossing
  lines, and renderers shrink node-heavy graphs until the text is unreadable.
- **Mind the shape subgraphs produce.** Under `flowchart LR`, two disconnected subgraphs
  stack vertically. Consolidate them into one chain, or use `flowchart TB` at the top
  level with `direction LR` inside each to set them side by side.
- **Colour carries meaning.** Group nodes with `classDef` (`fill` / `stroke` / `color`);
  it degrades to plain boxes if a renderer ignores it.
- **Node text is always centred.** Left-aligned tabular content belongs in a table.
- **Control box width** when labels wrap awkwardly:
  `%%{init: {"flowchart": {"wrappingWidth": 320}}}%%`.

## Skeleton

```markdown
## <Title naming the change>

> <The author's own words, or drop the quote if they skipped.>
>
> — <git config user.name>

<!-- mr-desc:start sha=<pushed HEAD> hash=<git blob hash of the block> -->
<One or two sentences; **bold** the key idea — what changed and why.>

> [!note]
> <Anything the reviewer must notice, or drop the callout entirely.>

| <Input> | Before | After |
| --- | --- | --- |
| <real value> | <real output> | <real output> |

- **<Header>** — <one line, effect-focused>.

<details><summary>📁 <b>Files touched</b></summary>

- `path/to/file` — <what changed, in a line the diff view can't give>.

</details>
<!-- mr-desc:end -->
```

## Auto-refreshed block

After every `git push` Claude makes, this plugin's hook rewrites only the text between the
two HTML comments in the skeleton, which neither platform renders. It works on GitHub PRs
(via `gh`) and GitLab MRs (via `glab`), picking the platform from the remote URL.

- **Everything outside the markers is never touched.** Keep a review bot's summary, test
  notes and anything hand-kept there. Callouts go inside.
- **The title and the author's note sit above the block.** The refresh never sees or
  rewrites them.
- **No markers, no refresh.** A description written without them is left alone.
- **A hand edit inside the block pauses it.** When the block no longer matches `hash=`,
  the refresh skips it; to keep an edit, move it outside the markers. To overwrite it
  anyway, run `"${CLAUDE_PLUGIN_ROOT}/hooks/refresh-mr-description.sh" run --force` from
  the repo.
- **Don't hand-edit the start line.** A malformed marker stops the refresh.
- **The refresh sees only this file, the current block and the diff** against the target
  branch, and keeps wording that is still true.

## Formatting that fails silently

- **Alerts must be lowercase.** GitLab renders only `> [!note]`, `> [!tip]`,
  `> [!important]`, `> [!warning]`, `> [!caution]`; uppercase degrades to a plain quote.
  GitHub is case-insensitive, so lowercase is the form that renders on both. Alerts don't
  render when indented or nested inside a list.
- **Write the body to a file, never inline.** The shell escapes `!` to `\!` and mangles
  backticks and `$`, so an alert becomes `[\!note]` and renders raw.
- **Write cross-references to another repo as full links.** A bare `#123` or `!123`
  resolves against the repo the description lives in.

## Rewriting an existing description

- **Save the current description first.** It is the only way back.
- **Keep a generated section byte-for-byte.** Where a review bot has written a block into
  the description, leave it exactly as it stands and put your prose above it.
- **Re-read the live description after writing.** The command's return value is not proof
  of what was stored.
