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
4. Generate a complete, self-contained HTML file using the design system below
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

Colors are derived from the actual site dark theme tokens (`dawidnitka.com`).

```css
:root {
  /* Exact values from site dark theme */
  --bg:        hsl(20, 14.3%, 4.1%);    /* --background */
  --surface:   hsl(12, 6.5%, 8%);
  --surface-2: hsl(12, 6.5%, 13%);     /* --muted / --border */
  --border:    hsl(12, 6.5%, 13%);     /* --border */
  --border-2:  hsl(12, 6.5%, 19%);

  --text:   hsl(60, 9.1%, 97.8%);      /* --foreground */
  --text-2: hsl(24, 5.4%, 63.9%);      /* --muted-foreground */
  --text-3: hsl(24, 5.4%, 40%);

  --accent:        hsl(47.9, 95.8%, 53.1%); /* --primary = #facc15 */
  --accent-bg:     hsla(47.9, 95.8%, 53.1%, 0.08);
  --accent-border: hsla(47.9, 95.8%, 53.1%, 0.22);

  --green:     hsl(142, 69%, 58%); --green-bg:  hsla(142, 69%, 58%, 0.08);
  --red:       hsl(0, 91%, 71%);  --red-bg:    hsla(0, 91%, 71%, 0.08);
  --blue:      hsl(213, 94%, 68%); --blue-bg:  hsla(213, 94%, 68%, 0.08);
  --orange:    hsl(27, 96%, 61%);  --orange-bg: hsla(27, 96%, 61%, 0.08);
  --violet:    hsl(265, 78%, 78%); --violet-bg: hsla(265, 78%, 78%, 0.12);

  /* Syntax token colors — slightly desaturated for comfort (not blinding) */
  --token-kw:    hsl(265, 55%, 68%);  /* const let async if return export import function */
  --token-fn:    hsl(213, 74%, 66%);  /* function / method names */
  --token-ident: hsl(47, 78%, 62%);   /* variable names, ALL_CAPS constants, named identifiers */
  --token-str:   hsl(142, 54%, 60%); /* string literals */
  --token-num:   hsl(25, 74%, 61%);  /* numeric literals */
  --token-type: hsl(190, 55%, 60%);  /* TS types, generics, interfaces; CSS selectors */
  --token-tag:  hsl(3, 58%, 63%);    /* HTML/JSX element names */
  --token-attr: hsl(30, 60%, 62%);   /* HTML attr names; CSS property names */

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

/* Scrollbars — Webkit (Chrome, Safari, Edge) */
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border-2); border-radius: 999px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-3); }

/* Firefox */
* { scrollbar-width: thin; scrollbar-color: var(--border-2) var(--bg); }
```

---

## Typography & Spacing

These are the most important rules — get these right and everything reads well.

```css
/* Header */
header {
  margin-bottom: 56px;
  padding-bottom: 36px;
  border-bottom: 1px solid var(--border);
}
.header-meta { display: flex; align-items: center; gap: 12px; margin-bottom: 18px; }
h1 { font-size: 34px; font-weight: 600; letter-spacing: -0.02em; line-height: 1.2; }
.subtitle { color: var(--text-2); margin-top: 10px; font-size: 15px; max-width: 680px; }
.date { font-family: var(--mono); font-size: 12px; color: var(--text-3); }

/* Sections — generous bottom margin so the next h2 has breathing room */
section { margin-bottom: 64px; }

h2 {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--accent);
  margin-bottom: 24px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border);
}

/* h3 — implementation units, subsections, task group titles */
h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text);
  margin-top: 36px;   /* big gap ABOVE — this is what separates units visually */
  margin-bottom: 14px;
}
h3:first-child { margin-top: 0; }

p { color: var(--text-2); line-height: 1.75; margin-bottom: 14px; }
p:last-child { margin-bottom: 0; }

a { color: var(--blue); text-decoration: none; }
a:hover { text-decoration: underline; }

/* Lists — indented enough to feel structured, marker in accent */
ul, ol {
  color: var(--text-2);
  padding-left: 28px;
  margin-top: 8px;
  margin-bottom: 20px;
  line-height: 1.8;
}
li { margin-bottom: 6px; }
li::marker { color: var(--accent); }
li > ul, li > ol { margin-top: 6px; margin-bottom: 0; }

/* Inline code */
:not(pre) > code {
  font-family: var(--mono);
  font-size: 13px;
  background: var(--surface-2);
  color: var(--text);
  padding: 2px 6px;
  border-radius: var(--radius-sm);
}
```

---

## Components

### Pills

