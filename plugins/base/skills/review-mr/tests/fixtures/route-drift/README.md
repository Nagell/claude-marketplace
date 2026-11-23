# Route drift fixture

A server route and the page that calls it, in one repo, out of step: the route
now requires `quantity`, and the page still posts only `name`. Nothing imports
the route, so a grep for changed exports finds no caller.

Use it to check the seam step of `references/agent-brief.md`: put
`server/api/items.post.ts` and `pages/items.vue` in two different slices and
give each owner the brief. The owner of the route's slice must find the page by
the URL `/api/items` and report that the page does not send `quantity`, so
every save now fails with a 400.
