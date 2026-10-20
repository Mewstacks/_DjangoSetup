"""Business-day arithmetic for regulatory deadlines.

Brazilian deadlines such as the ANPD incident notice are counted in business days
(Resolution CD/ANPD 15/2024 uses 3 - confirm the current rule with counsel; the number is a
setting). Saturdays and Sundays never count; national and local holidays are listed by the
operator in ``PRIVACY_HOLIDAYS`` (ISO dates), because the correct list depends on the
controller's city and changes every year - guessing would silently produce wrong dates.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from django.conf import settings


def _holidays() -> set[date]:
    return {date.fromisoformat(value) for value in settings.PRIVACY_HOLIDAYS}


def is_business_day(day: date) -> bool:
    return day.weekday() < 5 and day not in _holidays()


def add_business_days(start: datetime, days: int) -> datetime:
    """``start`` moved forward by ``days`` business days, keeping the time of day.

    Day zero is the start day itself; the deadline falls on the ``days``-th business day after
    it. Starting on a weekend counts from the next business day.
    """
    current = start
    remaining = days
    while remaining > 0:
        current += timedelta(days=1)
        if is_business_day(current.date()):
            remaining -= 1
    return current


def business_days_between(start: datetime, end: datetime) -> int:
    """Whole business days from ``start`` until ``end`` (negative once ``end`` has passed)."""
    sign = 1
    if end < start:
        start, end, sign = end, start, -1
    count = 0
    day = start.date()
    while day < end.date():
        day += timedelta(days=1)
        if is_business_day(day):
            count += 1
    return sign * count
