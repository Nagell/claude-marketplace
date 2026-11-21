---
name: pr-descriptions
description: House style for writing a merge request or pull request description that a busy reviewer can skim. Use whenever you write, rewrite, draft or review an MR/PR description on GitLab or GitHub, including the title heading, the author's note, sample tables, diagrams, the file map and the auto-refresh markers.
---

# Writing the MR/PR description (house style)

Write for a human reviewer skimming the page, not a changelog. Lead with the picture,
then **show the change instead of describing it**: a table of real before/after samples
carries more than any paragraph about what the code now does.

## Shape

- **Title heading**: a `## Heading` naming the change.
- **Author's note**: the author's own words on what the change is for, quoted and signed
  under the title. See below.
- **Short prose intro**: one or two sentences on _what changed and why_, with the key
  idea in **bold**. Announce the change; keep flag names and inline code out of here.
- **A callout** for anything a reviewer must not miss (a coupled MR in another repo, a
  data migration, a breaking change), as a lowercase alert (see Formatting). Omit it when
  there's nothing to flag.
- **A sample table** whenever the change alters what something renders, returns or
  stores. This is the part most descriptions are missing; see below.
- **Bold-led bullets**: each a small header then **one short sentence**, e.g.
  "**Simpler pagination** — reads newline-delimited output instead of hand-stitched
  pages". Describe the effect ("~20 lines → 2"), not the line-by-line diff.
- **A diagram** when the change alters a flow: steps, their order, or a decision that
  sends work one way or another. See below.
- **A collapsed file map**, only for five or more files, and only when each entry tells
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

- **Ask once, when you first write the description.** Offer a skip. A skip means no note,
  and you don't ask again.
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
- **Produce every cell by executing the real code.** Run the formatter, the serializer,
  the component; paste what it printed. A wrong cell is worse than no table.
- **Drop a row you cannot show honestly** rather than guess at it, such as an output
  with a non-breaking space or another invisible character.

## A table beats repeated bullets

The moment the same shape repeats (surface × helper, option × attribute, state ×
behaviour), collapse the bullets into a table. It skims faster, never wraps mid-phrase,
and makes a missing cell visible. Keep a "why" only where a reviewer would otherwise
file deliberate behaviour as a bug.

## The file map that earns its fold

**Skip it below five files**: the diff view is enough. A list of paths duplicates that
view and goes stale on the next push. What makes the fold worth opening is a short note
beside each entry that the diff view can't give: what the file does now, often against
what it did before.

- **Say something the path doesn't, in one line.** "Updated the formatter" adds
  nothing; "now reads the locale instead of a hard-coded `.`" does.
- **Group related files** rather than listing every one flat.
- **Keep it in `<details>`** with an emoji + bold summary. Inline code belongs here, not
  in the prose above.

```markdown
<details><summary>📁 <b>Files touched</b></summary>

- `app/utils/format.ts` — hard-coded the `.` separator; now reads the active locale.
- **Consultation widgets** (`app/components/consultation/*.vue`) — call the shared
  helper instead of formatting numbers inline.

</details>
```

## Diagrams

**Reach for one whenever the change alters a flow**: steps, their order, or a decision
that sends work one way or another. A small `flowchart` of the new flow, with the changed
step highlighted, replaces the bullets that would describe it. The same goes for an
invariant that prose states weakly. A restatement of the bullets in boxes is worse than
nothing. Both GitLab and GitHub render a fenced `mermaid` block.

- **Few nodes, no convergence.** A node everything funnels back into creates crossing
  lines, and renderers shrink node-heavy graphs until the text is unreadable.
- **Mind the shape subgraphs produce.** Under `flowchart LR`, two disconnected subgraphs
  stack vertically. Consolidate them into one chain, or use `flowchart TB` at the top
  with `direction LR` inside each to set them side by side.
- **Colour carries meaning.** Use `classDef` (`fill` / `stroke` / `color`) to group
  nodes so the rule reads at a glance.
- **You cannot left-align node text**, so a table wins for left-aligned content.
- **Control box width** when labels wrap awkwardly:
  `%%{init: {"flowchart": {"wrappingWidth": 320}}}%%`.

## Skeleton

```markdown
## <Title naming the change>

> <The author's own words, or drop the quote if they skipped.>
>
> — <git config user.name>

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
```

## Auto-refreshed block

After each push, `hooks/refresh-mr-description.sh` rewrites the text between two HTML
comments, which neither GitLab nor GitHub renders. It works on GitHub PRs (via `gh`) and
GitLab MRs (via `glab`), picking the platform from the remote URL:

```markdown
<!-- mr-desc:start sha=<full HEAD sha> hash=<git blob hash of the block> -->
...the description below the title and note, in the house style above...
<!-- mr-desc:end -->
```

- **Everything outside the markers is never touched.** Put review-bot summaries, test
  notes and anything hand-kept there, and keep a bot's block byte-for-byte. The alerts
  the house style asks for go inside.
- **The title and the author's note sit above the block.** The refresh never sees or
  rewrites them.
- **No markers, no refresh.** To add them to an existing description, run the script with
  `run --adopt`, which puts the start marker below the title and the note.
- **A hand edit inside the block pauses it.** When the block no longer matches `hash=`,
  the refresh skips it until `run --force`. To keep an edit, move it outside.
- **Don't hand-edit the start line.** The script refuses a malformed marker and says so.

## Formatting

- **Alerts must be lowercase**: `> [!note]`, `> [!tip]`, `> [!important]`,
  `> [!warning]`, `> [!caution]`. GitLab renders only lowercase and degrades `[!NOTE]` to
  a plain quote; GitHub accepts either.
