---
name: writing-style-guide
description: "Dawid Nitka's personal writing style guide. Use this skill whenever writing, drafting, editing, or reviewing any text that will be read by humans - including articles, blog posts, documentation, README files, PR descriptions, technical write-ups, Slack messages, emails, proposals, or any prose longer than a couple of sentences. Also trigger when the user asks to 'write like me', 'use my voice', 'check my style', 'edit for voice', or mentions their writing style. Even for commit messages or code comments that need personality, consult this skill. If in doubt whether a writing task needs the style guide - use it anyway."
dependencies:
  - humanizer
---

# Writing Style Guide - Dawid Nitka

Apply this guide whenever producing or editing text that will be read by humans. The guide defines voice, structure, sentence-level preferences, signature moves, anti-patterns, and revision standards.

For the full style guide with examples, positive/negative samples, and revision checklist, read:

- `references/style-guide.md` - Complete style guide
- `references/prompt-templates.md` - Reusable prompt templates for common writing tasks

## Dependency: humanizer

Generic AI-tell removal (em-dashes, rule-of-three, "not X but Y", filler, hedging, sycophantic openers, inflated symbolism, vague attributions, staccato drama, "Here's the thing:" openers, etc.) is owned by the **`humanizer` skill**, vendored in this plugin at `base-setup:skills/humanizer/` (declared under `dependencies` in the frontmatter). Run humanizer **first** for that pass, then apply this guide to layer Dawid's voice on top.

This guide carries only what humanizer does **not**: Dawid's voice, structure, non-native fixes, and a few deliberate overrides (Oxford comma, dash fallback) below.

## Quick Reference (always apply these)

### Voice

- Direct and brave. Say the uncomfortable thing.
- Concrete before abstract. Lead with specifics.
- Compressed humor. Personality is structural, not decorative.
- Practitioner's authority. Write from inside the work.
- Honest about uncertainty. Show your thinking.
- Lumpy, not balanced. Default to loaded run-ons with parentheticals; drop the occasional rough fragment. Avoid staccato short pairs - they read as machine-tuned.

### Personality Dial (context-dependent)

- **Internal docs / coding standards**: Maximum personality (escalating humor, deadpan code comments)
- **Opinion/argument pieces**: High (direct, occasionally cheeky, grounded in experience)
- **Thought leadership essays**: Moderate (structured, personality in openings/transitions/endings)
- **Tutorials / technical docs**: Restrained (clear, personality only in section openers and asides)
- **Commit messages / PRs**: Minimal but human (no corporate-speak, keep it real)

### Dawid-Specific Tells & Overrides (humanizer doesn't cover these)

Generic AI-tells (rule-of-three, "not X but Y", colon-reveal "Here's the thing:", uniform polish/staccato, "evolving landscape", "it's worth noting", hollow transitions, fake profundity, sycophantic openers) are humanizer's job - don't duplicate them here. This guide adds only:

- **Balanced antithesis** - "The vision is there. The org move is lagging." / "The willing are there. It's the enablement that's missing." Dawid's #1 structural tell, a disguised "not X, but Y" used as the default beat. Break the symmetry: merge into one sentence or leave one side loaded and rough.
- **Em-dash override**: hard ban on `—`. First preference - restructure to avoid the dash. Fallback only: `-` (hyphen with spaces). humanizer also kills em-dashes but replaces with comma/period; Dawid prefers the spaced hyphen.
- **Oxford comma before "and"**: drop it. "red, green and blue", not "red, green, and blue". humanizer has no rule on this.

### Voice Fingerprints (use these - they make text unmistakably Dawid)

- **"Somehow" / "Anyway" / "Nevertheless"** as connective hinges. ("Somehow I still believe...")
- **Ventriloquize the skeptic** - act out the dumb inner monologue in their voice. ("I'm skeptical, but I will try. I tried, didn't work that well, I was right.")
- **Scare-quote sarcasm** - quote the dumb thing flatly, let it hang. ("'just use our Google login' doesn't cut it")
- **Self-interrupting cutoffs** - bail on your own rant. ("Ok enough whining!")
- **Decision-handback endings** - hand the ball back, never summarize. ("up to you", "WDYT? Have I missed something?")
- **Vivid, slightly absurd metaphor.** ("It's like contact with an alien - maybe it will kill you but you still want to touch it.")
- **The absurd range.** ("anything between 2 days and 'impossible to deliver in this shape'")
- **Emoji as tone-markers in DMs** (`:wink:`, `:smile:`, `:man-shrugging:`). Not in articles.

### Non-Native English Fixes

- Check articles (a/the) before countable nouns
- Watch for Germanic word order (verb-final, misplaced adverbs)
- Fix preposition calques ("from my side" -> "on my end")
- When a sentence is technically correct but flat, suggest more idiomatic alternatives
- **Fix every true error in all registers (DMs too) and briefly explain why**, so Dawid learns the pattern. Example: "schoolings" -> "trainings/courses" (calque of German _Schulung_).
- **Preserve voice, not mistakes.** The run-ons, "somehow", the sarcasm stay. Grammar errors don't.

### Parenthetical Check

Dawid leans on parentheses and sometimes overuses them to bolt a second sentence onto the first. For each parenthetical:

- Smuggled full thought? Drop the parens - make it its own sentence, or cut it.
- Genuine mid-stream aside, not worth its own sentence? Keep it.

Flag when a draft is leaning on parens to staple sentences together.

### Economy Rule

Cut words that don't earn their place. Exception: words that create spoken rhythm are worth keeping ("Well... not exactly" - the "Well" is unnecessary for meaning but essential for voice).

### Key Instruction

Don't smooth out personality. Dawid's raw voice is the raw material. Your job is to give it structure and fluency, not to make it "professional." When in doubt, cut words rather than add them.
