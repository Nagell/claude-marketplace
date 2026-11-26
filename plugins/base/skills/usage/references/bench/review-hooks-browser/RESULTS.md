# Results: review benchmark on the hooks + browser snapshot (2,905 lines, 14 known bugs)

## Setup runs

One line per run, written by `bench.py run`. Results are compared only within one setup id; `results.json` holds the numbers.

| Run | Setup | Model / effort | Key caught (strict / with partials) | Real cost (with refuter) | Slowest agent | Date |
|---|---|---|---|---|---|---|
| J | review-mr-v1-354ec1e3-c57ac89f | claude-haiku-5-5 max | incomplete: stopped by hand: slice reports were not saved (deny rule on model-bench), so the refuter had no input; finished: slice-1, slice-2, slice-3, slice-4, slice-5 | $1.89 ($1.89) | n/a | 2026-11-25 |
| K | review-mr-v1-354ec1e3-c57ac89f | claude-haiku-5-5 max | incomplete: stopped by hand: switching to parallel slices; finished: none | $0.00 ($0.00) | n/a | 2026-11-25 |
| L | review-mr-v1-354ec1e3-c57ac89f | claude-haiku-5-5 max | incomplete: slice-4, slice-8, slice-9 hit the 5-hour usage limit (logged as 'success'); Bash was denied in dontAsk mode in every call; finished: slice-1, slice-2, slice-3, slice-5, slice-6, slice-7, runit | $2.74 ($2.74) | n/a | 2026-11-25 |
| M | review-mr-v1-354ec1e3-c57ac89f | claude-haiku-5-5 max | 11 / 12.0; resumed: slice-3, slice-5, slice-6, slice-7, slice-8, slice-9, runit rerun | $8.40 ($11.19); spent $25.85 with broken attempts | 29.2 min | 2026-11-26 |

## History: runs B to I (not ranked)

Runs B to I used different briefs and slicings (3 slices with or without a cross-file agent, run D's 7 named slices, PR #251's first brief, the brief of commit `c3f54be`) and have no checker model, dates or hashes on record. They are history, not a setup: they get no entry in `results.json` and are never ranked. Run I is the reference point for the first `review-mr-v1` baseline (task 7.1 of `add-usage-models-mode`): Haiku 5.5 max, 7 hand-cut slices plus run-it, Opus 5.5 medium refuter, 12 strict / 13 with partials of 14, all 4 highs, $11.59 with the refuter. The Haiku 7-slice range of runs D, G and I is 10 to 13 strict of 14, all 4 highs. Their briefs are in `history/`; their run outputs stay outside the repo.

| Run | Setup | Key caught (strict / with partials) | Real cost | Requests >100k | Notes |
|---|---|---|---|---|---|
| B | Opus 5.5 medium: 3 component slices + 1 cross-file | 6 / 7 | $6.38 | n/a | cross-file agent most expensive, no unique key catch |
| C | Haiku 5.5 max: same slices | 7 / 8.5 | $3.34 | 69% | cross-file agent alone caught H1 |
| D | Haiku 5.5 max: 7 small slices + narrow cross-file, plus "what the code does NOT set" lens (tool defaults, verify tool claims against tool source/docs, swallowed errors, false blocks) | **13 / 13.5** | $5.08 | 71% | found all highs (sandbox off, literal password fill, gate bypass); cross-file added nothing unique; agents left 27 temp dirs, one in the real repo |

Reference point: the full review-mr setup (11 Opus agents) cost $21.68 on 1,743 lines of #237/#238 and missed the push-gate bypass that one Haiku max agent found on #238 ($0.50).

Lessons: (1) the defaults lens, not the model, closed the high-severity gap; (2) small slices raise recall but did not keep Haiku under 100k: tool output and stub runs grow context, so 70%+ of requests pay the 5x tier; (3) the cross-file agent rarely adds unique findings when slices are small; (4) agents do not clean up unless told to and checked.

## Run E (added 2026-11-22)

