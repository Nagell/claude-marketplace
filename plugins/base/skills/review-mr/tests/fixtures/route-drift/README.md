# Route drift fixture

A server route and the page that calls it, in one repo, out of step: the route
now requires `quantity`, and the page still posts only `name`. Nothing imports
the route, so a grep for changed exports finds no caller.

Use it to check the seam step of `references/agent-brief.md`. A real run would
put both files in one slice (a changed route stays with its changed callers),
so force the split: give one owner the brief with only
`server/api/items.post.ts` as its slice, and tell it the MR added the
`quantity` requirement. It must find `pages/items.vue` by the URL `/api/items`
and report that the page does not send `quantity`, so every save now fails
with a 400. It is a fragment, not a runnable Nuxt app: there is no
`package.json`.
