#!/usr/bin/env python3
"""Helpers for posting line-anchored review comments on a GitLab MR.

Wraps ``glab api`` because glab's own ``-f``/``-F`` flags build a flat JSON body
and silently drop the nested ``position`` object, which turns an inline thread
into an unanchored general note. Every subcommand that writes verifies the
anchor came back populated, so a silent downgrade fails loudly instead of
looking like success.

Subcommands:
  refs         print diff_refs + changed paths for an MR
  counterpart  find the other repo's MR for the same change (same branch, or linked)
  diff         dump the MR diff to a file
  added-lines  list line numbers that are ADDED in the new file (valid anchors)
  list         list existing non-system notes (optionally filtered by author)
  threads      dump discussions as JSON (ownership, resolved state, full bodies)
  post         post a positioned discussion from a markdown file
  edit         replace an existing note's body, keeping its anchor
  reply        append a note to an existing discussion
  resolve      mark a discussion resolved  (refuses threads we did not open)
  unresolve    reopen a discussion         (refuses threads we did not open)
  note         post a general, non-resolvable MR note from a markdown file
  approve      approve the MR at an exact head sha
  me           print the username glab is authenticated as

Review flow (one GitLab review, one notification, one verdict):
  drafts          list the pending draft notes we hold on the MR
  draft           create one draft: inline on a line or range, outside the diff,
                  general, or a reply on a thread; recorded in a ledger file
  submit          publish every draft with a summary note and a review state
  discard-drafts  delete the drafts a ledger recorded that are still pending
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from urllib.parse import quote


def glab(path: str, repo_dir: str | None = None, method: str = "GET",
         body: dict | None = None) -> dict | list:
    """Call ``glab api`` and parse the JSON response.

    Raises SystemExit with the raw output when the response is not JSON, which
    is what a 502 from GitLab looks like. A write may still have landed in that
    case, so callers must re-list before retrying.
    """
    cmd = ["glab", "api", "--method", method, path]
    stdin = None
    if body is not None:
        cmd += ["-H", "Content-Type: application/json", "--input", "-"]
        stdin = json.dumps(body)
    proc = subprocess.run(
        cmd, cwd=repo_dir, input=stdin, capture_output=True, text=True
    )
    # bulk_publish and DELETE answer 204 with no body.
    if proc.returncode == 0 and not proc.stdout.strip():
        return {}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        sys.exit(
            f"glab api {method} {path} did not return JSON.\n"
            f"stdout: {proc.stdout.strip()[:500]}\n"
            f"stderr: {proc.stderr.strip()[:500]}\n"
            "If this was a write, re-run the `list` subcommand before retrying "
            "so you do not double-post."
        )


def mr_base(project: str, iid: str) -> str:
    return f"projects/{project}/merge_requests/{iid}"


def cmd_refs(a) -> None:
    d = glab(mr_base(a.project, a.iid), a.repo_dir)
    refs = d["diff_refs"]
    print(f"base_sha  {refs['base_sha']}")
    print(f"start_sha {refs['start_sha']}")
    print(f"head_sha  {refs['head_sha']}")
    print(f"branch    {d['source_branch']} -> {d['target_branch']}")
    print(f"title     {d.get('title') or ''}")
    if a.description_out:
        with open(a.description_out, "w", encoding="utf-8") as fh:
            fh.write(d.get("description") or "")
        print(f"description -> {a.description_out}")
    print("changed:")
    for c in _changes(a):
        print(f"  {c['new_path']}" + ("  (diff withheld)" if c["withheld"] else ""))


def _refs(a) -> dict:
    return glab(mr_base(a.project, a.iid), a.repo_dir)["diff_refs"]


def _paged(path: str, repo_dir: str | None) -> list[dict]:
    """Every item of a GitLab list endpoint, across all pages.

    A single request returns one page (20 items by default, 100 at most), and a
    truncated list reads exactly like a complete one.
    """
    per_page = 100
    sep = "&" if "?" in path else "?"
    out: list[dict] = []
    page = 1
    last = None
    while True:
        batch = glab(f"{path}{sep}per_page={per_page}&page={page}", repo_dir)
        # Some endpoints (draft_notes) ignore paging and answer every page with
        # the full list; a repeated page means everything has been read.
        if batch == last:
            return out
        out += batch
        if len(batch) < per_page:
            return out
        last = batch
        page += 1


def _changes(a) -> list[dict]:
    """Every file's diff, from /diffs.

    /changes collapses a large file's diff to an empty string, which reads
    exactly like "nothing changed here" and silently drops its anchors. A file
    whose diff GitLab withheld is flagged rather than fatal: the rest of the MR
    stays reviewable, and only an anchor on that file is refused.
    """
    out = _paged(f"{mr_base(a.project, a.iid)}/diffs", a.repo_dir)
    for c in out:
        c["withheld"] = bool(c.get("too_large") or (c.get("collapsed") and not c["diff"]))
        if c["withheld"]:
            print(f"note: GitLab withheld the diff of {c['new_path']} (too large); "
                  "it cannot take an inline anchor - review it at head and use "
                  "--outside for findings on it", file=sys.stderr)
    return out


def cmd_diff(a) -> None:
    out = []
    for c in _changes(a):
        out.append(f"##### FILE: {c['new_path']}"
                   + ("  (diff withheld by GitLab)" if c["withheld"] else ""))
        out.append(c["diff"])
    text = "\n".join(out)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"wrote {a.out} ({len(text.splitlines())} lines)")


def added_line_map(changes: list[dict]) -> dict[str, dict[int, str]]:
    """Map new-file line numbers to their content, for ADDED lines only.

    Anchoring on an added line is the reliable case: GitLab accepts ``new_line``
    with no ``old_line``. Context and removed lines need different position
    fields, so steering callers to added lines avoids a class of rejected
    positions.
    """
    result: dict[str, dict[int, str]] = {}
    for c in changes:
        n = None
        added: dict[int, str] = {}
        for line in c["diff"].splitlines():
            m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)", line)
            if m:
                n = int(m.group(1))
                continue
            if n is None:
                continue
            # "\ No newline at end of file" belongs to the line before it.
            if line.startswith("-") or line.startswith("\\"):
                continue
            if line.startswith("+"):
                added[n] = line[1:]
            n += 1
        result[c["new_path"]] = added
    return result


def cmd_added_lines(a) -> None:
    amap = added_line_map(_changes(a))
    for path, added in amap.items():
        if a.file and not path.endswith(a.file):
            continue
        print(f"== {path}")
        for line in sorted(added):
            print(f"  {line}: {added[line][:100]}")


def cmd_list(a) -> None:
    ds = _paged(f"{mr_base(a.project, a.iid)}/discussions", a.repo_dir)
    for d in ds:
        for note in d["notes"]:
            if note.get("system"):
                continue
            if a.author and note["author"]["username"] != a.author:
                continue
            pos = note.get("position")
            anchor = (f"{pos.get('new_path')}:{pos.get('new_line') or pos.get('old_line')}"
                      if pos else "UNANCHORED")
            head = note["body"].splitlines()[0][:70] if note["body"] else ""
            state = "resolved" if note.get("resolved") else "open"
            print(f"{d['id']} {note['id']} {note['author']['username']} "
                  f"[{state}] {anchor}")
            print(f"   {head}")


def _verify_anchor(note: dict, expect_path: str, expect_line: int) -> None:
    pos = note.get("position")
    if not pos:
        sys.exit(
            f"note {note['id']} posted but position is NULL - it became a "
            "general note, not an inline thread. GitLab rejected the position; "
            "check that the line is an ADDED line (see `added-lines`) and that "
            "head_sha matches the MR."
        )
    got = (pos["new_path"], pos["new_line"])
    if got != (expect_path, expect_line):
        sys.exit(f"note {note['id']} anchored to {got}, expected "
                 f"{(expect_path, expect_line)}")
    print(f"  note={note['id']} resolvable={note.get('resolvable')} "
          f"anchored={pos['new_path']}:{pos['new_line']} "
          f"({len(note['body'])} chars)")


def cmd_post(a) -> None:
    refs = _refs(a)
    amap = added_line_map(_changes(a))
    if a.line not in amap.get(a.path, {}):
        sys.exit(
            f"{a.path}:{a.line} is not an added line in this MR. Run "
            "`added-lines` and pick one, or GitLab will drop the anchor."
        )
    body = open(a.file, encoding="utf-8").read()
    payload = {
        "body": body,
        "position": {
            "position_type": "text",
            "base_sha": refs["base_sha"],
            "start_sha": refs["start_sha"],
            "head_sha": refs["head_sha"],
            "new_path": a.path,
            "old_path": a.path,
            "new_line": a.line,
        },
    }
    d = glab(f"{mr_base(a.project, a.iid)}/discussions", a.repo_dir, "POST", payload)
    _verify_anchor(d["notes"][0], a.path, a.line)
    print(f"  discussion={d['id']}")


def cmd_edit(a) -> None:
    body = open(a.file, encoding="utf-8").read()
    note = glab(
        f"{mr_base(a.project, a.iid)}/discussions/{a.discussion}/notes/{a.note}",
        a.repo_dir, "PUT", {"body": body},
    )
    if "id" not in note:
        sys.exit(f"note {a.note} not updated: {note.get('message', note)}")
    pos = note.get("position")
    if note.get("type") != "DiffNote":
        print(f"  note={note['id']} {len(note['body'])} chars (general note)")
        return
    if not pos:
        sys.exit(f"note {a.note} lost its anchor after the edit")
    print(f"  note={note['id']} {len(note['body'])} chars, still anchored "
          f"{pos['new_path']}:{pos['new_line']}")


SEVERITY = re.compile(r"\*\*(Critical|Blocker|High|Medium|Low)\b")
SUGGESTION = re.compile(r"^\s*(`{3,}|~{3,})suggestion", re.M)


def severity(body: str) -> str | None:
    """The severity label a finding we posted opens with, if any."""
    m = SEVERITY.search(body.splitlines()[0] if body else "")
    return m.group(1).lower() if m else None


def current_user(repo_dir: str | None) -> str:
    """The username glab is authenticated as - who "our" comments belong to."""
    return glab("user", repo_dir)["username"]


def _first_human_note(discussion: dict) -> dict | None:
    for n in discussion["notes"]:
        if not n.get("system"):
            return n
    return None


def _discussion(a, did: str) -> dict:
    d = glab(f"{mr_base(a.project, a.iid)}/discussions/{did}", a.repo_dir)
    if "notes" not in d:
        sys.exit(
            f"no discussion {did} on !{a.iid}: {d.get('message', d)}. "
            "Discussion ids are long hex strings - take the whole one from "
            "`threads`, not the shortened form a summary printed."
        )
    return d


def _require_ours(a, did: str) -> dict:
    """Refuse to change the state of a thread somebody else opened.

    Resolving a colleague's or a bot's thread claims their finding is dealt
    with, which is theirs to say. The check lives here rather than in the
    prose because a review run is long and this is the irreversible part.
    """
    d = _discussion(a, did)
    note = _first_human_note(d)
    if note is None:
        sys.exit(f"discussion {did} has no human note - nothing to own")
    me = current_user(a.repo_dir)
    owner = note["author"]["username"]
    if owner != me:
        sys.exit(
            f"refusing: discussion {did} was opened by {owner}, not {me}. "
            "Only the author of a thread may resolve or reopen it - reply "
            "instead if you want to say something on it."
        )
    return d


def cmd_me(a) -> None:
    print(current_user(a.repo_dir))


def cmd_threads(a) -> None:
    """Dump discussions as JSON: ownership, resolved state and full bodies.

    A rerun has to judge whether each of our old findings was actually
    addressed, which needs the whole conversation, not the one-line summary
    `list` prints.
    """
    ds = _paged(f"{mr_base(a.project, a.iid)}/discussions", a.repo_dir)
    me = current_user(a.repo_dir)
    out = []
    for d in ds:
        notes = [n for n in d["notes"] if not n.get("system")]
        if not notes:
            continue
        first = notes[0]
        if a.mine and first["author"]["username"] != me:
            continue
        pos = first.get("position") or {}
        out.append({
            "discussion_id": d["id"],
            "opened_by": first["author"]["username"],
            "ours": first["author"]["username"] == me,
            "resolvable": bool(first.get("resolvable")),
            "resolved": bool(first.get("resolved")),
            "severity": severity(first["body"]),
            "path": pos.get("new_path"),
            "new_line": pos.get("new_line"),
            "head_sha": pos.get("head_sha"),
            "last_note_by": notes[-1]["author"]["username"],
            "notes": [
                {
                    "note_id": n["id"],
                    "author": n["author"]["username"],
                    "created_at": n["created_at"],
                    "body": n["body"],
                }
                for n in notes
            ],
        })
    text = json.dumps({"me": me, "discussions": out}, indent=2)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        ours = sum(1 for t in out if t["ours"])
        print(f"wrote {a.out}: {len(out)} threads, {ours} ours "
              f"({sum(1 for t in out if t['ours'] and t['resolved'])} of ours resolved)")
    else:
        print(text)


def cmd_reply(a) -> None:
    body = open(a.file, encoding="utf-8").read()
    note = glab(
        f"{mr_base(a.project, a.iid)}/discussions/{a.discussion}/notes",
        a.repo_dir, "POST", {"body": body},
    )
    print(f"  replied note={note['id']} on discussion={a.discussion} "
          f"({len(note['body'])} chars)")


def _set_resolved(a, want: bool) -> None:
    _require_ours(a, a.discussion)
    d = glab(
        f"{mr_base(a.project, a.iid)}/discussions/{a.discussion}",
        a.repo_dir, "PUT", {"resolved": want},
    )
    note = _first_human_note(d)
    got = bool(note.get("resolved")) if note else None
    if got is not want:
        sys.exit(
            f"discussion {a.discussion} still reads resolved={got} after asking "
            f"for {want} - GitLab did not apply it, check the thread by hand."
        )
    print(f"  discussion={a.discussion} resolved={got}")


def cmd_resolve(a) -> None:
    _set_resolved(a, True)


def cmd_unresolve(a) -> None:
    _set_resolved(a, False)


def cmd_note(a) -> None:
    """Post a general note: the finish-mode comment that carries what is left.

    It must not be resolvable, or it blocks a merge under "all threads must be
    resolved" and the approval next to it means nothing.
    """
    body = open(a.file, encoding="utf-8").read()
    note = glab(f"{mr_base(a.project, a.iid)}/notes", a.repo_dir, "POST",
                {"body": body})
    if "id" not in note:
        sys.exit(f"note not created: {note.get('message', note)}")
    if note.get("resolvable"):
        sys.exit(
            f"note {note['id']} was posted but GitLab made it resolvable, so it "
            "blocks the merge. Resolve it by hand or edit it out."
        )
    print(f"  note={note['id']} resolvable=False ({len(note['body'])} chars)")


def diff_rows(diff: str) -> dict[int, tuple[int, int, str | None]]:
    """Index one file's diff rows by new-file line: (old_line, new_line, kind).

    kind is "new" for an added row and None for unchanged context. An added row
    carries the next unconsumed old line, which is what GitLab's line codes use.
    Removed rows only advance the old counter: a comment lands on the file as
    the MR leaves it.
    """
    rows: dict[int, tuple[int, int, str | None]] = {}
    old = new = None
    for line in diff.split("\n"):
        m = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)", line)
        if m:
            old, new = int(m.group(1)), int(m.group(2))
            continue
        if old is None or not line or line.startswith("\\"):
            continue
        if line.startswith("+"):
            rows[new] = (old, new, "new")
            new += 1
        elif line.startswith("-"):
            old += 1
        else:
            rows[new] = (old, new, None)
            old += 1
            new += 1
    return rows


def _endpoint(row: tuple[int, int, str | None], path: str) -> dict:
    # A context endpoint goes out as type "new": some GitLab versions reject a
    # null type, and a span ending on a context line is routine.
    old, new, kind = row
    digest = hashlib.sha1(path.encode()).hexdigest()
    return {
        "line_code": f"{digest}_{old}_{new}",
        "type": kind or "new",
        "old_line": old if kind != "new" else None,
        "new_line": new,
    }


def build_position(a, start: int, end: int, body: str = "") -> dict:
    """Position for a thread spanning start..end, anchored on the end line."""
    change = next((c for c in _changes(a) if c["new_path"] == a.path), None)
    if change is None:
        sys.exit(f"{a.path} is not a changed file in !{a.iid}")
    if change.get("withheld"):
        sys.exit(f"GitLab withheld the diff of {a.path}, so it has no line to "
                 "anchor on. Draft it with --outside instead.")
    rows = diff_rows(change["diff"])
    covered = [n for n in range(start, end + 1) if n in rows]
    if not covered:
        sys.exit(
            f"{a.path}:{start}-{end} is outside the diff. Draft it with "
            "--outside as a general note in the same review."
        )
    gaps = [n for n in range(covered[0], covered[-1] + 1) if n not in rows]
    if gaps:
        sys.exit(f"{a.path}:{start}-{end} spans two hunks (lines {gaps[0]}-{gaps[-1]} "
                 "are outside the diff). Anchor on the part inside one hunk, or "
                 "split the finding.")
    if (covered[0], covered[-1]) != (start, end):
        note = (f"clamped {a.path}:{start}-{end} to {covered[0]}-{covered[-1]}, "
                "the rest is outside the diff")
        if SUGGESTION.search(body):
            sys.exit(f"{note}. The suggestion fence was written for the whole span "
                     "and its offsets would replace the wrong lines: rewrite it for "
                     "the clamped span, or drop the fence.")
        print(f"  {note}")
    start, end = covered[0], covered[-1]
    refs = _refs(a)
    old, new, kind = rows[end]
    pos = {
        "position_type": "text",
        "base_sha": refs["base_sha"],
        "start_sha": refs["start_sha"],
        "head_sha": refs["head_sha"],
        "new_path": change["new_path"],
        "old_path": change["old_path"],
        "new_line": new,
    }
    if kind != "new":
        pos["old_line"] = old
    if start != end:
        pos["line_range"] = {
            "start": _endpoint(rows[start], change["new_path"]),
            "end": _endpoint(rows[end], change["new_path"]),
        }
    return pos


def outside_body(ref: str, body: str) -> str:
    """Wrap a finding on lines no hunk touched as a general review note.

    A suggestion fence only applies inside a diff-anchored thread, so it turns
    into a plain code sample rather than a dead apply button.
    """
    path = ref.rsplit(":", 1)[0]
    lang = path.rsplit(".", 1)[-1] if "." in path.rsplit("/", 1)[-1] else ""
    body = re.sub(r"^(\s*)(`{3,}|~{3,})suggestion\S*", rf"\1\2{lang}", body,
                  flags=re.M)
    return f"**Outside the diff - `{ref}`**\n\n{body}"


def _drafts(a) -> list[dict]:
    return _paged(f"{mr_base(a.project, a.iid)}/draft_notes", a.repo_dir)


def _ledger(path: str, required: bool = False) -> list[dict]:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        if required:
            sys.exit(f"no ledger at {path}. Check the path: a mistyped ledger would "
                     "read as no drafts of ours and leave them pending.")
        return []


def _write_ledger(path: str, ledger: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(ledger, fh, indent=2)


def cmd_drafts(a) -> None:
    ds = _drafts(a)
    for d in ds:
        pos = d.get("position") or {}
        where = f"{pos.get('new_path')}:{pos.get('new_line')}" if pos else "general"
        if d.get("discussion_id"):
            where = f"reply on {d['discussion_id']}"
        head = (d.get("note") or "").splitlines()[0][:70] if d.get("note") else ""
        print(f"{d['id']} {where}\n   {head}")
    print(f"{len(ds)} pending draft(s)")


def cmd_draft(a) -> None:
    """Create one draft note and record its id in the ledger.

    The ledger is what lets a failed or interrupted run delete its own drafts,
    which the next run would otherwise mistake for a review the user started.
    """
    body = open(a.file, encoding="utf-8").read()
    payload: dict = {"note": body}
    kind = "general"
    resolve_after_submit = False
    if a.reply:
        if a.resolve and a.reopen:
            sys.exit("--resolve and --reopen contradict each other")
        thread = (_require_ours(a, a.reply) if (a.resolve or a.reopen)
                  else _discussion(a, a.reply))
        first = _first_human_note(thread) or {}
        # Publishing a draft reply without resolve_discussion unresolves the
        # thread (DraftNotes::PublishService#set_discussion_resolve_status).
        if first.get("resolved") and not (a.resolve or a.reopen):
            sys.exit(
                f"refusing: discussion {a.reply} is resolved, and publishing a "
                "reply without --resolve reopens it. Pass --resolve to keep it "
                "closed, or --reopen if reopening is the point."
            )
        payload["in_reply_to_discussion_id"] = a.reply
        payload["resolve_discussion"] = bool(a.resolve)
        kind = f"reply on {a.reply}" + (" + resolve" if a.resolve else "")
    elif a.outside:
        payload["note"] = outside_body(a.outside, body)
        kind = f"outside the diff {a.outside}"
    elif a.path:
        if a.line is None:
            sys.exit("--path needs --line")
        start = a.line
        end = a.end_line if a.end_line is not None else a.line
        start, end = min(start, end), max(start, end)
        payload["position"] = build_position(a, start, end, body)
        kind = f"{a.path}:{start}" + (f"-{end}" if end != start else "")
    d = glab(f"{mr_base(a.project, a.iid)}/draft_notes", a.repo_dir, "POST", payload)
    if "id" not in d and payload.get("resolve_discussion"):
        # GitLab refuses resolve_discussion on some threads we can resolve
        # directly; draft without it and let submit resolve afterwards.
        payload["resolve_discussion"] = False
        d = glab(f"{mr_base(a.project, a.iid)}/draft_notes", a.repo_dir, "POST", payload)
        resolve_after_submit = True
        kind = f"reply on {a.reply} + resolve after submit"
    if "id" not in d:
        sys.exit(f"draft not created ({kind}): {d.get('message', d)}")
    if "position" in payload and not (d.get("position") or {}).get("new_line"):
        glab(f"{mr_base(a.project, a.iid)}/draft_notes/{d['id']}", a.repo_dir,
             "DELETE")
        sys.exit(f"draft for {kind} came back unanchored; deleted it")
    ledger = _ledger(a.ledger)
    entry = {"id": d["id"], "label": a.label, "where": kind}
    if a.resolve:
        entry["resolve"] = a.reply
        entry["resolve_after_submit"] = resolve_after_submit
    ledger.append(entry)
    _write_ledger(a.ledger, ledger)
    print(f"  draft={d['id']} {a.label} {kind} ({len(payload['note'])} chars)")


def cmd_submit(a) -> None:
    """Publish every pending draft as one review, then check what landed.

    bulk_publish answers 204 even when the state change did not stick, and a
    failure can arrive after some drafts already became threads, so the
    result is read back rather than trusted.
    """
    ledger_ids = {e["id"] for e in _ledger(a.ledger)}
    pending = _drafts(a)
    foreign = [d["id"] for d in pending if d["id"] not in ledger_ids]
    if foreign:
        sys.exit(
            f"refusing: {len(foreign)} pending draft(s) on !{a.iid} are not in "
            f"this run's ledger ({foreign}). Submitting would publish them too - "
            "the user has to submit or discard them first."
        )
    payload = {"reviewer_state": a.state}
    summary = None
    if a.file:
        summary = open(a.file, encoding="utf-8").read()
        payload["note"] = summary
    answer = glab(f"{mr_base(a.project, a.iid)}/draft_notes/bulk_publish",
                  a.repo_dir, "POST", payload)
    left = [d["id"] for d in _drafts(a) if d["id"] in ledger_ids]
    if answer:
        # Success is a 204 with no body; anything else is GitLab's error.
        sys.exit(f"bulk_publish answered: {answer}. {len(left)} of "
                 f"{len(ledger_ids)} drafts still pending: {left}. Run `threads` "
                 "before anything else, then `discard-drafts` what is left.")
    me = current_user(a.repo_dir)
    reviewers = glab(f"{mr_base(a.project, a.iid)}/reviewers", a.repo_dir)
    state = next((r.get("state") for r in reviewers
                  if r["user"]["username"] == me), None)
    print(f"  published {len(ledger_ids) - len(left)}/{len(ledger_ids)} drafts, "
          f"reviewer state={state} (asked {a.state})")
    if left:
        sys.exit(
            f"{len(left)} draft(s) still pending: {left}. Run `threads` before "
            "anything else - some may have published anyway - then "
            "`discard-drafts` the rest."
        )
    if summary and not _summary_posted(a, summary, me):
        print("  the summary note does not show on the MR - check it by hand "
              "before posting it again")
    _settle_resolves(a)
    # Emptied so a later run on the same ledger cannot re-apply these resolves.
    _write_ledger(a.ledger, [])


def _summary_posted(a, summary: str, me: str) -> bool:
    notes = glab(f"{mr_base(a.project, a.iid)}/notes?sort=desc&order_by=created_at"
                 "&per_page=20", a.repo_dir)
    return any(n.get("author", {}).get("username") == me
               and (n.get("body") or "").strip() == summary.strip() for n in notes)


def _settle_resolves(a) -> None:
    """Make every thread a draft asked to resolve read resolved after submit.

    bulk_publish skips the resolve where GitLab refused it on the draft, and
    a 204 is no proof it applied anywhere else either.
    """
    for entry in _ledger(a.ledger):
        did = entry.get("resolve")
        if not did:
            continue
        note = _first_human_note(_discussion(a, did)) or {}
        if note.get("resolved"):
            print(f"  {entry['label']}: discussion={did} resolved=True")
            continue
        a.discussion = did
        _set_resolved(a, True)


def cmd_discard_drafts(a) -> None:
    ours = {e["id"] for e in _ledger(a.ledger, required=True)}
    gone = 0
    for d in _drafts(a):
        if d["id"] in ours:
            glab(f"{mr_base(a.project, a.iid)}/draft_notes/{d['id']}", a.repo_dir,
                 "DELETE")
            gone += 1
    still = sorted(ours & {d["id"] for d in _drafts(a)})
    if still:
        sys.exit(f"drafts {still} survived the delete")
    _write_ledger(a.ledger, [])
    print(f"  deleted {gone} draft(s) of this run; none of ours left pending")


def cmd_approve(a) -> None:
    """Approve at the sha we reviewed, so a push during the run is refused."""
    d = glab(f"{mr_base(a.project, a.iid)}/approve", a.repo_dir, "POST",
             {"sha": a.sha})
    me = current_user(a.repo_dir)
    approvers = [u["user"]["username"] for u in d.get("approved_by", [])]
    if me not in approvers:
        sys.exit(
            f"!{a.iid} not approved by {me}: {d.get('message', d)}. "
            "A sha mismatch means the author pushed since the review - re-run "
            "`refs` and re-check before approving."
        )
    print(f"  !{a.iid} approved by {me} at {a.sha[:12]}")


def _linked_iids(description: str, sibling_path: str) -> list[str]:
    """MR iids in the sibling project that the description links or references."""
    path = re.escape(sibling_path)
    found = re.findall(rf"{path}/-/merge_requests/(\d+)", description)
    found += re.findall(rf"(?<![\w/.-]){path}!(\d+)", description)
    return list(dict.fromkeys(found))


def cmd_counterpart(a) -> None:
    """Find the sibling project's MR for the same change.

    The FE and BE halves of one change share a branch name, because that is
    what makes one review app build both. A link in the description is the
    fallback for pairs that broke that convention.
    """
    mr = glab(mr_base(a.project, a.iid), a.repo_dir)
    sibling_path = glab(f"projects/{a.sibling}", a.repo_dir)["path_with_namespace"]
    found: dict[str, str] = {}
    branch = mr["source_branch"]
    same = glab(f"projects/{a.sibling}/merge_requests?state=opened&per_page=100"
                f"&source_branch={quote(branch, safe='')}", a.repo_dir)
    for m in same:
        found[str(m["iid"])] = "same branch"
    for iid in _linked_iids(mr.get("description") or "", sibling_path):
        found.setdefault(iid, "linked in description")
    if not found:
        print(f"none: no open {sibling_path} MR on {branch}, none linked")
        return
    for iid, how in found.items():
        c = glab(mr_base(a.sibling, iid), a.repo_dir)
        refs = c["diff_refs"] or {}
        print(f"!{iid} ({how}) {c['state']}{' draft' if c['draft'] else ''}")
        print(f"  url       {c['web_url']}")
        print(f"  branch    {c['source_branch']} -> {c['target_branch']}")
        print(f"  base_sha  {refs.get('base_sha')}")
        print(f"  head_sha  {refs.get('head_sha')}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project", required=True, help="numeric project id or URL-encoded path")
    p.add_argument("--iid", required=True, help="MR iid (the !123 in the URL)")
    p.add_argument("--repo-dir", default=None, help="cwd for glab (a checkout of the repo)")
    sub = p.add_subparsers(dest="cmd", required=True)

    rf = sub.add_parser("refs")
    rf.add_argument("--description-out", default=None,
                    help="write the MR description to this file")
    rf.set_defaults(func=cmd_refs)

    cp = sub.add_parser("counterpart")
    cp.add_argument("--sibling", required=True, help="the other repo's project id")
    cp.set_defaults(func=cmd_counterpart)

    d = sub.add_parser("diff")
    d.add_argument("--out", required=True)
    d.set_defaults(func=cmd_diff)

    al = sub.add_parser("added-lines")
    al.add_argument("--file", default=None, help="only paths ending with this")
    al.set_defaults(func=cmd_added_lines)

    ls = sub.add_parser("list")
    ls.add_argument("--author", default=None)
    ls.set_defaults(func=cmd_list)

    po = sub.add_parser("post")
    po.add_argument("--file", required=True, help="markdown file with the comment body")
    po.add_argument("--path", required=True)
    po.add_argument("--line", required=True, type=int)
    po.set_defaults(func=cmd_post)

    ed = sub.add_parser("edit")
    ed.add_argument("--file", required=True)
    ed.add_argument("--discussion", required=True)
    ed.add_argument("--note", required=True)
    ed.set_defaults(func=cmd_edit)

    sub.add_parser("me").set_defaults(func=cmd_me)

    th = sub.add_parser("threads")
    th.add_argument("--out", default=None, help="write JSON here instead of stdout")
    th.add_argument("--mine", action="store_true", help="only threads we opened")
    th.set_defaults(func=cmd_threads)

    rp = sub.add_parser("reply")
    rp.add_argument("--file", required=True, help="markdown file with the reply body")
    rp.add_argument("--discussion", required=True)
    rp.set_defaults(func=cmd_reply)

    rs = sub.add_parser("resolve")
    rs.add_argument("--discussion", required=True)
    rs.set_defaults(func=cmd_resolve)

    ur = sub.add_parser("unresolve")
    ur.add_argument("--discussion", required=True)
    ur.set_defaults(func=cmd_unresolve)

    nt = sub.add_parser("note")
    nt.add_argument("--file", required=True, help="markdown file with the note body")
    nt.set_defaults(func=cmd_note)

    ap = sub.add_parser("approve")
    ap.add_argument("--sha", required=True, help="head_sha the review was done against")
    ap.set_defaults(func=cmd_approve)

    sub.add_parser("drafts").set_defaults(func=cmd_drafts)

    dr = sub.add_parser("draft")
    dr.add_argument("--file", required=True, help="markdown file with the body")
    dr.add_argument("--label", required=True, help="finding id, e.g. H1 or T2")
    dr.add_argument("--ledger", required=True, help="JSON file recording this run's drafts")
    where = dr.add_mutually_exclusive_group()
    where.add_argument("--path", help="inline: file path at head")
    where.add_argument("--outside", metavar="PATH:LINES",
                       help="general note for lines no hunk touched, e.g. a.ts:40-47")
    where.add_argument("--reply", metavar="DISCUSSION", help="reply on this thread")
    dr.add_argument("--line", type=int, help="inline: start line (or the only line)")
    dr.add_argument("--end-line", type=int, help="inline: end line of a range")
    dr.add_argument("--resolve", action="store_true",
                    help="with --reply: resolve the thread on submit (ours only)")
    dr.add_argument("--reopen", action="store_true",
                    help="with --reply on a resolved thread: let the publish reopen it "
                         "(ours only)")
    dr.set_defaults(func=cmd_draft)

    sb = sub.add_parser("submit")
    sb.add_argument("--ledger", required=True)
    sb.add_argument("--state", required=True, choices=["requested_changes", "reviewed"])
    sb.add_argument("--file", default=None, help="markdown file with the summary note")
    sb.set_defaults(func=cmd_submit)

    dd = sub.add_parser("discard-drafts")
    dd.add_argument("--ledger", required=True)
    dd.set_defaults(func=cmd_discard_drafts)

    a = p.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