```html
<span class="pill pill--mono">LABEL</span>
<span class="pill pill--yellow">In Progress</span>
<span class="pill pill--green">Done</span>
<span class="pill pill--red">Blocked</span>
<span class="pill pill--blue">Info</span>
```

```css
.pill {
  display: inline-flex; align-items: center;
  font-size: 11px; font-weight: 500; letter-spacing: 0.04em;
  padding: 3px 9px; border-radius: 999px;
  background: var(--surface-2); border: 1px solid var(--border); color: var(--text-2);
  white-space: nowrap;
}
.pill--mono   { font-family: var(--mono); text-transform: uppercase; letter-spacing: 0.08em; }
.pill--yellow { background: var(--accent-bg);  border-color: var(--accent-border); color: var(--accent); }
.pill--green  { background: var(--green-bg);   border-color: rgba(74,222,128,.2);  color: var(--green); }
.pill--red    { background: var(--red-bg);     border-color: rgba(248,113,113,.2); color: var(--red); }
.pill--blue   { background: var(--blue-bg);    border-color: rgba(96,165,250,.2);  color: var(--blue); }
.pill--violet { background: var(--violet-bg);  border-color: rgba(170,128,220,.3); color: var(--violet); }
```

### Stats Row — summary numbers near the top

```html
<div class="stats">
  <div class="stat"><div class="stat__value">12</div><div class="stat__label">Done</div></div>
  <div class="stat"><div class="stat__value">3</div><div class="stat__label">In Progress</div></div>
</div>
```

```css
.stats { display: flex; gap: 1px; background: var(--border); border: 1px solid var(--border); border-radius: var(--radius-lg); overflow: hidden; margin-bottom: 40px; }
.stat { flex: 1; padding: 20px 24px; background: var(--surface); }
.stat__value { font-size: 28px; font-weight: 600; letter-spacing: -0.03em; line-height: 1; margin-bottom: 5px; }
.stat__label { font-size: 11px; color: var(--text-3); text-transform: uppercase; letter-spacing: 0.07em; }
```

### Row List — checklists, task lists, findings

```html
<ul class="row-list">
  <li class="row">
    <span class="row__title">Item title</span>
    <span class="row__meta">owner · 2d</span>
    <span class="pill pill--green">Done</span>
  </li>
</ul>
```

```css
.row-list { list-style: none; padding: 0; border: 1px solid var(--border); border-radius: var(--radius-lg); overflow: hidden; }
.row { display: flex; align-items: center; gap: 12px; padding: 14px 20px; border-bottom: 1px solid var(--border); background: var(--surface); }
.row:last-child { border-bottom: none; margin-bottom: 0; }
.row:hover { background: var(--surface-2); }
.row__title { flex: 1; font-size: 14px; color: var(--text); }
.row__meta  { font-family: var(--mono); font-size: 12px; color: var(--text-3); white-space: nowrap; }
```

### Task Card — implementation units, spec items (use instead of plain h3+list)

```html
<div class="task-card">
  <div class="task-card__head">
    <span class="task-card__title">Unit title</span>
    <span class="pill pill--yellow">In Progress</span>
  </div>
  <p>Short description of what this unit covers.</p>
  <ul>
    <li>Step or requirement</li>
    <li>Another step</li>
  </ul>
</div>
```

```css
.task-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 20px 24px;
  margin-bottom: 14px;
}
.task-card__head {
  display: flex; align-items: center; gap: 12px;
  margin-bottom: 12px;
}
.task-card__title {
  flex: 1;
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
}
/* Sub-section labels inside a task card (Goal, Files, Approach, Verification, etc.) */
.task-card .detail-label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: var(--text-3);
  margin-top: 24px;   /* clear visual break above each sub-section */
  margin-bottom: 6px;
}
.task-card .detail-label:first-of-type { margin-top: 16px; }

.task-card ul, .task-card ol { margin-top: 8px; margin-bottom: 0; }

/* Prevent phantom bottom gap — last child in any container should not add space */
.task-card > *:last-child,
.panel__content > *:last-child,
.callout > *:last-child,
.q > *:last-child { margin-bottom: 0; }
```

### Callout — key insights, warnings, risks

```html
<div class="callout callout--yellow"><strong>Key point</strong> — detail here</div>
<div class="callout callout--red"><strong>Risk</strong> — what could go wrong</div>
<div class="callout callout--green"><strong>Resolved</strong> — decision made</div>
```

