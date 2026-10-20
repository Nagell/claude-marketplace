#!/usr/bin/env python3
"""Install unsecretised/sketchybar-config into ~/.config/sketchybar, adapted for FlashSpace.

The upstream config has no license, so this repo ships only the changes, applied to a
checkout of the pinned commit on the user's machine:

- workspace buttons 1-9 driven by FlashSpace instead of bobrwm
- a RAM item showing macOS memory pressure
- bar offset and side padding from --gap, so the bar lines up with Rectangle's gaps

Every edit checks its anchor in the upstream text first and stops if it is missing.
Python 3 standard library only.

Usage:
    patch.py --source DIR [--target DIR] [--gap PX] [--always-shown N]
"""

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

UPSTREAM_COMMIT = "07cf294"
COPIED_PLUGINS = ["battery.sh", "clock.sh", "front_app.sh", "music.sh", "volume.sh"]
BAR_HEIGHT = 36
GROUP_HEIGHT = 30  # height of the rounded left/right groups inside the bar

WORKSPACES_TAIL = r'''
# FlashSpace passes the new workspace with its change event; timer runs have to ask.
FOCUSED="${WORKSPACE:-$(flashspace get-workspace 2>/dev/null)}"

for sid in 1 2 3 4 5 6 7 8 9; do
  # Lines are "App Name,bundle.id"; only running apps get an icon.
  bundle_ids="$(flashspace list-apps "$sid" --only-running --with-bundle-id 2>/dev/null | cut -d, -f2 | sort -u)"

  icons=""
  while IFS= read -r bid; do
    [ -z "$bid" ] && continue
    [ -n "$icons" ] && icons+=" "
    icons+="$(app_icon "$bid")"
  done <<< "$bundle_ids"

  # 1..ALWAYS_SHOWN always show; the rest only while they hold running apps or are focused.
  drawing=on
  if [ "$sid" -gt ALWAYS_SHOWN ] && [ -z "$icons" ] && [ "$sid" != "$FOCUSED" ]; then
    drawing=off
  fi

  if [ "$sid" = "$FOCUSED" ]; then
    sketchybar --set "workspace.$sid" \
      drawing="$drawing" \
      icon.highlight=on \
      label="$icons" \
      label.drawing=on \
      icon.padding_right=0 \
      background.color=0x30${FG_DIM:2} \
      background.border_width=1 \
      background.border_color=0x60${FG_DIM:2}
  else
    sketchybar --set "workspace.$sid" \
      drawing="$drawing" \
      icon.highlight=off \
      label="$icons" \
      label.drawing=on \
      icon.padding_right=2 \
      background.color=0x00000000 \
      background.border_width=0
  fi
done
'''

RAM_SCRIPT = '''#!/bin/sh

# Memory pressure, not "Memory Used": macOS keeps RAM full and compressed pages count as
# used, so that figure sits near 80% even when nothing is short. Pressure shows real demand.
FREE="$(memory_pressure | awk -F': ' '/free percentage/ { sub(/%/, "", $2); print $2 }')"

sketchybar --set "$NAME" label="$((100 - FREE))%"
'''

RAM_ITEM = (
    "sketchybar --add item ram right \\\n"
    "           --set ram \\\n"
    "               icon=\U000F035B \\\n"
    "               icon.font.size=14.0 \\\n"
    "               icon.color=0x99${FG_DIM:2} \\\n"
    "               label.color=0xff${FG_SECONDARY:2} \\\n"
    "               label.font=\"JetBrainsMono Nerd Font:Medium:12.0\" \\\n"
    "               label.padding_right=2 \\\n"
    "               update_freq=5 \\\n"
    "               script=\"$PLUGIN_DIR/ram.sh\"\n\n"
)

UPSTREAM_UPDATER = """##############################
#  Workspace Updater (bobrwm)#
##############################

sketchybar --add item workspaces_updater left \\
           --set workspaces_updater \\
               script="$PLUGIN_DIR/workspaces.sh" \\
               update_freq=2 \\
               drawing=off"""

