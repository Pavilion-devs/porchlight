from dataclasses import replace
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from porchlight import webhooks
from porchlight.brain import Brain
from porchlight.config import settings
from porchlight.hub import Hub
from porchlight.replayer import SCENARIOS, Replayer, seed_history
from porchlight.store import Store
from porchlight.vision import Observation

TZ = ZoneInfo("America/Los_Angeles")
DAY = date(2026, 10, 20)
KEY = "test-hmac-key"


class FakeNotifier:
    channel = "test"

    def __init__(self):
        self.sent = []

    async def send(self, text, photo=None):
        self.sent.append(text)
        return True


def at(hh, mm, day=DAY):
    return datetime.combine(day, time(hh, mm), TZ)


@pytest.fixture
def brain(tmp_path):
    s = replace(settings, timezone="America/Los_Angeles", package_alert_minutes=180, data_dir=tmp_path,
                hmac_key=KEY)
    return Brain(Store(":memory:"), Hub(), FakeNotifier(), s, agent=None)


def types(brain):
    return [e["type"] for e in brain.store.events()]


async def test_package_unattended_then_resolved(brain):
    await brain.on_observation(Observation(at(10, 6), "Box on the step", package=True, activity="delivery"))
    await brain.tick(at(12, 0))
    assert "package_unattended" not in types(brain)
    await brain.tick(at(13, 10))
    assert types(brain).count("package_unattended") == 1
    assert len(brain.notifier.sent) == 1
    await brain.tick(at(13, 30))  # no duplicate alert
    assert types(brain).count("package_unattended") == 1
    await brain.on_observation(Observation(at(15, 5), "Resident takes the box", is_resident_likely=True,
                                           person=True, activity="resident_at_door"))
    resolved = [e for e in brain.store.events() if e["type"] == "resolved"]
    assert resolved and resolved[0]["related_id"] == next(
        e["id"] for e in brain.store.events() if e["type"] == "package_unattended")


async def test_one_missed_frame_does_not_clear_package(brain):
    await brain.on_observation(Observation(at(10, 6), "Box", package=True, activity="delivery"))
    await brain.on_observation(Observation(at(10, 7), "Glare, box not visible"))
    await brain.tick(at(13, 10))
    assert "package_unattended" in types(brain)


async def test_package_taken_by_stranger(brain):
    await brain.on_observation(Observation(at(10, 6), "Box", package=True, activity="delivery"))
    await brain.on_observation(Observation(at(10, 40), "A man picks up the box and walks away", person=True,
                                           activity="package_pickup", person_desc="man in black jacket"))
    taken = [e for e in brain.store.events() if e["type"] == "package_taken"]
    assert taken and taken[0]["severity"] == "urgent"


async def test_routine_missed_after_latest_usual_time(brain):
    seed_history(brain.store, DAY, TZ)  # replay history
    await brain.tick(at(8, 15), "replay")
    assert "routine_missed" not in types(brain)
    await brain.tick(at(9, 40), "replay")
    assert "routine_missed" in types(brain)
    await brain.on_observation(Observation(at(10, 20), "Resident gets the paper", person=True,
                                           is_resident_likely=True, activity="resident_at_door", source="replay"))
    assert "resolved" in types(brain)


async def test_no_routine_alert_when_she_was_out(brain):
    seed_history(brain.store, DAY, TZ)
    await brain.on_observation(Observation(at(7, 50), "Resident gets the paper", person=True,
                                           is_resident_likely=True, activity="resident_at_door", source="replay"))
    await brain.tick(at(11, 0), "replay")
    assert "routine_missed" not in types(brain)


async def test_night_activity_is_urgent(brain):
    await brain.on_observation(Observation(at(3, 12), "Resident on the porch in a robe", person=True,
                                           is_resident_likely=True, activity="resident_at_door"))
    night = [e for e in brain.store.events() if e["type"] == "night_activity"]
    assert night and night[0]["severity"] == "urgent"


async def test_repeat_visitor_needs_two_earlier_days(brain):
    seed_history(brain.store, DAY, TZ)  # seeds the clipboard man on the two previous days
    sig = "man, grey hoodie, clipboard, no uniform"
    await brain.on_observation(Observation(at(14, 12), "Man with clipboard", person=True,
                                           activity="visitor_at_door", visitor_signature=sig, source="replay"))
    assert "repeat_visitor" in types(brain)


async def test_live_never_uses_replay_history(brain):
    """Seeded replay history must not leak into live decisions (a bug we hit on the real stream)."""
    seed_history(brain.store, DAY, TZ)
    await brain.tick(at(9, 40), "ring_live")  # live has no learned routine -> no routine alert
    await brain.on_observation(Observation(at(14, 12), "Man with clipboard", person=True, activity="visitor_at_door",
                                           visitor_signature="man, grey hoodie, clipboard, no uniform"))
    assert "routine_missed" not in types(brain) and "repeat_visitor" not in types(brain)


async def test_new_visitor_is_not_flagged(brain):
    seed_history(brain.store, DAY, TZ)
    await brain.on_observation(Observation(at(14, 12), "Woman with flowers", person=True,
                                           activity="visitor_at_door", visitor_signature="woman, red coat, flowers"))
    assert "repeat_visitor" not in types(brain)


def test_webhook_signature_roundtrip():
    raw = b'{"data": {"type": "button_press"}}'
    assert webhooks.verify(raw, webhooks.sign(raw, KEY), KEY)
    assert not webhooks.verify(raw + b" ", webhooks.sign(raw, KEY), KEY)
    assert not webhooks.verify(raw, webhooks.sign(raw, "other-key"), KEY)


def test_webhook_payload_matches_ring_format():
    p = webhooks.build_payload("motion_detected", "dev1", at(10, 6), "package_delivery")
    assert p["meta"]["version"] == "1.1"
    assert p["data"]["attributes"]["sub_type"] == "package_delivery"
    parsed = webhooks.parse(__import__("json").dumps(p).encode())
    assert parsed["type"] == "motion_detected" and parsed["device_id"] == "dev1"
    assert abs((parsed["time"] - at(10, 6)).total_seconds()) < 1


@pytest.mark.parametrize("scenario", sorted(SCENARIOS))
async def test_scenarios_run_end_to_end(brain, scenario):
    received = []

    async def sink(raw, sig):
        assert webhooks.verify(raw, sig, KEY)
        received.append(webhooks.parse(raw))

    r = Replayer(brain, brain.store, TZ, KEY, sink, max_gap_s=0, min_gap_s=0)
    await r.run(scenario, day=DAY)
    t = types(brain)
    expected = {"night_activity": "night_activity", "routine_missed": "routine_missed",
                "repeat_visitor": "repeat_visitor", "package": "package_unattended",
                "full_day": "daily_summary"}[scenario]
    assert expected in t, t
    assert received, "scenario should send at least one signed Ring webhook"
    assert all(e["source"] == "replay" for e in brain.store.events())


async def test_package_scenario_only_tells_the_package_story(brain):
    async def sink(raw, sig):
        pass

    await Replayer(brain, brain.store, TZ, KEY, sink, max_gap_s=0, min_gap_s=0).run("package", day=DAY)
    assert "routine_missed" not in types(brain)
    alert = next(e for e in brain.store.events() if e["type"] == "package_unattended")
    assert "last seen at the door at 7:48" in alert["summary"], alert["summary"]