```css
.callout {
  padding: 14px 20px;
  border-radius: var(--radius);
  border-left: 3px solid var(--border-2);
  background: var(--surface);
  font-size: 14px;
  color: var(--text-2);
  margin: 20px 0;
  line-height: 1.7;
}
.callout--yellow { border-left-color: var(--accent);  background: var(--accent-bg);  color: var(--text); }
.callout--red    { border-left-color: var(--red);     background: var(--red-bg); }
.callout--green  { border-left-color: var(--green);   background: var(--green-bg); }
.callout--violet { border-left-color: var(--violet);  background: var(--violet-bg); }
```

### Open Questions — decisions still pending

```html
<div class="open-q">
  <div class="q">
    <div class="q__title">Should we use Redis or in-memory cache?</div>
    <div class="q__detail">Impacts deployment complexity and cost.</div>
    <div class="q__owner">Owner: @dawid · Due: before Phase 2</div>
  </div>
</div>
```

```css
.open-q { display: flex; flex-direction: column; gap: 12px; }
.q {
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  border-radius: var(--radius-lg);
  padding: 18px 22px;
}
.q__title  { font-size: 15px; font-weight: 600; color: var(--text); margin-bottom: 5px; }
.q__detail { font-size: 13.5px; color: var(--text-2); }
.q__owner  { font-family: var(--mono); font-size: 11.5px; color: var(--text-3); margin-top: 10px; }
```

### Panel — generic labeled block

```html
<div class="panel">
  <div class="panel__label">Context</div>
  <div class="panel__content">Content here</div>
</div>
```

```css
.panel { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 20px 24px; margin-bottom: 14px; }
.panel__label   { font-size: 11px; font-weight: 600; letter-spacing: 0.07em; text-transform: uppercase; color: var(--text-3); margin-bottom: 10px; }
.panel__content { color: var(--text-2); font-size: 14.5px; line-height: 1.7; }
```

### Code Block

```css
pre {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 18px 22px;
  overflow-x: auto;
  margin: 18px 0;
}
pre code { font-family: var(--mono); font-size: 13px; color: var(--text-2); line-height: 1.65; background: none; padding: 0; }
```

### Table

Always wrap in `.table-wrap` — `border-collapse: collapse` breaks `border-radius` on `<table>` itself, so the outer border and rounded corners must live on the wrapper.

```html
<div class="table-wrap">
  <table>
    <thead><tr><th>Column</th><th>Column</th></tr></thead>
    <tbody>
      <tr><td>Value</td><td>Value</td></tr>
    </tbody>
  </table>
</div>
```

```css
/* Wrapper carries the visible border and corners */
.table-wrap {
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
  margin: 18px 0;
}
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th { text-align: left; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.07em; color: var(--text-3); padding: 11px 18px; border-bottom: 1px solid var(--border); background: var(--surface); }
td { padding: 13px 18px; border-bottom: 1px solid var(--border); color: var(--text-2); }
tr:last-child td { border-bottom: none; }
tbody tr:hover td { background: var(--surface-2); }
```

### Table of Contents Sidebar

Use for long documents (research, explainers, long plans). When present, switch `.page` to a two-column grid — the nav is the left column, content is the right. Hidden below 920px via media query.

```html
<!-- Replace .page div with this when ToC is needed -->
<div class="page page--toc">

  <nav>
    <div class="toc-label">On this page</div>
    <a href="#overview">Overview</a>
    <a href="#requirements">Requirements</a>
    <a href="#implementation">Implementation</a>
    <a href="#risks">Risks</a>
    <!-- L2 = nested sub-section -->
    <a href="#unit-1" class="l2">Unit 1</a>
  </nav>

  <main>
    <!-- all sections go here, each with matching id -->
    <section id="overview">...</section>
  </main>

</div>
```

```css
.page--toc {
  display: grid;
  grid-template-columns: 190px minmax(0, 1fr);
  gap: 48px;
  align-items: start;
}
@media (max-width: 920px) {
  .page--toc { grid-template-columns: 1fr; }
  .page--toc nav { display: none; }
}
nav {
  position: sticky;   /* scrolls with page, sticks when it reaches top offset */
  top: 32px;
  align-self: start;
  font-size: 13px;
}
.toc-label {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--text-3);
  margin-bottom: 12px;
}
nav a {
  display: block;
  padding: 5px 0 5px 12px;
  border-left: 2px solid var(--border-2);
  color: var(--text-2);
  text-decoration: none;
  line-height: 1.4;
}
nav a:hover, nav a.active { color: var(--text); border-left-color: var(--accent); }
nav a.l2 { padding-left: 24px; font-size: 12px; color: var(--text-3); }
```

Add this `<script>` block at the end of `<body>` whenever a ToC is present:

