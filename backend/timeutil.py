"""timeutil.py — timezone-aware month boundaries (sargable range filters, not to_char())."""
from __future__ import annotations

from datetime import datetime, timezone

from backend.settings import get_settings


def month_key(dt: datetime) -> str:
    """'YYYY-MM' of `dt` in the application timezone."""
    return dt.astimezone(get_settings().tz).strftime("%Y-%m")


def month_bounds(month: str) -> tuple[datetime, datetime]:
    """[start, end) of 'YYYY-MM' in the application timezone, as UTC datetimes."""
    tz = get_settings().tz
    year, mon = int(month[:4]), int(month[5:7])
    start = datetime(year, mon, 1, tzinfo=tz)
    end = datetime(year + (mon == 12), mon % 12 + 1, 1, tzinfo=tz)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)
