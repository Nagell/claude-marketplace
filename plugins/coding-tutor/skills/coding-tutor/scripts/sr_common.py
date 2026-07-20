#!/usr/bin/env python3
"""
Shared spaced-repetition scoring for coding-tutor.

Both quiz_priority.py (reads tutorial frontmatter) and train_priority.py
(reads training_log.md) import this module, so the interval schedule and the
priority formula live in exactly one place. Change them here, not in a copy.
"""

from datetime import datetime

# Ideal days between assessments based on score (0-10).
# Lower score = more frequent review. Fibonacci-ish progression.
INTERVALS = {
    0: 1,    # Never assessed - urgent
    1: 2,
    2: 3,
    3: 5,
    4: 8,
    5: 13,
    6: 21,
    7: 34,
    8: 55,
    9: 89,
    10: 144,
}


def parse_date(date_value):
    """Parse a DD-MM-YYYY string into a date; pass date objects through."""
    if isinstance(date_value, str):
        return datetime.strptime(date_value, "%d-%m-%Y").date()
    return date_value


def calculate_priority(score, last_assessed, created, today):
    """
    Spaced-repetition priority. Higher = more urgent.

    Args:
        score: 0-10 (or None -> treated as 0). Picks the ideal interval.
        last_assessed: date / DD-MM-YYYY string / None. None = never assessed.
        created: date / DD-MM-YYYY string / None. Age basis for never-assessed.
        today: date.

    Logic:
    1. Never assessed -> use created age + a bonus so it surfaces early.
    2. Assessed -> days overdue relative to the score's interval.
    3. No date info at all -> max urgency (100).
    """
    score = score or 0
    ideal_interval = INTERVALS.get(score, INTERVALS[5])

    if not last_assessed:
        # Never assessed - need a baseline.
        if created:
            created = parse_date(created)
            days_since_created = (today - created).days
            # Bonus ensures never-assessed items surface early.
            return days_since_created / ideal_interval + 10
        # No date info at all - max urgency.
        return 100

    last_assessed = parse_date(last_assessed)
    days_since = (today - last_assessed).days
    days_overdue = days_since - ideal_interval
    return days_overdue / ideal_interval