```html
<script>
const observer = new IntersectionObserver(entries => {
  entries.forEach(e => {
    if (e.isIntersecting)
      document.querySelectorAll('nav a').forEach(a =>
        a.classList.toggle('active', a.getAttribute('href') === `#${e.target.id}`)
      );
  });
}, { rootMargin: '-10% 0px -80% 0px' });

document.querySelectorAll('section[id]').forEach(s => observer.observe(s));
</script>
```

### Timeline / Milestone

Use for implementation plans or roadmaps that have phases with dates. Dots turn solid green when a phase is done.

```html
<div class="timeline">
  <div class="milestone">
    <div class="when">Week 1</div>
    <div class="dot-col">
      <div class="dot dot--done"></div>
      <div class="line"></div>
    </div>
    <div class="body">
      <h3>Phase title</h3>
      <p>What gets delivered.</p>
      <div style="display:flex;gap:8px;flex-wrap:wrap;">
        <span class="pill pill--green">Done</span>
        <span class="pill pill--mono">U1 U2</span>
      </div>
    </div>
  </div>
  <!-- last milestone: omit .line or it will render a dangling line -->
  <div class="milestone">
    <div class="when">Week 3</div>
    <div class="dot-col">
      <div class="dot"></div>
    </div>
    <div class="body">
      <h3>Next phase</h3>
      <p>What comes after.</p>
    </div>
  </div>
</div>
```

```css
.timeline { display: flex; flex-direction: column; }
.milestone { display: grid; grid-template-columns: 100px 22px 1fr; gap: 0 16px; }
.when { text-align: right; font-family: var(--mono); font-size: 12px; color: var(--text-3); padding-top: 3px; }
.dot-col { display: flex; flex-direction: column; align-items: center; }
.dot { width: 12px; height: 12px; border-radius: 50%; background: var(--bg); border: 2px solid var(--accent); margin-top: 4px; flex-shrink: 0; }
.dot--done { background: var(--green); border-color: var(--green); }
.line { width: 2px; flex: 1; background: var(--border-2); margin: 4px 0; min-height: 16px; }
.milestone .body { padding-bottom: 32px; }
.milestone .body h3 { font-size: 16px; font-weight: 600; color: var(--text); margin-top: 0; margin-bottom: 6px; }
.milestone .body p { font-size: 14px; color: var(--text-2); margin-bottom: 10px; }
```

### Code Panel — with syntax coloring

Use instead of bare `<pre>` when showing actual source code in a code review or implementation plan. Wrap `<span>` tags around token types.

```html
<div class="code-panel">
  <div class="code-panel__label">src/components/Form.tsx</div>
  <pre><code><span class="kw">const</span> <span class="fn">handleSubmit</span> = <span class="kw">async</span> (e) => {
  <span class="cm">// prevent default form POST</span>
  e.preventDefault();
  <span class="kw">const</span> res = <span class="kw">await</span> fetch(<span class="str">'/api/submit'</span>, { method: <span class="str">'POST'</span> });
};</code></pre>
</div>
```

```css
.code-panel { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-lg); overflow: hidden; margin: 18px 0; }
.code-panel__label { padding: 10px 18px; border-bottom: 1px solid var(--border); font-family: var(--mono); font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-3); background: var(--surface-2); }
.code-panel pre { padding: 18px 22px; overflow-x: auto; margin: 0; border: none; border-radius: 0; background: none; }
.code-panel code { font-family: var(--mono); font-size: 13px; line-height: 1.65; color: var(--text-2); background: none; padding: 0; }
/* Core tokens — all languages */
.code-panel .kw    { color: var(--token-kw); }
.code-panel .fn    { color: var(--token-fn); }
.code-panel .str   { color: var(--token-str); }
.code-panel .num   { color: var(--token-num); }
.code-panel .cm    { color: var(--text-3); font-style: italic; }
.code-panel .bool  { color: var(--token-kw); }
.code-panel .const { color: var(--token-ident); }
.code-panel .ident { color: var(--token-ident); }
.code-panel .op    { color: var(--text-2); }
.code-panel .regex { color: var(--token-str); }

/* TypeScript / JavaScript */
.code-panel .type  { color: var(--token-type); }
.code-panel .deco  { color: var(--token-type); }

/* HTML / JSX / Vue */
.code-panel .tag   { color: var(--token-tag); }
.code-panel .attr  { color: var(--token-attr); }
.code-panel .directive { color: var(--token-kw); }

/* CSS / SCSS */
.code-panel .sel  { color: var(--token-type); }
.code-panel .prop { color: var(--token-attr); }
.code-panel .val  { color: var(--token-str); }
.code-panel .unit { color: var(--token-num); }
.code-panel .var  { color: var(--token-type); }
.code-panel .at   { color: var(--token-kw); }

