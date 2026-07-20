#!/usr/bin/env python3
"""
Prioritize training-log concepts for re-drilling based on spaced repetition.

Usage: python3 train_priority.py
       python3 train_priority.py --tutorials-dir /path/to/tutorials

Reads the single training ledger (training_log.md) and returns concepts
ordered by drill urgency (most urgent first). Shares the interval schedule
and priority formula with quiz_priority.py via sr_common.
"""

import argparse
from datetime import datetime
from pathlib import Path

from sr_common import calculate_priority, parse_date

# Column order of the training_log.md markdown table.
COLUMNS = [
    "concept", "source_repo", "created", "last_trained",
    "training_score", "commit", "file", "tutorial", "notes",
]


def get_tutorials_directory():
    """Get the tutorials directory (~/coding-tutor-tutorials/)."""
    return Path.home() / "coding-tutor-tutorials"


def parse_ledger(filepath):
    """Parse the markdown table in training_log.md into row dicts."""
    rows = []
    for line in filepath.read_text().splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        # Skip the header row and the |---|---| separator row.
        if not cells or cells[0].lower() == "concept":
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        rows.append(dict(zip(COLUMNS, cells)))
    return rows


def _clean(value):
    """Blank / em-dash placeholder -> None."""
    if not value or value == "—":
        return None
    return value


def _score(value):
    value = _clean(value)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Prioritize training-log concepts for re-drilling"
    )
    parser.add_argument(
        "--tutorials-dir",
        help="Path to tutorials directory (defaults to ~/coding-tutor-tutorials/)",
        default=None,
    )
    args = parser.parse_args()

    today = datetime.now().date()

    if args.tutorials_dir:
        tutorials_path = Path(args.tutorials_dir)
    else:
        tutorials_path = get_tutorials_directory()

    ledger = tutorials_path / "training_log.md"
    if not ledger.exists():
        print("No training log found at ~/coding-tutor-tutorials/training_log.md")
        return

    rows = parse_ledger(ledger)
    if not rows:
        print("No training entries yet")
        return

    for row in rows:
        row["priority"] = calculate_priority(
            _score(row.get("training_score")),
            _clean(row.get("last_trained")),
            _clean(row.get("created")),
            today,
        )

    # Sort by priority (highest first = most urgent).
    rows.sort(key=lambda r: r["priority"], reverse=True)

    print("=" * 60)
    print("TRAINING PRIORITY (most urgent first)")
    print("=" * 60)
    print()

    for i, row in enumerate(rows, 1):
        score = _score(row.get("training_score"))
        score_str = f"{score}/10" if score is not None else "never"

        last = _clean(row.get("last_trained"))
        if last:
            days_ago = (today - parse_date(last)).days
            last_str = f"{days_ago} days ago"
        else:
            last_str = "never"

        print(f"{i}. {row.get('concept', '')}")
        print(f"   training_score: {score_str}")
        print(f"   last_trained: {last_str}")
        print(f"   source_repo: {row.get('source_repo', '')}")
        print()


if __name__ == "__main__":
    main()
