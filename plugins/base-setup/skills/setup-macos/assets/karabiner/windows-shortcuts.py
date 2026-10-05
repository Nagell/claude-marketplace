#!/usr/bin/env python3
"""Merge Windows-style shortcut rules into Karabiner-Elements' karabiner.json.

Rules go into the selected profile; a rule with the same description is replaced, never
duplicated. The file is backed up before it is written. Python 3 standard library only.

Usage:
    windows-shortcuts.py [--config PATH] [--work-dir DIR] [--device VID:PID ...] [--dry-run]
    windows-shortcuts.py --list-devices
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# Apps that keep their own Ctrl shortcuts: terminals need Ctrl+C etc., VS Code has its own.
EXCLUDED_APPS = [
    "com.mitchellh.ghostty",
    "com.apple.Terminal",
    "com.microsoft.VSCode",
]

# Browsers that get the Windows tab and developer-tools shortcuts.
BROWSERS = [
    "com.google.Chrome",
    "com.google.chrome.for.testing",
    "org.mozilla.firefox",
    "com.apple.Safari",
]

# Karabiner matches physical key positions in US terms, so on QWERTZ layouts the Z and Y
# rules swap. Add every enabled QWERTZ layout (Swiss German, Austrian, Czech, ...) here.
QWERTZ_LAYOUTS = [
    "com.apple.keylayout.German",
]

# Cmd+Q types "@" (Windows' AltGr+Q on German keyboards) instead of quitting the app. The key
# that types "@" depends on the layout; every other layout gets Shift+2 (U.S., Polish Pro).
AT_SIGN_KEYS = {
    "com.apple.keylayout.German": ("l", ["option"]),
}

DEFAULT_CONFIG = Path.home() / ".config/karabiner/karabiner.json"
KARABINER_CLI = "/Library/Application Support/org.pqrs/Karabiner-Elements/bin/karabiner_cli"
OPEN_DIR_PREFIX = "Windows: Option+E opens Finder in "
EXCEPT = "(not in terminals, VS Code)"


def anchored(values):
    return ["^" + re.escape(v) + "$" for v in values]


def not_in_excluded_apps():
    return {"type": "frontmost_application_unless", "bundle_identifiers": anchored(EXCLUDED_APPS)}


def in_browsers():
    return {"type": "frontmost_application_if", "bundle_identifiers": anchored(BROWSERS)}


def layout(condition_type):
    sources = [{"input_source_id": s} for s in anchored(QWERTZ_LAYOUTS)]
    return {"type": condition_type, "input_sources": sources}


def remap(from_key, from_mods, to_key, to_mods, *extra_conditions):
    return {
        "type": "basic",
        "from": {"key_code": from_key, "modifiers": {"mandatory": from_mods}},
        "to": [{"key_code": to_key, "modifiers": to_mods}],
        "conditions": [not_in_excluded_apps(), *extra_conditions],
    }


def build_rules(work_dir):
    """Return the rules this script owns, in the order they are added."""
    qwertz, qwerty = layout("input_source_if"), layout("input_source_unless")
    ctrl, ctrl_shift = ["control"], ["control", "shift"]
    open_dir = {
        "type": "basic",
        "from": {"key_code": "e", "modifiers": {"mandatory": ["option"]}},
        "to": [{"shell_command": f'open "$HOME/{work_dir}"'}],
    }
    close_window = {
        "type": "basic",
        "from": {"key_code": "f4", "modifiers": {"mandatory": ["option"]}},
        "to": [{"key_code": "w", "modifiers": ["command"]}],
        "conditions": [],
    }
    return [
        {"description": "Windows: Option+F4 closes the window (Cmd+W)",
         "manipulators": [close_window]},
        {"description": f"{OPEN_DIR_PREFIX}~/{work_dir}", "manipulators": [open_dir]},
        {"description": f"Windows: Ctrl(+Shift)+Left/Right jump/select by word {EXCEPT}",
         "manipulators": [
             remap("left_arrow", ctrl, "left_arrow", ["option"]),
             remap("right_arrow", ctrl, "right_arrow", ["option"]),
             remap("left_arrow", ctrl_shift, "left_arrow", ["option", "shift"]),
             remap("right_arrow", ctrl_shift, "right_arrow", ["option", "shift"]),
         ]},
        {"description": f"Windows: Ctrl+Backspace/Delete delete a word {EXCEPT}",
         "manipulators": [
             remap("delete_or_backspace", ctrl, "delete_or_backspace", ["option"]),
             remap("delete_forward", ctrl, "delete_forward", ["option"]),
         ]},
        {"description": f"Windows: Ctrl+A selects all {EXCEPT}",
         "manipulators": [remap("a", ctrl, "a", ["command"])]},
        {"description": f"Windows: Ctrl+Z/Y/X/C/V undo, redo, cut, copy, paste {EXCEPT}",
         "manipulators": [
             # QWERTZ: the key labelled Z sits where US has Y, and vice versa.
             remap("y", ctrl, "y", ["command"], qwertz),
             remap("z", ctrl, "y", ["command", "shift"], qwertz),
             remap("z", ctrl, "z", ["command"], qwerty),
             remap("y", ctrl, "z", ["command", "shift"], qwerty),
             remap("x", ctrl, "x", ["command"]),
             remap("c", ctrl, "c", ["command"]),
             remap("v", ctrl, "v", ["command"]),
         ]},
        {"description": f"Windows: Ctrl(+Shift)+R reload / hard reload {EXCEPT}",
         "manipulators": [
             remap("r", ctrl, "r", ["command"]),
             remap("r", ctrl_shift, "r", ["command", "shift"]),
         ]},
        {"description": f"Windows: Ctrl+B/I/U bold, italic, underline {EXCEPT}",
         "manipulators": [
             remap("b", ctrl, "b", ["command"]),
             remap("i", ctrl, "i", ["command"]),
             remap("u", ctrl, "u", ["command"]),
         ]},
        {"description": "Windows: Ctrl+T new tab, Ctrl+Shift+T reopen closed tab (browsers)",
         "manipulators": [
             remap("t", ctrl, "t", ["command"], in_browsers()),
             remap("t", ctrl_shift, "t", ["command", "shift"], in_browsers()),
         ]},
        {"description": "Windows: Ctrl+Shift+I opens developer tools (browsers)",
         "manipulators": [remap("i", ctrl_shift, "i", ["command", "option"], in_browsers())]},
        {"description": "Windows: Cmd+Q types @ instead of quitting (all apps)",
         "manipulators": at_sign_manipulators()},
    ]


def at_sign_manipulators():
    """Cmd+Q -> the layout's "@" key: one manipulator per listed layout, Shift+2 otherwise."""
    def cmd_q(to_key, to_mods, condition):
        return {
            "type": "basic",
            "from": {"key_code": "q", "modifiers": {"mandatory": ["command"]}},
            "to": [{"key_code": to_key, "modifiers": to_mods}],
            "conditions": [condition],
        }

    def sources(ids):
        return [{"input_source_id": s} for s in anchored(ids)]

    per_layout = [cmd_q(key, mods, {"type": "input_source_if", "input_sources": sources([layout_id])})
                  for layout_id, (key, mods) in AT_SIGN_KEYS.items()]
    fallback = cmd_q("2", ["shift"], {"type": "input_source_unless",
                                      "input_sources": sources(AT_SIGN_KEYS)})
    return [*per_layout, fallback]


