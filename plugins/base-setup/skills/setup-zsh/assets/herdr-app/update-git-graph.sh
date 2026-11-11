#!/usr/bin/env bash
set -euo pipefail

repo="$HOME/.local/src/herdr-git-graph"
fork_url="https://github.com/Nagell/herdr-git-graph.git"
upstream_url="https://github.com/werlang/herdr-git-graph.git"
feature_branch="feat/stage-commit-discard"
obsolete_branch="backup/pre-rebase-stage-commit-discard"

mkdir -p "$HOME/.local/src"

if [ ! -d "$repo/.git" ]; then
  git clone "$fork_url" "$repo"
fi

if [ -n "$(git -C "$repo" status --porcelain)" ]; then
  printf '%s\n' "Refusing to update: $repo has uncommitted changes." >&2
  exit 1
fi

git -C "$repo" remote set-url origin "$fork_url"
if git -C "$repo" remote get-url upstream >/dev/null 2>&1; then
  git -C "$repo" remote set-url upstream "$upstream_url"
else
  git -C "$repo" remote add upstream "$upstream_url"
fi

git -C "$repo" fetch --prune origin
git -C "$repo" fetch --prune upstream
git -C "$repo" switch main
git -C "$repo" merge --ff-only origin/main
git -C "$repo" switch "$feature_branch"
git -C "$repo" merge --ff-only "origin/$feature_branch"
git -C "$repo" branch -D "$obsolete_branch" 2>/dev/null || true
(cd "$repo" && ./sync.sh)

printf '%s\n' 'Git Graph is updated and synced into Herdr.'
