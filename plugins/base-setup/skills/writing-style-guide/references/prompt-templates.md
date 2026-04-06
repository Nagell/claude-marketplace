# Prompt Templates - Writing Workflow

These prompts are designed to work inside a Claude Project that has the Style Guide loaded as project instructions. Copy-paste and adapt as needed.

---

## 1. Draft from Notes

Use when: You have rough notes, bullet points, or a brain dump and want a first draft.

```
Here are my rough notes for an article:

---
[PASTE NOTES HERE]
---

Target audience: [who is reading this - developers, engineering managers, your CTO, general tech audience]
Purpose: [inform, persuade, teach, document]
Personality level: [high / moderate / restrained]

Before writing, please:
1. Suggest which structural template (A: Friction→Pattern→Framework, B: Bold Claim→Proof, C: Problem→Solution→Walkthrough) fits best, and why.
2. Propose a section outline with 1-sentence descriptions.
3. Wait for my feedback before drafting prose.
```

---

## 2. Rewrite in My Voice

Use when: You have a draft (yours or AI-generated) that sounds flat or generic and needs voice injection.

```
Here's a draft that needs to sound more like me:

---
[PASTE DRAFT HERE]
---

Please rewrite following my style guide. Specifically:
- Inject personality where appropriate (compressed asides, preemptive objections, pivot questions)
- Cut all blacklist patterns
- Tighten sentences - remove filler, reduce word count by ~20% where possible
- Flag and fix any non-native English patterns (articles, prepositions, word order)
- Show me a before/after for the 3 most significant changes so I can learn the pattern
```

---

## 3. Expand Bullets into Prose

Use when: You have structured bullet points that need to become readable paragraphs.

```
Turn these bullet points into prose following my style guide:

---
[PASTE BULLETS HERE]
---

Rules:
- Don't just connect bullets with transitions. Each paragraph should flow naturally.
- Vary sentence length. Short for emphasis, longer for explanation.
- Keep my compressed aside style - use dashes and parentheticals where they'd add personality.
- Personality level: [high / moderate / restrained]
- Don't add information I haven't provided. If something needs expansion, flag it as [NEEDS DETAIL].
```

---

## 4. Edit for Anti-Patterns

Use when: You have a near-final draft and want a strict quality pass.

```
Run my revision checklist against this draft:

---
[PASTE DRAFT HERE]
---

For each issue found, show:
1. The exact problematic text
2. Which checklist item it violates
3. A suggested fix

Group issues by category: Voice, Structure, Sentences, English Quality, Economy.
At the end, give an overall assessment: is this ready to publish, or does it need another pass?
```

---

## 5. Opening Variants

Use when: You're stuck on how to start a piece.

```
I'm writing about: [TOPIC]
Audience: [WHO]
Template: [A / B / C]
Personality level: [high / moderate / restrained]

Generate 3 different openings (2-3 paragraphs each):
1. One that opens with personal friction - something specific that happened to me
2. One that opens with a bold, compressed claim
3. One that opens with a concrete scene or moment

For each, use my style guide voice. No throat-clearing, no "In today's world..." - stakes clear by paragraph 2.
```

---

## 6. Ending Variants

Use when: You've written the body but the ending feels flat or summary-ish.

```
Here's my article so far (the ending is weak or missing):

---
[PASTE ARTICLE]
---

Generate 3 different endings (1-2 paragraphs each):
1. One that extends the core idea forward - what comes next, what this implies
2. One that ends with a provocation or question for the reader
3. One that circles back to the opening image/moment but reframes it

None of them should summarize the article. The reader just read it - they don't need a recap.
```

---

## 7. English Fluency Check

Use when: You want specific help with non-native patterns.

```
Review this text for non-native English patterns:

---
[PASTE TEXT HERE]
---

Focus specifically on:
- Article usage (a/the/zero) - explain the rule for each fix
- Preposition choices - suggest the most natural English option
- Word order - flag any Germanic/Slavic sentence structures
- Flat phrasings - where something is technically correct but a native speaker would say it differently, suggest 2-3 alternatives with brief explanations

Format: show the original, the fix, and a one-line explanation of *why* so I learn the pattern.
```

---

## 8. Quick Technical Section

Use when: You need to write a technical explanation that's clear but not boring.

```
I need to explain [TECHNICAL CONCEPT] in [CONTEXT - article section, documentation, README].

Key points to cover:
- [POINT 1]
- [POINT 2]
- [POINT 3]

Audience: [developers who know X but not Y / complete beginners / experienced engineers]
Personality level: [restrained for docs, moderate for articles]

Write it following my style guide. Include:
- A concrete example or code snippet
- At least one "gotcha" or common mistake
- No "let's dive in" or "without further ado" - just explain the thing
```

---

## 9. Article Series Planning

Use when: You want to plan a multi-part series (like the monorepo articles).

```
I want to write a series about: [TOPIC]

What I know so far:
- [KEY POINTS / SUBTOPICS]

Target audience: [WHO]

Help me plan this:
1. How many parts should it be? (err on the side of fewer, tighter articles)
2. What's the narrative arc across the series?
3. For each part: title, 1-paragraph summary, which structural template (A/B/C) fits
4. What's the hook that makes someone want to read the next part?
5. What's the one thing the complete series should leave the reader able to do?
```

---

## 10. Tone Calibration Check

Use when: You're unsure if the personality level is right for the audience.

```
Here's a passage I wrote:

---
[PASTE PASSAGE]
---

The audience is: [WHO]
The purpose is: [WHAT]

Is the personality level appropriate? Specifically:
- Is anything too casual for this audience?
- Is anything too stiff given my natural voice?
- Are the jokes earning their word count?
- Would anything land differently than intended with [specific audience]?

If adjustments are needed, show me the recalibrated version.
```
