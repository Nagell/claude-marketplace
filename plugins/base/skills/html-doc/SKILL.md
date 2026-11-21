---
name: html-doc
description: Use when the user asks to convert markdown into a styled HTML document OR create an HTML slide deck / presentation. Triggers: "HTML version of this", "make this an HTML report", "convert to HTML", "HTML version of [file]", "give me the HTML output", "create slides", "make a slide deck", "build a presentation", "HTML slideshow". Do NOT invoke automatically when writing markdown or creating plans.
---

# HTML Document & Slides

Convert markdown or structured content into a beautiful, self-contained HTML file — either a scrollable **report** or a fullscreen **slide deck** — using the shared design system below.

> **Source:** Components adapted from Thariq Shihipar's (Anthropic) 20 HTML document examples — <https://github.com/ThariqS/html-effectiveness>. Check there first when extending this skill.

## Instructions

1. Read the source markdown file (or use the content already in context)
2. Detect mode: **report** (scrollable document) or **slide deck** (fullscreen presentation). If slides, read `references/slides.md` before generating any HTML.
3. Determine the document type: `status`, `code-review`, `plan`, `findings`, `pr`, `research`, or infer from content
4. Generate a complete, self-contained HTML file; read **`references/styles.md`** for all component HTML and CSS patterns
5. Write it next to the source file with the same base name but `.html` extension (e.g. `plan-auth.md` → `plan-auth.html`). If there is no source file, write to the current working directory with a descriptive kebab-case name.
6. Generate a browser-ready URL for the file and output it as the only line of output:
   - **WSL** (`$WSL_DISTRO_NAME` is set): run `wslpath -w "<path>"` to get the Windows UNC path (`\\wsl.localhost\Distro\...`), then convert to `file://wsl.localhost/Distro/...` by stripping the leading `\\` and replacing `\` with `/`
   - **macOS / native Linux**: `file:///absolute/path/to/file.html`
   - **Windows native** (Git Bash etc.): `file:///C:/path/to/file.html`

**Rules:**

- All CSS inline in a `<style>` tag — no external stylesheets, no CDN links
- No JavaScript frameworks — vanilla JS only, only when it adds real value (tabs, toggles)
- Semantic HTML: `<header>`, `<main>`, `<section>`, `<article>`, `<table>`, `<code>`
- Populate with the actual content — never use lorem ipsum or placeholder text
- Preserve all information from the source — nothing gets dropped

---

## Design System

Colors derived from the site dark theme tokens (`dawidnitka.com`). Always include the full `:root` block and reset in every output file.

