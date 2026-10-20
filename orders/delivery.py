"""When an order is promised, counted in business hours (Asia/Kolkata by default)."""

import datetime

from django.utils import timezone


def _at(day, time):
    return timezone.make_aware(datetime.datetime.combine(day, time))


def _next_working_open(day, open_time, working_days):
    """Opening time on the first working day strictly after `day`."""
    for offset in range(1, 8):
        candidate = day + datetime.timedelta(days=offset)
        if candidate.weekday() in working_days:
            return _at(candidate, open_time)
    raise ValueError("working_days is empty")


def _add_business_hours(start, hours, open_time, close_time, working_days):
    """`start` is an opening time; spill over into following days for long windows."""
    remaining = datetime.timedelta(hours=hours)
    cursor = start
    while True:
        available = _at(cursor.date(), close_time) - cursor
        if remaining <= available:
            return cursor + remaining
        remaining -= available
        cursor = _next_working_open(cursor.date(), open_time, working_days)


def delivery_deadline(paid_at, hours, open_time, close_time, working_days):
    """The time delivery is promised by.

    Paid inside business hours, and paid time + window still ends before closing:
    paid time + window. Otherwise: the next opening time + window (next working day,
    or later today if paid before opening on a working day).
    """
    local = timezone.localtime(paid_at)
    today = local.date()
    window = datetime.timedelta(hours=hours)

    if today.weekday() in working_days:
        opens, closes = _at(today, open_time), _at(today, close_time)
        if local < opens:
            return _add_business_hours(opens, hours, open_time, close_time, working_days)
        if local < closes and local + window <= closes:
            return local + window

    start = _next_working_open(today, open_time, working_days)
    return _add_business_hours(start, hours, open_time, close_time, working_days)


def describe_deadline(deadline, now=None):
    """'by 4:30 pm today', 'by 12:00 pm tomorrow' or 'by 12:00 pm on Mon 21 Oct'."""
    if deadline is None:
        return ""
    local = timezone.localtime(deadline)
    today = timezone.localtime(now or timezone.now()).date()
    clock = local.strftime("%I:%M %p").lstrip("0").lower()
    if local.date() == today:
        day = "today"
    elif local.date() == today + datetime.timedelta(days=1):
        day = "tomorrow"
    else:
        day = f"on {local.strftime('%a')} {local.day} {local.strftime('%b')}"
    return f"by {clock} {day}"