def is_owned(description, owned):
    return description in owned or description.startswith(OPEN_DIR_PREFIX)


def selected_profile(config):
    profiles = config.setdefault("profiles", [])
    if not profiles:
        profiles.append({"name": "Default profile", "selected": True})
    return next((p for p in profiles if p.get("selected")), profiles[0])


def merge_rules(profile, rules):
    complex_mods = profile.setdefault("complex_modifications", {})
    owned = {r["description"] for r in rules}
    existing = complex_mods.get("rules", [])
    kept = [r for r in existing if not is_owned(r.get("description", ""), owned)]
    complex_mods["rules"] = kept + rules


def device_entry(vendor_id, product_id):
    return {
        "identifiers": {
            "is_keyboard": True,
            "is_pointing_device": True,
            "product_id": product_id,
            "vendor_id": vendor_id,
        },
        "ignore": False,
    }


def merge_devices(profile, devices):
    entries = profile.setdefault("devices", [])
    for vendor_id, product_id in devices:
        new = device_entry(vendor_id, product_id)
        entries[:] = [e for e in entries if e.get("identifiers") != new["identifiers"]]
        entries.append(new)


def parse_device(value):
    match = re.fullmatch(r"(\d+):(\d+)", value)
    if not match:
        raise argparse.ArgumentTypeError(f"expected VENDOR_ID:PRODUCT_ID (decimal), got {value!r}")
    return int(match[1]), int(match[2])


def parse_work_dir(value):
    if not value or value.startswith("/") or re.search(r'["\\$`]', value):
        raise argparse.ArgumentTypeError(
            f"expected a folder relative to $HOME without quotes, $ or backslashes, got {value!r}")
    return value.rstrip("/")


def list_devices():
    """Print keyboards that also report as pointing devices; Karabiner skips those by default."""
    try:
        out = subprocess.run([KARABINER_CLI, "--list-connected-devices"],
                             check=True, capture_output=True, text=True).stdout
    except (OSError, subprocess.CalledProcessError) as err:
        sys.exit(f"Could not run karabiner_cli ({err}). Is Karabiner-Elements installed?")
    for dev in json.loads(out):
        ids = dev.get("device_identifiers", {})
        if ids.get("is_virtual_device"):
            continue
        if ids.get("is_keyboard") and ids.get("is_pointing_device"):
            device_id = f'{ids.get("vendor_id")}:{ids.get("product_id")}'
            name = f'{dev.get("manufacturer", "?")} {dev.get("product", "?")}'
            print(f'{device_id}\t{name}\t{dev.get("transport", "")}')


def load(path):
    if not path.exists():
        return {"profiles": [{"name": "Default profile", "selected": True}]}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save(path, config):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup = path.with_name(f"{path.name}.bak-{datetime.now():%Y%m%d-%H%M%S}")
        shutil.copy2(path, backup)
        print(f"Backup: {backup}", file=sys.stderr)
    # Write a sibling temp file and rename it, so Karabiner never reloads a half-written file.
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".karabiner-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)
    print(f"Wrote: {path}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG,
                        help=f"karabiner.json to update (default: {DEFAULT_CONFIG})")
    parser.add_argument("--work-dir", type=parse_work_dir, default="Development",
                        help="folder under $HOME that Option+E opens (default: Development)")
    parser.add_argument("--device", type=parse_device, action="append", default=[],
                        metavar="VID:PID", help="also modify this keyboard+pointing device")
    parser.add_argument("--dry-run", action="store_true", help="print the result, write nothing")
    parser.add_argument("--list-devices", action="store_true",
                        help="list connected keyboards that also report as pointing devices")
    args = parser.parse_args()

    if args.list_devices:
        list_devices()
        return

    config = load(args.config)
    profile = selected_profile(config)
    merge_rules(profile, build_rules(args.work_dir))
    merge_devices(profile, args.device)

    if args.dry_run:
        json.dump(config, sys.stdout, indent=4, ensure_ascii=False)
        print()
    else:
        save(args.config, config)


if __name__ == "__main__":
    main()
