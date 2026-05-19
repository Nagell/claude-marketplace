# Slide Deck Reference

All CSS, JS, and HTML patterns for HTML presentations built with the `html-doc` skill.

## Contents

- [Deck Shell CSS](#deck-shell-css)
- [Navigation JS](#navigation-js)
- [Chart Construction](#chart-construction)
- [Slide Types](#slide-types)
  - [Title slide](#1-title-slide)
  - [Stats + single-series chart](#2-stats--single-series-chart-slide)
  - [Big-stat headline](#3-big-stat-headline-slide)
  - [Comparison bar chart](#4-comparison-bar-chart-slide)
  - [Findings](#5-findings-slide)
  - [Section divider](#6-section-divider-slide)
  - [Recommendation](#7-recommendation-slide)
  - [Table / verdict](#8-table--verdict-slide)
  - [CTA / actions](#9-cta--actions-slide)
  - [Closing](#10-closing-slide)

---

## Deck Shell CSS

Add these rules after the shared `:root` block. They override report defaults and establish the fullscreen layout.

```css
html, body { height: 100%; }
body { overflow: hidden; }

/* Deck container */
.deck {
  position: relative;
  width: 100vw; height: 100vh;
  max-width: 1900px;
  margin: 0 auto;
  overflow: hidden;
}

/* Each slide: stacked absolutely, hidden by default */
.slide {
  position: absolute; inset: 0;
  padding: clamp(56px, 8vh, 96px) clamp(36px, 5vw, 96px) clamp(40px, 5vh, 64px);
  display: flex; flex-direction: column;
  opacity: 0;
  transition: opacity 220ms ease;
  pointer-events: none;
  overflow: hidden;
}
.slide.is-active { opacity: 1; pointer-events: auto; }

/* Slide typography (overrides report defaults — uses clamp for viewport scaling) */
.slide h1 {
  font-size: clamp(40px, 5vw, 60px);
  font-weight: 600; letter-spacing: -0.02em; line-height: 1.1;
  margin-bottom: clamp(20px, 2.6vh, 36px);
}
.slide h2 {
  font-size: clamp(22px, 2.4vw, 32px);
  font-weight: 600; letter-spacing: -0.01em; line-height: 1.2;
  color: var(--text);
  margin-bottom: clamp(18px, 2.4vh, 32px);
  padding-bottom: 14px;
  border-bottom: 1px solid var(--border);
  text-transform: none;   /* slide h2 is NOT the yellow uppercase label */
}
.slide h2::before {
  content: "";
  display: inline-block;
  width: 6px; height: 22px;
  background: var(--accent); border-radius: 2px;
  margin-right: 14px; vertical-align: -3px;
}
.subtitle {
  color: hsl(60, 9%, 90%);
  margin-top: 8px;
  font-size: clamp(16px, 1.35vw, 20px);
  max-width: 960px; line-height: 1.55;
}
.slide p { color: var(--text-2); line-height: 1.65; margin-bottom: 12px; }
.slide p:last-child { margin-bottom: 0; }
ul, ol { color: var(--text-2); padding-left: 24px; margin-top: 6px; margin-bottom: 14px; line-height: 1.65; }
li { margin-bottom: 4px; }
li::marker { color: var(--accent); }

/* Deck chrome */
.deck-header {
  position: absolute; top: 0; left: 0; right: 0;
  padding: 14px clamp(32px, 5vw, 80px) 0;
  display: flex; justify-content: space-between; align-items: center;
  pointer-events: none; z-index: 5;
}
.deck-header .brand {
  font-family: var(--mono); font-size: 11px;
  text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-3);
}
.deck-header .counter { font-family: var(--mono); font-size: 11px; color: var(--text-3); }

.dots {
  position: absolute; left: 0; right: 0; bottom: 14px;
  display: flex; gap: 6px; justify-content: center; z-index: 5;
}
.dots button {
  width: 7px; height: 7px; border-radius: 50%;
  background: var(--border-2); border: none; cursor: pointer; padding: 0;
  transition: background 150ms ease, transform 150ms ease;
}
.dots button.is-active { background: var(--accent); transform: scale(1.35); }
.dots button:hover { background: var(--text-3); }

/* Stats row — tighter padding vs. report */
.stats { display: flex; gap: 1px; background: var(--border); border: 1px solid var(--border); border-radius: var(--radius-lg); overflow: hidden; margin-bottom: 20px; }
.stat { flex: 1; padding: 14px 20px; background: var(--surface); }
.stat__value { font-size: clamp(22px, 2.2vw, 28px); font-weight: 600; letter-spacing: -0.03em; line-height: 1; margin-bottom: 4px; }
.stat__label { font-size: 11px; color: var(--text-3); text-transform: uppercase; letter-spacing: 0.07em; }

/* Callout — tighter margins */
.callout { padding: 12px 18px; border-radius: var(--radius); border-left: 3px solid var(--border-2); background: var(--surface); font-size: 14px; color: var(--text-2); margin: 8px 0; line-height: 1.55; }
.callout--yellow { border-left-color: var(--accent); background: var(--accent-bg); }
.callout--violet { border-left-color: var(--violet); background: var(--violet-bg); }
.callout--red    { border-left-color: var(--red);    background: var(--red-bg); }
.callout--green  { border-left-color: var(--green);  background: var(--green-bg); }
```

### Deck HTML skeleton

```html
<div class="deck" id="deck">
  <div class="deck-header">
    <span class="brand">Your title · YYYY-MM</span>
    <span class="counter" id="counter">1 / 1</span>
  </div>

  <!-- slides go here — see slide types below -->

  <nav class="dots" id="dots"></nav>
</div>
```

---

## Navigation JS

Paste verbatim at the end of `<body>`. Handles keyboard, touch, dot clicks, URL hash, and legend toggles.

```html
<script>
(function () {
  const deck = document.getElementById('deck');
  const slides = Array.from(deck.querySelectorAll('.slide'));
  const dots = document.getElementById('dots');
  const counter = document.getElementById('counter');
  if (!slides.length) return;

  function parseHash() {
    const m = /^#s(\d+)$/.exec(location.hash || '');
    if (!m) return 0;
    const n = parseInt(m[1], 10) - 1;
    return Math.max(0, Math.min(slides.length - 1, n));
  }

  let i = parseHash();
  for (let n = 0; n < slides.length; n++) {
    const b = document.createElement('button');
    b.type = 'button';
    b.setAttribute('aria-label', 'Slide ' + (n + 1));
    b.addEventListener('click', () => setActive(n));
    dots.appendChild(b);
  }

  function setActive(n) {
    n = Math.max(0, Math.min(slides.length - 1, n));
    if (n === i && slides[i].classList.contains('is-active')) return;
    slides.forEach((s, k) => s.classList.toggle('is-active', k === n));
    Array.from(dots.children).forEach((d, k) => d.classList.toggle('is-active', k === n));
    counter.textContent = (n + 1) + ' / ' + slides.length;
    slides[i].querySelectorAll('.chart.hide-tech, .chart.hide-nontech').forEach(c => {
      c.classList.remove('hide-tech', 'hide-nontech');
    });
    slides[i].querySelectorAll('.legend button.is-off').forEach(b => b.classList.remove('is-off'));
    i = n;
    history.replaceState(null, '', '#s' + (n + 1));
  }

  setActive(i);

  document.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown' || e.key === ' ' || e.key === 'PageDown') { e.preventDefault(); setActive(i + 1); }
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp' || e.key === 'PageUp') { e.preventDefault(); setActive(i - 1); }
    else if (e.key === 'Home') { e.preventDefault(); setActive(0); }
    else if (e.key === 'End') { e.preventDefault(); setActive(slides.length - 1); }
  });

  let tx = 0;
  deck.addEventListener('touchstart', (e) => { tx = e.changedTouches[0].clientX; }, { passive: true });
  deck.addEventListener('touchend', (e) => {
    const dx = e.changedTouches[0].clientX - tx;
    if (Math.abs(dx) > 40) setActive(i + (dx < 0 ? 1 : -1));
  }, { passive: true });

  deck.addEventListener('click', (e) => {
    const btn = e.target.closest('.legend button[data-series]');
    if (!btn) return;
    const slide = btn.closest('.slide');
    const series = btn.dataset.series;
    const cls = series === 'technical' ? 'hide-tech' : 'hide-nontech';
    btn.classList.toggle('is-off');
    slide.querySelectorAll('.chart').forEach(c => c.classList.toggle(cls));
  });

  window.addEventListener('hashchange', () => setActive(parseHash()));
})();
</script>
```

---

## Chart Construction

Bar charts are driven by a single CSS custom property `--pct` (0–100) set inline on each `.bar`. No JS needed for rendering — only for the legend toggle (already in the nav script).

### Computing values

```js
--pct  = Math.round(count / total * 100)   // bar height as % of bar-area
```

`bar__meta` label format: `"count · pct%"` — e.g. `38 · 93%`.

### Chart layout

| Attribute | Effect |
| --- | --- |
| `style="--cols:N"` on `.chart` | Number of columns (= number of answer options) |
| `chart--single` modifier | Single-series layout — wider columns, more breathing room |
| No modifier | Dual-series layout — two bars per group side by side |

Rule of thumb: `--cols` up to 6 works well for dual-series; up to 10 for single-series. Beyond that, labels get cramped — consider splitting across two slides.

### Single-series (one group per question)

Use `.bar--tech` or `.bar--nontech` (or any single class) — color is determined by the class. `--pct` is relative to the **total respondent count** for that group.

```html
<div class="chart chart--single" style="--cols:5">
  <div class="group">
    <div class="group__bars">
      <div class="bar bar--tech" style="--pct:49">
        <span class="bar__meta">40 · 49%</span>
        <div class="bar__fill"></div>
      </div>
    </div>
    <div class="group__label">Engineering / QA</div>
  </div>
</div>
```

### Dual-series (two groups compared per question)

Two `.bar` elements inside each `.group__bars`. Each `--pct` is relative to **that group's total**, not the combined total — so both groups can hit 100% independently.

```html
<div class="chart" style="--cols:5">
  <div class="group">
    <div class="group__bars">
      <div class="bar bar--tech" style="--pct:93">
        <span class="bar__meta">38 · 93%</span>
        <div class="bar__fill"></div>
      </div>
      <div class="bar bar--nontech" style="--pct:23">
        <span class="bar__meta">9 · 23%</span>
        <div class="bar__fill"></div>
      </div>
    </div>
    <div class="group__label">Claude Code</div>
  </div>
</div>
```

### Bar colors

| Class | Color | Intended use |
| --- | --- | --- |
| `.bar--tech` | `--accent` (yellow) | Technical / primary group |
| `.bar--nontech` | `--violet` | Non-technical / secondary group |

Rename the classes freely — only the CSS fill rule needs to match (`.bar--tech .bar__fill { background: var(--accent); }`).

---

## Slide Types

### 1. Title slide

Full-viewport centered layout with eyebrow label, large h1, subtitle text, and optional pills.

```html
<section class="slide slide--centered is-active">
  <div class="centered-body">
    <div class="eyebrow">Company · YYYY-MM</div>
    <h1>Title of the presentation.</h1>
    <p class="subtitle">One or two sentences of framing. Who, what, n=X.</p>
    <div class="centered-pills">
      <span class="pill pill--yellow">Group A · N</span>
      <span class="pill pill--violet">Group B · N</span>
      <span class="pill pill--mono">n = total</span>
    </div>
  </div>
</section>
```

```css
.slide--centered { justify-content: center; align-items: flex-start; }
.slide--centered .centered-body { max-width: 1100px; }
.slide--centered .eyebrow {
  font-family: var(--mono); font-size: 16px;
  letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--accent); margin-bottom: 22px;
}
.slide--centered h1 {
  font-size: clamp(56px, 7vw, 104px);
  line-height: 1.05; letter-spacing: -0.02em; margin-bottom: 24px;
}
.slide--centered .subtitle { font-size: clamp(18px, 1.55vw, 24px); line-height: 1.5; max-width: 880px; margin-top: 0; }
.slide--centered .centered-pills { margin-top: 32px; display: flex; gap: 12px; flex-wrap: wrap; }
.slide--centered .centered-pills .pill { font-size: 14px; padding: 6px 14px; }
```

---

### 2. Stats + single-series chart slide

Demographics or distribution: stats row at top, single-series bar chart below.

```html
<section class="slide">
  <h2>Who answered</h2>
  <div class="stats">
    <div class="stat"><div class="stat__value">81</div><div class="stat__label">Total</div></div>
    <div class="stat"><div class="stat__value" style="color:var(--accent)">41</div><div class="stat__label">Group A</div></div>
    <div class="stat"><div class="stat__value" style="color:var(--violet)">40</div><div class="stat__label">Group B</div></div>
  </div>
  <div class="chart chart--single" style="--cols:10">
    <div class="group">
      <div class="group__bars">
        <div class="bar bar--tech" style="--pct:49">
          <span class="bar__meta">40 · 49%</span>
          <div class="bar__fill"></div>
        </div>
      </div>
      <div class="group__label">Engineering / QA</div>
    </div>
    <!-- repeat .group for each category -->
  </div>
</section>
```

```css
/* Bar chart */
.chart {
  --bar-area: clamp(280px, 44vh, 440px);
  --label-lines: 3;
  --label-line-h: 1.25em;
  display: grid;
  grid-template-columns: repeat(var(--cols, 6), minmax(0, 1fr));
  gap: clamp(12px, 1.4vw, 20px);
  align-items: stretch;
  margin-top: 8px;
  padding: 44px 0 16px;
}
.chart--single { grid-template-columns: repeat(var(--cols, 10), minmax(0, 1fr)); }
.group { display: grid; grid-template-rows: var(--bar-area) auto; min-width: 0; }
.group__bars { display: flex; gap: 6px; align-items: end; height: var(--bar-area); border-bottom: 1px solid var(--border-2); position: relative; }
.bar { flex: 1; min-width: 14px; height: 100%; position: relative; }
.bar__fill { position: absolute; bottom: 0; left: 0; right: 0; height: calc(var(--pct, 0) * 1%); border-radius: 4px 4px 0 0; transition: height 200ms ease; min-height: 2px; }
.bar__meta { position: absolute; left: 50%; transform: translateX(-50%); bottom: calc(var(--pct, 0) * 1% + 4px); font-family: var(--mono); font-size: clamp(12px, 1.05vw, 15px); font-weight: 600; color: var(--text); white-space: nowrap; pointer-events: none; }
.bar--tech    .bar__fill { background: var(--accent); opacity: 0.88; }
.bar--nontech .bar__fill { background: var(--violet); opacity: 1; }
.group__label { margin-top: 16px; font-size: clamp(12px, 1vw, 14px); color: var(--text); text-align: center; overflow-wrap: break-word; word-break: auto-phrase; line-height: var(--label-line-h); hyphens: none; min-height: calc(var(--label-lines) * var(--label-line-h)); display: -webkit-box; -webkit-line-clamp: var(--label-lines); -webkit-box-orient: vertical; overflow: hidden; }
```

---

### 3. Big-stat headline slide

Three key numbers with colored accent text, each with a body explanation. Use for "what's working" / "what's missing" summaries.

```html
<section class="slide">
  <h2>Section title</h2>
  <p class="subtitle">One-line framing sentence.</p>
  <div class="headline-grid">
    <div class="big-stat big-stat--green">
      <div class="big-stat__num">93%</div>
      <div class="big-stat__body">Explanation of what this number means.</div>
    </div>
    <div class="big-stat big-stat--yellow">
      <div class="big-stat__num">42%</div>
      <div class="big-stat__body">Another finding. <code>inline code</code> if needed.</div>
    </div>
    <div class="big-stat big-stat--violet">
      <div class="big-stat__num">2 / 81</div>
      <div class="big-stat__body">Third number with context.</div>
    </div>
  </div>
</section>
```

Modifiers: `big-stat--yellow`, `big-stat--violet`, `big-stat--red`, `big-stat--green`.

```css
.headline-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: clamp(20px, 2.4vw, 36px); margin-top: 12px; flex: 1; align-items: stretch; }
.big-stat { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: clamp(28px, 3.4vh, 44px) clamp(26px, 2.4vw, 40px); display: grid; grid-template-rows: 1fr 1fr; }
.big-stat__num { align-self: end; font-size: clamp(56px, 8vw, 110px); font-weight: 700; letter-spacing: -0.04em; line-height: 1; }
.big-stat--yellow .big-stat__num { color: var(--accent); }
.big-stat--violet .big-stat__num { color: var(--violet); }
.big-stat--red    .big-stat__num { color: var(--red); }
.big-stat--green  .big-stat__num { color: var(--green); }
.big-stat__body { align-self: start; padding-top: 22px; font-size: clamp(17px, 1.45vw, 23px); color: var(--text); line-height: 1.6; }
.big-stat__body code { font-family: var(--mono); background: var(--surface-2); padding: 1px 6px; border-radius: 4px; font-size: 0.92em; }
```

---

### 4. Comparison bar chart slide

Side-by-side bars for two groups (e.g. technical vs. non-technical). Toggle buttons hide/show each series. Optional quote block below.

```html
<section class="slide">
  <h2>Question text</h2>
  <div class="legend">
    <button type="button" data-series="technical"><span class="swatch"></span>Technical (41)</button>
    <button type="button" data-series="nonTechnical"><span class="swatch"></span>Non-technical (40)</button>
  </div>
  <div class="chart" style="--cols:5">
    <div class="group">
      <div class="group__bars">
        <div class="bar bar--tech" style="--pct:93">
          <span class="bar__meta">38 · 93%</span>
          <div class="bar__fill"></div>
        </div>
        <div class="bar bar--nontech" style="--pct:23">
          <span class="bar__meta">9 · 23%</span>
          <div class="bar__fill"></div>
        </div>
      </div>
      <div class="group__label">Option label</div>
    </div>
    <!-- repeat .group for each answer option -->
  </div>
  <!-- optional quotes -->
  <div class="quotes">
    <div class="callout quote callout--yellow">
      <span class="quote__tag">Tech</span>
      <span class="quote__text">Free-text quote from a respondent.</span>
    </div>
  </div>
</section>
```

```css
/* Legend */
.legend { display: flex; gap: 10px; margin-bottom: 4px; }
.legend button { font: inherit; cursor: pointer; display: inline-flex; align-items: center; gap: 8px; padding: 5px 12px; border-radius: 999px; background: var(--surface-2); border: 1px solid var(--border); color: var(--text-2); transition: opacity 150ms ease; }
.legend button .swatch { width: 10px; height: 10px; border-radius: 2px; }
.legend button[data-series="technical"] .swatch  { background: var(--accent); }
.legend button[data-series="nonTechnical"] .swatch { background: var(--violet); }
.legend button.is-off { opacity: 0.35; }
.chart.hide-tech    .bar--tech    { display: none; }
.chart.hide-nontech .bar--nontech { display: none; }

/* Quotes */
.quotes { margin-top: 18px; display: flex; flex-direction: column; gap: 8px; }
.callout.quote { display: flex; align-items: baseline; gap: 14px; font-size: clamp(14px, 1.05vw, 16px); line-height: 1.55; color: var(--text); padding: 12px 18px; }
.quote__tag { flex-shrink: 0; min-width: 88px; font-family: var(--mono); font-size: clamp(11px, 0.85vw, 12px); text-transform: uppercase; letter-spacing: 0.08em; font-weight: 600; }
.callout--yellow .quote__tag { color: var(--accent); }
.callout--violet .quote__tag { color: var(--violet); }
.quote__text { flex: 1; }
```

---

### 5. Findings slide

Three finding cards, each with a bold lead phrase and supporting body text.

```html
<section class="slide">
  <h2>Key findings</h2>
  <p class="subtitle">Framing sentence.</p>
  <div class="findings-grid">
    <div class="finding-card finding-card--yellow">
      <div class="finding-card__lead">Lead phrase or stat</div>
      <div class="finding-card__body">Supporting explanation — 2–3 sentences.</div>
    </div>
    <div class="finding-card finding-card--violet">
      <div class="finding-card__lead">Second finding</div>
      <div class="finding-card__body">Body text.</div>
    </div>
    <div class="finding-card finding-card--red">
      <div class="finding-card__lead">Third finding</div>
      <div class="finding-card__body">Body text.</div>
    </div>
  </div>
</section>
```

Modifiers: `finding-card--yellow`, `finding-card--violet`, `finding-card--red`.

```css
.findings-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: clamp(20px, 2.4vw, 36px); margin-top: 14px; flex: 1; align-items: stretch; }
.finding-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: clamp(28px, 3.4vh, 44px) clamp(26px, 2.4vw, 40px); display: grid; grid-template-rows: 1fr 1fr; }
.finding-card__lead { align-self: end; font-size: clamp(22px, 2.4vw, 36px); font-weight: 700; letter-spacing: -0.01em; line-height: 1.15; }
.finding-card--yellow .finding-card__lead { color: var(--accent); }
.finding-card--violet .finding-card__lead { color: var(--violet); }
.finding-card--red    .finding-card__lead { color: var(--red); }
.finding-card__body { align-self: start; padding-top: 22px; font-size: clamp(15px, 1.25vw, 19px); color: var(--text-2); line-height: 1.6; }
```

---

### 6. Section divider slide

Centered layout used between major sections (e.g. "Recommendations" heading). Re-uses `.slide--centered`.

```html
<section class="slide slide--centered">
  <div class="centered-body">
    <div class="eyebrow">Part 2</div>
    <h1>Section title</h1>
    <p class="subtitle">Optional framing sentence.</p>
  </div>
</section>
```

Same CSS as the Title slide — no additional rules needed.

---

### 7. Recommendation slide

Two-column panel grid: left panel holds prose or bullet action list, right panel holds a pain-point grid (percentage + description pairs).

```html
<section class="slide">
  <h2>Recommendation title</h2>
  <div class="rec-pill">REC-01 · audience</div>
  <div class="rec-body">
    <div class="rec-grid">
      <div class="rec-panel">
        <div class="rec-panel__label">What to do</div>
        <div class="rec-panel__body">
          <ul>
            <li>Action item one.</li>
            <li>Action item two with <code>code</code>.</li>
          </ul>
        </div>
      </div>
      <div class="rec-panel">
        <div class="rec-panel__label">Why it matters</div>
        <div class="rec-panel__body">
          <div class="pain-list">
            <span class="pain-stat">46%</span>
            <span class="pain-text">Description of the pain point.</span>
            <span class="pain-stat pain-stat--quote">"</span>
            <span class="pain-text pain-text--quote">Direct quote from a respondent.</span>
          </div>
        </div>
      </div>
    </div>
    <div class="rec-footer">
      <span class="pill pill--yellow">In Progress</span>
      <span class="pill pill--mono">owner · timeline</span>
    </div>
  </div>
</section>
```

```css
.rec-pill { font-family: var(--mono); font-size: 13px; color: var(--text-3); margin-bottom: 8px; letter-spacing: 0.05em; }
.rec-body { display: flex; flex-direction: column; gap: 24px; max-width: 1500px; width: 100%; margin-top: 22px; }
.rec-grid { display: grid; grid-template-columns: 1fr 1fr; gap: clamp(20px, 2.2vw, 36px); }
.rec-panel { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: clamp(22px, 2.4vh, 32px) clamp(24px, 2.2vw, 36px); max-height: clamp(300px, 40vh, 420px); overflow: hidden; display: flex; flex-direction: column; }
.rec-panel__label { font-size: 13px; text-transform: uppercase; letter-spacing: 0.1em; color: var(--text-3); margin-bottom: 14px; font-weight: 600; }
.rec-panel__body { font-size: clamp(14px, 1.15vw, 18px); color: var(--text); line-height: 1.65; }
.rec-panel__body ul { margin: 4px 0 0; padding-left: 22px; color: var(--text); }
.rec-panel__body li { margin-bottom: 10px; }
.rec-panel__body li:last-child { margin-bottom: 0; }
.rec-panel__body code { font-size: 0.92em; color: var(--accent); background: var(--accent-bg); padding: 1px 6px; border-radius: 4px; }
.pain-list { display: grid; grid-template-columns: max-content 1fr; column-gap: clamp(18px, 1.4vw, 26px); row-gap: 14px; align-items: baseline; }
.pain-stat { font-family: var(--mono); font-weight: 700; font-size: 1.1em; color: var(--accent); text-align: right; white-space: nowrap; line-height: 1.4; }
.pain-stat--quote { color: var(--text-3); font-weight: 400; font-size: 1.2em; }
.pain-text { color: var(--text); line-height: 1.55; }
.pain-text--quote { color: var(--text-2); }
.pain-text strong { color: var(--accent); font-weight: 600; }
.rec-footer { display: flex; gap: 12px; flex-wrap: wrap; }
.rec-footer .pill { font-size: 13px; padding: 5px 12px; }
```

---

### 8. Table / verdict slide

Full-width table with larger fonts for readability at distance. First column is bold; third column is monospaced.

```html
<section class="slide">
  <h2>Comparison / verdict</h2>
  <div class="table-wrap">
    <table class="verdict-table">
      <thead>
        <tr>
          <th>Item</th>
          <th>Assessment</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>Row label</td>
          <td>Prose explanation of the verdict.</td>
          <td><span class="pill pill--green">Done</span></td>
        </tr>
      </tbody>
    </table>
  </div>
</section>
```

```css
.table-wrap { border: 1px solid var(--border); border-radius: var(--radius-lg); overflow: hidden; margin: 14px 0; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th { text-align: left; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.07em; color: var(--text-3); padding: 10px 16px; border-bottom: 1px solid var(--border); background: var(--surface); }
td { padding: 11px 16px; border-bottom: 1px solid var(--border); color: var(--text-2); vertical-align: top; }
tr:last-child td { border-bottom: none; }
.verdict-table { font-size: clamp(15px, 1.2vw, 19px); }
.verdict-table th { font-size: clamp(12px, 0.95vw, 14px); padding: 14px 22px; }
.verdict-table td { padding: 16px 22px; line-height: 1.45; }
.verdict-table td:first-child { font-weight: 600; color: var(--text); font-size: clamp(15px, 1.25vw, 20px); }
.verdict-table td:nth-child(3) { font-family: var(--mono); font-size: clamp(13px, 1vw, 16px); color: var(--text-2); }
.verdict-table .pill { font-size: 13px; padding: 5px 12px; }
```

---

### 9. CTA / actions slide

Numbered action items (CSS counter) with a follow-up callout at the bottom.

```html
<section class="slide">
  <h2>What happens next</h2>
  <div class="cta-list">
    <div class="cta-item">
      <div>
        <div class="cta-item__title">Action title</div>
        <div class="cta-item__meta">owner · timeline</div>
      </div>
    </div>
    <!-- repeat .cta-item -->
  </div>
  <div class="cta-follow">Follow-up note or next milestone.</div>
</section>
```

```css
.cta-list { counter-reset: cta; display: flex; flex-direction: column; gap: 14px; margin-top: 14px; }
.cta-item { display: grid; grid-template-columns: 56px 1fr; gap: 18px; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 18px 24px; }
.cta-item::before { counter-increment: cta; content: counter(cta); font-family: var(--mono); font-size: clamp(28px, 3vw, 40px); color: var(--accent); font-weight: 700; line-height: 1; align-self: center; }
.cta-item__title { font-size: clamp(16px, 1.25vw, 20px); color: var(--text); font-weight: 600; margin-bottom: 6px; }
.cta-item__meta  { font-family: var(--mono); font-size: 12px; color: var(--text-3); }
.cta-follow { margin-top: 18px; padding: 14px 22px; border-left: 3px solid var(--accent); background: var(--accent-bg); color: var(--text); border-radius: 6px; font-size: clamp(14px, 1.1vw, 17px); }
```

---

### 10. Closing slide

Re-uses `.slide--centered`. Adds a large accent tagline below the h1.

```html
<section class="slide slide--centered">
  <div class="centered-body">
    <div class="eyebrow">Thank you</div>
    <h1>Questions?</h1>
    <div class="closing-tagline">tagline or next step</div>
    <p class="subtitle">Optional contact / link.</p>
  </div>
</section>
```

```css
.closing-tagline {
  font-size: clamp(36px, 4vw, 60px);
  font-weight: 600; letter-spacing: -0.01em; line-height: 1.1;
  color: var(--accent); margin-top: 8px; margin-bottom: 28px;
}
```
