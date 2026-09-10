# herdr-spin reference

Details for Step 15 (installing herdr-spin) that don't need to be in the main skill
flow: what the plugin actually does, how to troubleshoot it, and how to remove it.

## How it works

The plugin polls `agent.list` twice a second and writes `pane.report_metadata` for each
working pane on every animation frame. Panes that are not working are written once, when
their state changes, so idle rows do not trigger a sidebar redraw eight times a second.

Herdr documents `[[startup]]` as one-shot initialisation, not a supervised daemon, so
`spin.py` double-forks and returns immediately. It holds a lock at
`/tmp/herdr-spin-$UID/spin.lock`, because the startup hook runs again on live handoff and
a second animator would fight the first over the same tokens. Nothing restarts it if it
dies.

`--restart` stops the running animator through a `stop` flag file rather than a signal. A
hand-started run and the plugin hook can sit in different PID namespaces, where neither
can signal the other's pid, but both see the same file.

## Blank icon column

The animator owns the whole glyph column, so nothing running means no icons. Working rows
go blank within a second because their glyph carries a TTL; the rest keep their last
glyph. Start it again:

```bash
python3 ~/.config/herdr-spin/spin.py --restart
```

If `--restart` does nothing, check that something holds `/tmp/herdr-spin-$UID/spin.lock`.
A free lock with a blank column means the animator is not running at all.

## Frame rate

Defaults to 120ms. Every frame is a socket round trip per working agent, which is the
redraw cost herdr removed deliberately in 0.8.0 — raise it if the sidebar feels busy:

```bash
HERDR_SPIN_FRAME_MS=200 python3 ~/.config/herdr-spin/spin.py --restart
```

Colours and layout live in `config.toml`, so changing those needs only
`herdr server reload-config`, no restart.

Log: `/tmp/herdr-spin-$UID/spin.log`, or the plugin's state dir when herdr started it.

## Uninstall

```bash
python3 ~/.config/herdr-spin/spin.py --stop   # clears the glyphs, then exits
herdr plugin unlink local.spin
```

Then restore `rows` in `~/.config/herdr/config.toml` to herdr's default
(`rows = [["state_icon", "workspace", "tab"], ["agent"]]`) and run
`herdr server reload-config`.