/* ENV / config */
.code-panel .key  { color: var(--token-kw); }

/* Python */
.code-panel .builtin { color: var(--token-fn); opacity: 0.8; }
.code-panel .self    { color: var(--text-3); font-style: italic; }
```

### PR Meta Row

Use in the header of PR writeups — files changed, additions, deletions in mono with color coding.

```html
<div class="pr-meta">
  <span><strong>14</strong> files changed</span>
  <span class="add">+<strong>312</strong> additions</span>
  <span class="del">−<strong>88</strong> deletions</span>
  <span>branch: <strong>feat/newsletter</strong></span>
</div>
```

```css
.pr-meta { display: flex; flex-wrap: wrap; gap: 18px; font-family: var(--mono); font-size: 13px; color: var(--text-3); margin-bottom: 20px; }
.pr-meta strong { color: var(--text); font-weight: 600; }
.pr-meta .add { color: var(--green); }
.pr-meta .del { color: var(--red); }
```

### Diff / Changed Lines

Use when showing code or file changes — incident reports, PR reviews, migration diffs.
Each line is a `<span>` inside a `<div class="diff__body">`. Use a `<div>`, not `<pre>` — a `<pre>` preserves newlines between spans as blank lines.

```html
<div class="diff">
  <div class="diff__file">src/components/Form.tsx</div>
  <div class="diff__hunk">@@ -42,7 +42,9 @@ export function Form() {</div>
  <div class="diff__body">
    <span class="diff__ctx">  const [loading, setLoading] = useState(false);</span>
    <span class="diff__del">- const handleSubmit = (e) => {</span>
    <span class="diff__add">+ const handleSubmit = async (e) => {</span>
    <span class="diff__add">+   await submitForm(data);</span>
    <span class="diff__ctx">  };</span>
  </div>
</div>
```

```css
.diff {
  font-family: var(--mono);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
  margin: 18px 0;
}
.diff__file {
  padding: 9px 18px;
  background: var(--surface-2);
  border-bottom: 1px solid var(--border);
  font-size: 11px;
  letter-spacing: 0.02em;
  color: var(--text-2);
}
.diff__hunk {
  padding: 5px 18px;
  background: var(--blue-bg);
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
  font-size: 12px;
  color: var(--text-3);
}
.diff__body { padding: 6px 0; background: var(--surface); overflow-x: auto; }
.diff__body > span { display: block; padding: 2px 18px; font-size: 13px; line-height: 1.65; white-space: pre; color: hsl(40, 7%, 82%); }
.diff__add { background: var(--green-bg); color: var(--green); }
.diff__del { background: var(--red-bg);   color: var(--red); }
```

For **inline changed tokens** within a line (word-level diff), nest `<mark>` inside the `<span>`:

```html
<span class="diff__del">- <mark>const</mark> handleSubmit = (e) => {</span>
<span class="diff__add">+ <mark>const</mark> handleSubmit = <mark>async</mark> (e) => {</span>
```

```css
.diff__add mark { background: rgba(74, 222, 128, 0.25); color: inherit; border-radius: 2px; }
.diff__del mark { background: rgba(248, 113, 113, 0.25); color: inherit; border-radius: 2px; }
```

---

## Document Type Guidance

Map source markdown to the right HTML patterns:

| Source content | Use this pattern |
| --- | --- |
| H1 | `<header>` with type pill + date |
| H2 sections | `<section id="...">` + `<h2>` (yellow uppercase label) |
| H3 subsections / simple sub-headers | `<h3>` — gets 36px top margin automatically |
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

**For implementation plans:** use Task Cards for each unit — they visually group description + steps and accept a status pill. Add a Timeline above the units if phases/dates exist.

**For research / long explainers:** always add the ToC sidebar. Add `id` attributes to every `<section>` and mirror them as `<a href="#...">` links in the `<nav>`.

---

## Presentation Mode

When the request is for slides, a deck, or a presentation (not a scrollable document), read **`references/slides.md`** — it contains the full deck shell CSS, navigation JS, and HTML patterns for every slide type.

Quick checklist:

- `body` gets `overflow: hidden` (fullscreen, no scroll)
- Each slide is a `<section class="slide">`, stacked absolutely, toggled by `.is-active`
- The outer `.deck` wrapper holds a `.deck-header` (brand + counter) and a `.dots` nav
- All shared design tokens and components from this file apply unchanged inside slides — only layout and typography scale differently (use `clamp()` for responsive sizing)
