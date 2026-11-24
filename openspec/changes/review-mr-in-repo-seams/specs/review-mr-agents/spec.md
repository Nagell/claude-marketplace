# Spec Delta

## MODIFIED Requirements

### Requirement: Slices follow one contract
Files SHALL be grouped so that a slice holds one tool contract or component: a script with its tests and the doc section describing it, a hook with its `hooks.json` entry, a component with its composable and spec, a changed route with the changed files that call it by its URL.

#### Scenario: One contract, several files
- **WHEN** an MR changes a hook script, its `hooks.json` entry and its test
- **THEN** the three files are one slice

#### Scenario: Route and caller both changed
- **WHEN** an MR changes `server/api/items.post.ts` and a page that posts to `/api/items`, together under the hard slice limit
- **THEN** both files are in one slice

### Requirement: No cross-file agent by default
The skill SHALL NOT spawn a cross-file agent by default. Run B, D and E found no key bug that only a cross-file agent caught. The one exception is the contract owner: when step 1a found a counterpart MR, exactly one contract agent SHALL apply the Contract lens (shape, meaning, duplicated rules, end to end, deploy order) against the counterpart.

#### Scenario: No counterpart
- **WHEN** a plan has four slices and no counterpart MR
- **THEN** only the four slice owners run and no cross-file agent is spawned

#### Scenario: Counterpart exists
- **WHEN** step 1a found a counterpart MR
- **THEN** one contract agent runs the Contract lens and the deploy-order check, and no other cross-file agent runs

#### Scenario: Seam between slices
- **WHEN** a changed export in one slice is consumed by a file in another slice
- **THEN** the owner of the slice that holds the export greps every consumer of it, not only one

#### Scenario: Route reached by URL
- **WHEN** a slice changes a file-based server route and a file in another slice calls that route's URL
- **THEN** the owner of the route's slice finds the caller by the URL, and compares the fields each side sends and reads

#### Scenario: Event or message name
- **WHEN** a slice changes what an emitted event or a websocket message carries
- **THEN** the owner finds every listener by the event or message name and checks it reads what is now sent

### Requirement: Engine question kept
The skill SHALL keep the step 0 question that chooses Claude, Codex or both, with `Claude (Recommended)` as the default, and SHALL describe the Claude option as Haiku slice owners with Opus refuters. It SHALL NOT add a model question. With the Codex engine, the skill SHALL run one Codex task per slice, name its reports `wave<n>-<slice>.txt` and pass the effort answer as `--effort`.

#### Scenario: First tool call
- **WHEN** a review starts and the repo's rules name a counterpart
- **THEN** the rules lookup runs, then one question dialog with the engine, counterpart and effort questions

#### Scenario: Codex effort
- **WHEN** the user picks Codex and answers `High` in the effort question
- **THEN** each Codex slice task runs with `--effort high`

## ADDED Requirements

### Requirement: Counterpart question only with a counterpart
Before the step 0 dialog the skill SHALL run only the local rules lookup. It SHALL ask the counterpart question only when the rules file has a `## Counterpart` section.

#### Scenario: No counterpart in the rules
- **WHEN** a review starts and there is no rules file, or it has no `## Counterpart` section
- **THEN** the dialog asks only the engine and effort questions, and step 1a is skipped


### Requirement: Server-rendering lens
The main session SHALL read the framework configs at the reviewed head once and decide per app whether it renders on the server. Only then SHALL each slice holding that app's source files get the server-rendering lens: hydration mismatches, browser-only globals during server render, module-level state shared between requests, secrets in public runtime config, and clashing or doubled data-fetch keys.

#### Scenario: Nuxt with server rendering
- **WHEN** an app's `nuxt.config` does not set `ssr: false` and a slice changes its pages
- **THEN** that slice's brief carries the server-rendering lens

#### Scenario: Client-only app
- **WHEN** `nuxt.config` sets `ssr: false`, or a Next.js config sets `output: 'export'`
- **THEN** no brief carries the lens and no brief text is added

#### Scenario: No supported framework
- **WHEN** the repo has no Nuxt or Next.js config
- **THEN** no brief carries the lens

### Requirement: Server-rendering override in the rules
A rules file SHALL be able to force the server-rendering lens on or off per repo, and that SHALL win over detection, because layers, environment variables and per-route settings can switch rendering in ways a config read cannot see.

#### Scenario: Detection says client-only, rules say on
- **WHEN** detection finds `ssr: false` but the rules say server rendering is on for the repo
- **THEN** the lens goes into the briefs of slices holding the repo's source files
