# Design

## Context

Slice owners already grep "every changed export, command, config key or file name" (agent brief, step 2). A file-based route is reached by a URL that the file name does not contain (`server/api/items.post.ts` is `POST /api/items`), so that grep misses its callers. The only cross-file agent is the counterpart contract agent, kept that way after the benchmark: in runs B, D and E it added no key bug the slices missed. In run C, on three wide component slices, it alone caught H1, and run D's seven small slices caught H1 without it.

## Goals / Non-Goals

**Goals:**
- Route, event and message seams inside one repo get the same check as export seams, at no extra agent cost.
- Server-rendering bugs get a lens, with zero cost for apps that don't render on the server.

**Non-Goals:**
- A contract agent for in-repo pairs declared in the rules.
- Framework support beyond Nuxt and Next.js in this change; the detection table is where others go.
- A benchmark run.

## Decisions

- **Widen the seam step, no new agent.** The owner derives the URL of each changed file-based route (Nuxt `server/api/**` and `server/routes/**`, Next.js `app/**/route.*` and `pages/api/**`) and greps for it, and greps event and message names it changes. It compares request and response fields both ways. Rejected: a contract agent for in-repo pairs. Its one unique catch (run C) came with wide slices, which the skill no longer cuts, and nothing yet shows an in-repo pair needs more than the widened seam step. A benchmark on in-repo route drift would reopen it.
- **Slice a route with its callers.** When planning slices, the main session greps each changed route's URL among the changed files and keeps the hits in the route's slice while under the hard limit. Over the limit, the seam step still covers them.
- **Detection by a script.** `scripts/find_server_rendering.py` lists tracked `nuxt.config.*` and `next.config.*` files at head and reports per app root whether it renders on the server, with the line that decided it. A table maps framework to config names and the setting that turns server rendering off, so adding a framework is one row. Text reading, not evaluation, with comments and strings skipped and only the top level of the config object counted: a config that computes the value, sets it twice or sets it only in a nested block is reported as `unknown`, which counts as rendering on the server and is said in the run summary.
- **Override in the rules body.** A `## Server rendering` section lists `<repo>: on` or `<repo>: off`. The rules body is already prose the main session reads, so no parser change.

## Risks / Trade-offs

- Regex detection misses computed configs and layers → `unknown` defaults to on, and the rules override exists.
- A route's URL can also be built at runtime (`$fetch(base + id)`, `${apiBase}/items`) → the owner greps the static prefix and the tail after a base variable, and names a caller it cannot resolve in its ledger; a miss stays possible.
- Regex reading can misjudge an app → only the top-level setting counts; nested ones (`routeRules`, `$production`) and computed or doubled ones give `unknown`, which counts as on. A Next.js static export counts as rendering, since its pages are rendered to HTML at build time.
