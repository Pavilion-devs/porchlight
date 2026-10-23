"""Ask Porchlight MCP server: tools list and answers, through a real MCP client (in-process)."""
from dataclasses import replace
from datetime import date

from mcp.client import Client

from porchlight import mcp_server
from porchlight.brain import Brain
from porchlight.config import settings
from porchlight.hub import Hub
from porchlight.replayer import Replayer
from porchlight.store import Store
from test_brain import DAY, KEY, TZ, FakeNotifier, at


async def make_server(tmp_path):
    s = replace(settings, timezone="America/Los_Angeles", data_dir=tmp_path, hmac_key=KEY)
    brain = Brain(Store(":memory:"), Hub(), FakeNotifier(), s, agent=None)

    async def sink(raw, sig):
        pass

    await Replayer(brain, brain.store, TZ, KEY, sink, max_gap_s=0, min_gap_s=0).run("full_day", day=DAY)
    summary = lambda src: brain.store.get(f"summary:{src}:{DAY}")  # noqa: E731
    baseline = lambda src: {"days_learned": 14, "items": [  # noqa: E731
        {"label": "First time outside", "usual": "07:52", "window_minutes": 18, "today": "07:48", "status": "ok"}]}
    return mcp_server.build(brain, s, {"frame_url": None}, lambda: {"stream": "stopped"}, lambda: "replay",
                            lambda src: at(20, 30), summary, baseline)


async def test_tools_answer_from_the_replayed_day(tmp_path):
    async with Client(await make_server(tmp_path)) as c:
        names = {t.name for t in (await c.list_tools()).tools}
        assert {"how_is_parent_doing", "open_concerns", "visitors_this_week", "usual_routine"} <= names

        async def ask(tool, **args):
            return "\n".join(x.text for x in (await c.call_tool(tool, args)).content)

        overview = await ask("how_is_parent_doing")
        assert "replayed demo day" in overview and "last seen at the door at 3:05pm" in overview
        assert "clipboard" in await ask("visitors_this_week")
        assert "3 visits" in await ask("visitors_this_week")
        assert "7:52am" in await ask("usual_routine")
        concerns = await ask("open_concerns")
        assert "Package" in concerns and "resolved" in concerns