```css
:root {
  --bg:        hsl(20, 14.3%, 4.1%);   /* page background */
  --surface:   hsl(12, 6.5%, 8%);      /* card / panel background */
  --surface-2: hsl(12, 6.5%, 13%);    /* hover state, code bg, pill bg */
  --border:    hsl(12, 6.5%, 13%);    /* default border */
  --border-2:  hsl(12, 6.5%, 19%);   /* stronger border, timeline line */

  --text:   hsl(60, 9.1%, 97.8%);     /* primary text — headings, values */
  --text-2: hsl(24, 5.4%, 63.9%);    /* body text — paragraphs, list items */
  --text-3: hsl(24, 5.4%, 40%);      /* muted text — dates, meta, labels */

  --accent:        hsl(47.9, 95.8%, 53.1%); /* primary highlight = #facc15 yellow */
  --accent-bg:     hsla(47.9, 95.8%, 53.1%, 0.08);
  --accent-border: hsla(47.9, 95.8%, 53.1%, 0.22);

  --green:     hsl(142, 69%, 58%); --green-bg:  hsla(142, 69%, 58%, 0.08); /* success, done, additions */
  --red:       hsl(0, 91%, 71%);   --red-bg:    hsla(0, 91%, 71%, 0.08);   /* error, risk, deletions */
  --blue:      hsl(213, 94%, 68%); --blue-bg:   hsla(213, 94%, 68%, 0.08); /* info, links, diff hunks */
  --orange:    hsl(27, 96%, 61%);  --orange-bg: hsla(27, 96%, 61%, 0.08);  /* warning */
  --violet:    hsl(265, 78%, 78%); --violet-bg: hsla(265, 78%, 78%, 0.12); /* secondary group / accent */

  /* Syntax tokens — used by Code Panel spans */
  --token-kw:    hsl(265, 55%, 68%); /* keywords: const let async if return export import function */
  --token-fn:    hsl(213, 74%, 66%); /* function / method names */
  --token-ident: hsl(47, 78%, 62%);  /* variable names, ALL_CAPS constants */
  --token-str:   hsl(142, 54%, 60%); /* string literals */
  --token-num:   hsl(25, 74%, 61%);  /* numeric literals */
  --token-type:  hsl(190, 55%, 60%); /* TS types, generics, interfaces; CSS selectors */
  --token-tag:   hsl(3, 58%, 63%);   /* HTML/JSX element names */
  --token-attr:  hsl(30, 60%, 62%);  /* HTML attr names; CSS property names */

  --sans: Inter, system-ui, -apple-system, "Segoe UI", sans-serif;
  --mono: "Fira Code", "FiraCode Nerd Font", "Fira Mono", "JetBrains Mono",
          "Cascadia Code", "Source Code Pro", "IBM Plex Mono",
          ui-monospace, "SF Mono", Menlo, Consolas, monospace;

  --radius:    8px;
  --radius-sm: 4px;
  --radius-lg: 12px;
}

* { box-sizing: border-box; margin: 0; padding: 0; }
html { scroll-behavior: smooth; }

body {
  background: var(--bg);
  color: var(--text);
  font-family: var(--sans);
  font-size: 15px;
  line-height: 1.65;
  -webkit-font-smoothing: antialiased;
  padding: 56px 32px 120px;
}

.page { max-width: 860px; margin: 0 auto; }

::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border-2); border-radius: 999px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-3); }
* { scrollbar-width: thin; scrollbar-color: var(--border-2) var(--bg); }
```

---

## Document Type Guidance

Read **`references/styles.md`** for component CSS and HTML markup for anything in this table.

| Source content | Use this pattern |
| --- | --- |
| H1 | `<header>` with type pill + date |
| H2 sections | `<section id="...">` + `<h2>` (yellow uppercase label) |
| H3 subsections | `<h3>` — gets 36px top margin automatically |
| Implementation units / spec items | **Task Card** (not bare h3+list) |
| Task lists / checklists | Row List with status pills |
| Bullet lists of facts/steps | Plain `<ul>` — 28px indent, accent markers |
| Key decisions, insights | Callout yellow |
| Risks | Callout red |
| Open questions | Open Questions component |
| Summary numbers | Stats Row |
| Code snippets (plain) | Code Block |
| Code snippets (source files, reviews) | **Code Panel** with syntax coloring |
| Code changes / diffs / before-after | **Diff** component |
| Comparisons / data tables | Table (wrapped in `.table-wrap`) |
| Generic labeled content | Panel |
| Phases with dates | **Timeline / Milestone** |
| PR writeup header | **PR Meta Row** |
| Long document (research, long plan) | Add **ToC Sidebar** — switch `.page` to `.page--toc` grid |
| Slide deck / presentation request | **Presentation Mode** — read `references/slides.md` |

**For implementation plans:** use Task Cards for each unit. Add a Timeline above if phases/dates exist.

**For research / long explainers:** always add the ToC sidebar.

---

## Presentation Mode

When the request is for slides, a deck, or a presentation, read **`references/slides.md`** — it contains the full deck shell CSS, navigation JS, and HTML patterns for every slide type.

- `body` gets `overflow: hidden` (fullscreen, no scroll)
- Each slide is a `<section class="slide">`, stacked absolutely, toggled by `.is-active`
- The outer `.deck` wrapper holds a `.deck-header` (brand + counter) and a `.dots` nav
- All shared tokens and components from `references/styles.md` apply unchanged inside slides