| E | Haiku 5.5 max: 3 component slices, no cross-file, with the run-D lens | 9 / 9.5 | $4.25 | 87% | missed S1 (literal password fill); slowest agent 32.9 min; cleanup instruction worked (no leftovers) |

Wall time (slowest agent): B 8.9 min, C 23.1, D 23.7, E 32.9. Cost per caught key bug: B $1.06, C $0.48, D $0.39, E $0.47.

Decision: fewer, wider Haiku agents grow their own context further (87% of requests over 100k, peak 425k), so they are not cheaper in practice and miss narrow-contract bugs. Use run D's slicing (one tool contract or component per slice) with the lens, and drop the cross-file agent (no unique key catch in B, D or E).

## Run F and the refuter test (added 2026-11-22)

| F | Opus 5.5 medium: 3 component slices, no cross-file, with the run-D lens (same prompts as E) | 9 / 9.5 | $6.99 | 37% (flat price, no tier) | slowest agent 9.2 min; missed H1, H3, S2, S3; caught S1, D1 and both halves of S5 that E missed; two agents listed the S2 bug as "sound"; no leftovers |

Opus has no long-context tier and stayed small (peak 146k vs 425k for E, 190 requests vs 252), but at Opus prices it cost $0.78 per caught key bug vs D's $0.39. Same miss count as E, different misses. `--fast` (Opus) is about 3.5x faster than the Haiku default, not better.

Refuter (review-mr step 5) on run F's 35 unique findings, brief in `refuter-brief.md`, no answer key:

| Refuter | Survives / refuted / unsettled | Cost | Share of run F | Active time |
|---|---|---|---|---|
| Opus high | 34 / 1 / 0 | $2.76 | +39% | 7.9 min |
| Opus medium | 33 / 1 / 1 | $1.74 | +25% | 5.8 min |

Both kept every key bug and refuted the same one finding (F3-13, umask; they were right and the checker wrong: the file sits in a 700 dir). Medium left F2-5 unsettled where high marked it derived; both downgraded the sandbox finding (key high S6) to medium(-high). Neither can catch a bug an agent wrongly lists as "sound" (S2), since refuters only see findings.

Recommendation: refuters on Opus medium (base effort), not one above; high bought no different verdict for 59% more. Single sample.

## Runs G, H and I (added 2026-11-23)

| Run | Setup | Key caught (strict / with partials) | Highs | Cost | Slowest agent |
|---|---|---|---|---|---|
| G | Haiku 5.5 max, PR #251 brief (first version), D's 7 slices + run-it, Opus medium refuter | 10 / 11 | 4 / 4 | $5.55, $9.82 with refuter | 19.7 min |
| H | Opus 5.5 medium, D's exact prompts and 7 slices, no cross-file | 10 / 11 | 4 / 4 | $10.37 | 14.6 min |
| I | Haiku 5.5 max, PR #251 brief with D's lens and context wording restored, 7 slices + run-it, Opus medium refuter | 12 / 13 | 4 / 4 | $7.89, $11.59 with refuter ($3.70) | 26.9 min |

Haiku 7-slice runs D, G, I: mean 11.7 strict (range 10-13), all highs every time. Opus on D's prompts (H) found fewer for twice the price: `--fast` buys time, not recall.

G's drop to 10 traced to the first brief: a 40-call soft budget cut slice 4 short (S3) and a one-path "sound" claim hid H3. Restoring D's wording (I) recovered both.

Refuters: G 78 findings, 70 kept, 3 new from sound-list samples; I 75 findings, 65 kept, 4 new from sound-list samples (one high). Both lowered key highs (I: S1 and S6 to medium), so the lowered-high flag is needed. Refuter cost $3.70-4.27 per run; kept for all severities by the user's choice.

Run-it agent: unique key catch in G (H4), none in I; keep until the plan's five-review drop test. Tool quirks: some subagents are refused report files by the Write tool, so the main session saves the reply; one run-it test reached the network by mistake (no credential).
