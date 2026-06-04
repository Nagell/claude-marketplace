---
name: writing-style-guide
description: "Dawid Nitka's personal writing style guide. Use this skill whenever writing, drafting, editing, or reviewing any text that will be read by humans - including articles, blog posts, documentation, README files, PR descriptions, technical write-ups, Slack messages, emails, proposals, or any prose longer than a couple of sentences. Also trigger when the user asks to 'write like me', 'use my voice', 'check my style', 'edit for voice', or mentions their writing style. Even for commit messages or code comments that need personality, consult this skill. If in doubt whether a writing task needs the style guide - use it anyway."
---

# Writing Style Guide - Dawid Nitka

Apply this guide whenever producing or editing text that will be read by humans. The guide defines voice, structure, sentence-level preferences, signature moves, anti-patterns, and revision standards.

For the full style guide with examples, positive/negative samples, and revision checklist, read:

- `references/style-guide.md` - Complete style guide
- `references/prompt-templates.md` - Reusable prompt templates for common writing tasks

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

### Critical Anti-Patterns (kill on sight)

**Structural tells - these are what actually expose AI. Check these first:**

- Balanced antithesis: "The vision is there. The org move is lagging." / "The willing are there. It's the enablement that's missing." This is the #1 tell - a disguised "not X, but Y". Break the symmetry.
- Rule-of-three triads: "Monorepo, Nix, CI." / "the resources, someone to clear the bottlenecks." Use two or four, or break the parallelism.
- Colon-reveal setups: "So the straight question:" / "Here's the thing:" Drop the drumroll, just say it.
- Uniform polish: every sentence landing cleanly. Leave one rough or loaded sentence in.

**Surface tells:**

- "Not X, but Y" / "not only X, but also Y" constructions
- "In today's rapidly evolving landscape..."
- "It's worth noting that..." / "Let's dive in" / "Without further ado"
- Em-dashes `—`: hard ban. First preference - restructure the sentence to avoid the dash entirely. Fallback only: `-` (hyphen with spaces). Almost no human types `—`, so it screams AI.
- Oxford commas before "and"
- Summary endings that recap the article
- Hollow transitions: "That being said," "Moreover," "On the other hand"
- Fake profundity: "This changes everything"
- Sycophantic openers: "Great question!"

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
