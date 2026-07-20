#!/usr/bin/env python3
"""
Prioritize tutorials for quizzing based on spaced repetition.

Usage: python3 quiz_priority.py
       python3 quiz_priority.py --tutorials-dir /path/to/tutorials

Returns tutorials ordered by quiz urgency (most urgent first).
"""

import argparse
import re
from datetime import datetime
from pathlib import Path

from sr_common import calculate_priority, parse_date


def get_tutorials_directory():
    """Get the tutorials directory (~/coding-tutor-tutorials/)."""
    return Path.home() / "coding-tutor-tutorials"


def parse_frontmatter(filepath):
    """Extract YAML frontmatter from tutorial."""
    content = filepath.read_text()

    # Match YAML frontmatter between --- delimiters
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if not match:
        return None

    frontmatter_text = match.group(1)
    metadata = {'filepath': str(filepath)}

    # Parse simple YAML key: value pairs
    for line in frontmatter_text.split('\n'):
        line = line.strip()
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()

            # Handle null values
            if value == 'null':
                value = None
            # Convert understanding_score to int
            elif key == 'understanding_score' and value:
                try:
                    value = int(value)
                except ValueError:
                    pass
            # Handle list values for concepts
            elif key == 'concepts' and value.startswith('['):
                value = value.strip('[]').strip()
                if value:
                    value = [item.strip() for item in value.split(',')]
                else:
                    value = []

            metadata[key] = value

    return metadata


def tutorial_priority(tutorial, today):
    """Quiz priority for a tutorial. Maps its frontmatter onto the shared
    spaced-repetition formula in sr_common."""
    return calculate_priority(
        tutorial.get('understanding_score'),
        tutorial.get('last_quizzed'),
        tutorial.get('created'),
        today,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Prioritize tutorials for quizzing based on spaced repetition"
    )
    parser.add_argument(
        "--tutorials-dir",
        help="Path to tutorials directory (defaults to ~/coding-tutor-tutorials/)",
        default=None
    )

    args = parser.parse_args()

    today = datetime.now().date()
    tutorials = []

    if args.tutorials_dir:
        tutorials_path = Path(args.tutorials_dir)
    else:
        tutorials_path = get_tutorials_directory()

    if not tutorials_path.exists():
        print("No tutorials found in ~/coding-tutor-tutorials/")
        return

    for filepath in tutorials_path.glob("*.md"):
        if filepath.name in ("learner_profile.md", "training_log.md"):
            continue
        metadata = parse_frontmatter(filepath)
        if metadata:
            metadata['priority'] = tutorial_priority(metadata, today)
            tutorials.append(metadata)

    if not tutorials:
        print("No tutorials found")
        return

    # Sort by priority (highest first = most urgent)
    tutorials.sort(key=lambda t: t['priority'], reverse=True)

    print("=" * 60)
    print("QUIZ PRIORITY (most urgent first)")
    print("=" * 60)
    print()

    for i, t in enumerate(tutorials, 1):
        score = t.get('understanding_score') or 0
        last_q = t.get('last_quizzed')
        concepts = t.get('concepts', [])
        if isinstance(concepts, list):
            concepts_str = ', '.join(concepts[:2])  # First 2 concepts
        else:
            concepts_str = str(concepts)

        # Calculate days ago
        if last_q:
            last_q = parse_date(last_q)
            days_ago = (today - last_q).days
            last_quizzed_str = f"{days_ago} days ago"
        else:
            last_quizzed_str = "never"

        print(f"{i}. {concepts_str}")
        print(f"   understanding_score: {score}/10")
        print(f"   last_quizzed: {last_quizzed_str}")
        print(f"   file: {t['filepath']}")
        print()


if __name__ == "__main__":
    main()
