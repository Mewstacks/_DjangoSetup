"""A small five-field cron matcher: enough for the schedules jobs declare, no extra dependency.

Fields: minute hour day-of-month month day-of-week (0 or 7 = Sunday). Each field takes ``*``,
``*/n``, ``a``, ``a-b``, ``a-b/n`` and comma lists. When both day fields are restricted, a time
matches if either does (the classic cron rule).
"""

from __future__ import annotations

from datetime import datetime

RANGES = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 7))


def _expand(field: str, low: int, high: int) -> set[int]:
    values: set[int] = set()
    for part in field.split(","):
        step = 1
        if "/" in part:
            part, _, raw_step = part.partition("/")
            step = int(raw_step)
            if step < 1:
                raise ValueError(f"bad step in {field!r}")
        if part in ("*", ""):
            start, stop = low, high
        elif "-" in part:
            raw_start, _, raw_stop = part.partition("-")
            start, stop = int(raw_start), int(raw_stop)
        else:
            start = int(part)
            stop = high if step > 1 else start
        if start < low or stop > high or start > stop:
            raise ValueError(f"{field!r} is outside {low}-{high}")
        values.update(range(start, stop + 1, step))
    return values


def parse(expression: str) -> tuple[set[int], set[int], set[int], set[int], set[int], bool, bool]:
    fields = expression.split()
    if len(fields) != 5:
        raise ValueError(f"expected 5 fields, got {expression!r}")
    parsed = [_expand(f, *r) for f, r in zip(fields, RANGES, strict=True)]
    parsed[4] = {d % 7 for d in parsed[4]}
    minute, hour, dom, month, dow = parsed
    return minute, hour, dom, month, dow, fields[2] != "*", fields[4] != "*"


def matches(expression: str, moment: datetime) -> bool:
    minute, hour, dom, month, dow, dom_set, dow_set = parse(expression)
    if moment.minute not in minute or moment.hour not in hour or moment.month not in month:
        return False
    day_ok = moment.day in dom
    weekday_ok = (moment.isoweekday() % 7) in dow
    if dom_set and dow_set:
        return day_ok or weekday_ok
    return day_ok and weekday_ok
