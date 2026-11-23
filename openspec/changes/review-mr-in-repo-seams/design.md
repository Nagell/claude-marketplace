# Design

## Context

Slice owners already grep "every changed export, command, config key or file name" (agent brief, step 2). A file-based route is reached by a URL that the file name does not contain (`server/api/items.post.ts` is `POST /api/items`), so that grep misses its callers. The only cross-file agent is the counterpart contract agent, kept that way after benchmark runs B, D and E.

## Goals / Non-Goals

**Goals:**
- Route, event and message seams inside one repo get the same check as export seams, at no extra agent cost.
- Server-rendering bugs get a lens, with zero cost for apps that don't render on the server.

**Non-Goals:**
- A contract agent for in-repo pairs declared in the rules.
- Framework support beyond Nuxt and Next.js in this change; the detection table is where others go.
- A benchmark run.

## Decisions

- **Widen the seam step, no new agent.** The owner derives the URL of each changed file-based route (Nuxt `server/api/**` and `server/routes/**`, Next.js `app/**/route.*` and `pages/api/**`) and greps for it, and greps event and message names it changes. It compares request and response fields both ways. Rejected: a contract agent for in-repo pairs, which reopens the benchmarked decision without evidence.
- **Slice a route with its callers.** When planning slices, the main session greps each changed route's URL among the changed files and keeps the hits in the route's slice while under the hard limit. Over the limit, the seam step still covers them.
- **Detection by a script.** `scripts/find_server_rendering.py` lists tracked `nuxt.config.*` and `next.config.*` files at head and reports per app root whether it renders on the server, with the line that decided it. A table maps framework to config names and the setting that turns server rendering off, so adding a framework is one row. Regex reading, not evaluation: a config that computes the value is reported as `unknown`, which counts as rendering on the server and is said in the run summary.
- **Override in the rules body.** A `## Server rendering` section lists `<repo>: on` or `<repo>: off`. The rules body is already prose the main session reads, so no parser change.

## Risks / Trade-offs

- Regex detection misses computed configs and layers → `unknown` defaults to on, and the rules override exists.
- A route's URL can also be built at runtime (`$fetch(base + id)`) → the owner greps the static prefix; a miss stays possible.
