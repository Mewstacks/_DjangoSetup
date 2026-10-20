"""Deadline arithmetic that a Temporal workflow can call: pure, no Django, no clock."""

from __future__ import annotations

from datetime import datetime, timedelta

REMINDER_OFFSETS = (timedelta(days=-5), timedelta(days=-1), timedelta(0))
OVERDUE_EVERY = timedelta(days=1)


def next_reminder(now: datetime, due: datetime) -> datetime:
    """The next moment worth waking up for, given the deadline.

    D-5, D-1 and the deadline itself, then once a day for as long as the request stays open.
    """
    for offset in REMINDER_OFFSETS:
        moment = due + offset
        if moment > now:
            return moment
    overdue = (now - due) // OVERDUE_EVERY + 1
    return due + overdue * OVERDUE_EVERY