FLASHSPACE_UPDATER = """##############################
#  Workspace Updater         #
##############################

# FlashSpace fires flashspace_workspace_change on a switch; apps opening or closing
# have no event, so the timer catches those.
sketchybar --add event flashspace_workspace_change
sketchybar --add item workspaces_updater left \\
           --set workspaces_updater \\
               script="$PLUGIN_DIR/workspaces.sh" \\
               update_freq=2 \\
               drawing=off \\
           --subscribe workspaces_updater flashspace_workspace_change front_app_switched"""


def replace_once(text, old, new, what):
    if text.count(old) != 1:
        sys.exit(f"Upstream changed: expected one {what} ({old!r}) in sketchybarrc. "
                 f"Check out commit {UPSTREAM_COMMIT}.")
    return text.replace(old, new)


def bar_offset(gap):
    """y_offset that puts the top of the rounded groups `gap` px below the screen edge."""
    return gap - (BAR_HEIGHT - GROUP_HEIGHT) // 2


def patch_rc(text, gap):
    text = replace_once(text, "for sid in {1..5}; do", "for sid in {1..9}; do", "workspace loop")
    text = replace_once(text, 'click_script="bobrwm focus-workspace $sid"',
                        'click_script="flashspace workspace --name $sid"', "workspace click")
    text = replace_once(text, UPSTREAM_UPDATER, FLASHSPACE_UPDATER, "bobrwm updater")
    text = replace_once(text, 'echo "sketchybar: bobrwm config loaded"\n', "", "load message")
    text = replace_once(text, "y_offset=0 \\", f"y_offset={bar_offset(gap)} \\", "bar y_offset")
    text = replace_once(text, "padding_left=12 \\\n                padding_right=12 \\",
                        f"padding_left={gap} \\\n                padding_right={gap} \\",
                        "bar padding")

    # RAM sits between battery and volume, with its own separator copied from sep.right2.
    start = text.index("sketchybar --add item sep.right2 right")
    end = text.index("sketchybar --add item volume right")
    separator = text[start:end].replace("sep.right2", "sep.right3")
    text = text[:start] + separator + RAM_ITEM + text[start:]
    return replace_once(text, "'/battery/' '/volume/'", "'/battery/' '/ram/' '/volume/'",
                        "right bracket members")


def workspaces_script(upstream, always_shown):
    """Keep upstream's app_icon() and replace its bobrwm loop with a FlashSpace one."""
    marker = "\nDATA="
    if marker not in upstream:
        sys.exit("Upstream changed: no bobrwm query in workspaces.sh. "
                 f"Check out commit {UPSTREAM_COMMIT}.")
    head = upstream[:upstream.index(marker)].rstrip() + "\n"
    return head + WORKSPACES_TAIL.replace("ALWAYS_SHOWN", str(always_shown))


def write_executable(path, text):
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, required=True,
                        help=f"checkout of unsecretised/sketchybar-config at {UPSTREAM_COMMIT}")
    parser.add_argument("--target", type=Path, default=Path.home() / ".config/sketchybar")
    parser.add_argument("--gap", type=int, default=10,
                        help="space between bar, screen edges and windows, in px (default: 10)")
    parser.add_argument("--always-shown", type=int, default=3,
                        help="workspaces 1..N always show in the bar (default: 3)")
    args = parser.parse_args()

    rc = (args.source / "sketchybarrc").read_text(encoding="utf-8")
    workspaces = (args.source / "plugins/workspaces.sh").read_text(encoding="utf-8")
    patched_rc = patch_rc(rc, args.gap)
    patched_workspaces = workspaces_script(workspaces, args.always_shown)

    if args.target.exists():
        backup = args.target.with_name(f"{args.target.name}.bak-{datetime.now():%Y%m%d-%H%M%S}")
        shutil.move(args.target, backup)
        print(f"Backup: {backup}", file=sys.stderr)

    plugins = args.target / "plugins"
    plugins.mkdir(parents=True)
    write_executable(args.target / "sketchybarrc", patched_rc)
    for name in COPIED_PLUGINS:
        shutil.copy2(args.source / "plugins" / name, plugins / name)
        (plugins / name).chmod(0o755)
    write_executable(plugins / "workspaces.sh", patched_workspaces)
    write_executable(plugins / "ram.sh", RAM_SCRIPT)
    print(f"Wrote: {args.target}", file=sys.stderr)


if __name__ == "__main__":
    main()
