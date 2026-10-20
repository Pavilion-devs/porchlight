"""Learns the parent's usual routine from past door activity, and matches repeat visitors."""
import statistics
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from .store import Store

RESIDENT_ACTIVITIES = ["resident_leaving", "resident_returning", "resident_at_door"]


@dataclass
class RoutineStat:
    label: str
    key: str
    usual: time | None  # median local time
    latest: time | None  # latest local time seen in the learning window
    window_minutes: int
    days: int


def _minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def _from_minutes(m: float) -> time:
    m = int(round(m))
    return time(m // 60 % 24, m % 60)


def _stat(label: str, key: str, times: list[time], days: int) -> RoutineStat:
    if not times:
        return RoutineStat(label, key, None, None, 0, days)
    mins = [_minutes(t) for t in times]
    med = statistics.median(mins)
    spread = max(abs(m - med) for m in mins)
    return RoutineStat(label, key, _from_minutes(med), _from_minutes(max(mins)), max(15, int(spread)), len(times))


def first_out_today(store: Store, day: date, tz: ZoneInfo) -> datetime | None:
    start = datetime.combine(day, time(4, 0), tz)
    obs = store.observations(start, start + timedelta(hours=20), RESIDENT_ACTIVITIES)
    return obs[0].time.astimezone(tz) if obs else None


def afternoon_out(store: Store, day: date, tz: ZoneInfo) -> datetime | None:
    start = datetime.combine(day, time(11, 30), tz)
    obs = store.observations(start, start + timedelta(hours=5), ["resident_leaving"])
    return obs[0].time.astimezone(tz) if obs else None


def learn(store: Store, today: date, tz: ZoneInfo, days: int = 14) -> list[RoutineStat]:
    first, walk = [], []
    learned_days = 0
    for i in range(1, days + 1):
        d = today - timedelta(days=i)
        f = first_out_today(store, d, tz)
        if f:
            learned_days += 1
            first.append(f.timetz().replace(tzinfo=None))
        w = afternoon_out(store, d, tz)
        if w:
            walk.append(w.timetz().replace(tzinfo=None))
    return [
        _stat("First time outside", "first_out", first, learned_days),
        _stat("Afternoon walk", "walk", walk, learned_days),
    ]


# --- repeat visitors ------------------------------------------------------------------------------

def _traits(signature: str) -> set[str]:
    return {t.strip().lower() for t in signature.replace(";", ",").split(",") if t.strip()}


def similarity(a: str, b: str) -> float:
    ta, tb = _traits(a), _traits(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def visitor_history(store: Store, signature: str, now: datetime, tz: ZoneInfo,
                    days: int = 7, threshold: float = 0.5) -> list[datetime]:
    """Earlier visits (one per day, not counting today) by someone matching this signature."""
    obs = store.observations(now - timedelta(days=days), now, ["visitor_at_door"])
    today = now.astimezone(tz).date()
    seen: dict[date, datetime] = {}
    for o in obs:
        d = o.time.astimezone(tz).date()
        if d != today and o.visitor_signature and similarity(o.visitor_signature, signature) >= threshold:
            seen.setdefault(d, o.time)
    return sorted(seen.values())
