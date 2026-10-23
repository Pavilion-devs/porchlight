# Demo video: script and shot list (target 2:45, hard limit 3:00)

Judges may stop at 3:00, so the best material comes first. Speak calmly, like you're telling a friend about your mom.

## Before you record (15 min)

1. **A fresh Ring Playground token:** paste it into `.env`, then run `make push-token`. You have 30 minutes per token, so record the live part first.
2. **A fast package alert for the live shot:** set `PACKAGE_ALERT_MINUTES=2` in `.env`, then run `make deploy`.
3. **Telegram:** set it up (`make telegram`), then `make deploy`. Put your phone on the desk, with Telegram open and notifications on.
4. **Claude app:** add the connector *Settings → Connectors → Add custom connector →* `https://100-57-176-133.sslip.io/mcp`.
5. **Stop the backend on your Mac,** so only AWS pulls the Ring stream.
6. **Browser:** 1440×900, full screen, dashboard at https://100-57-176-133.sslip.io. Hide bookmarks. **Never show the Playground token.**
7. **Screen recorder:** QuickTime (*File → New Screen Recording*) or OBS. Record the phone with a second phone, or mirror it with QuickTime (*New Movie Recording → choose the iPhone*).

## Script

| Time | On screen | Voiceover |
|---|---|---|
| **0:00–0:15** | Close-up of the phone buzzing. A Telegram message with the doorbell photo: *"Hey Ade, a package has been on Mom's step since…"* | "My mom lives alone. I can't be there every day. But her front door can tell me when something's off." |
| **0:15–0:30** | The dashboard, a slow pan: door view → timeline → care agent → routine | "This is Porchlight. It watches only her Ring doorbell, never a camera inside her home. It learns her normal day, and messages the family only when something needs attention." |
| **0:30–1:05** | **Live.** Ring Developer Playground → click **Package**. Cut to the dashboard: the *LIVE · Ring doorbell* frame, with "A yellow package is sitting on the front doorstep" and the Package chip lit | "This is a real Ring doorbell stream from Ring's developer sandbox. Every few seconds Porchlight takes a frame and Claude on Amazon Bedrock describes it. It's a package, and nobody's picked it up." |
| **1:05–1:25** | Two minutes later: the **Care agent** panel types "Checking the routine… Checking the last 12 hours…". The alert card appears with the blue message bubble. The phone buzzes | "When it's been out too long, a care agent built with the Strands SDK investigates before it says anything. It checks her routine, recent activity and what we've already been told. Then it writes one calm, specific message." |
| **1:25–2:05** | **Replay.** Click *Replayed day*, then **A whole day**. The timeline fills: newspaper 7:48am, package, the *Same visitor, 3rd time this week* card turns red, the bubble appears. Click **Why did the agent decide this?** End on the evening summary | "The sandbox has no history, so we replay a whole day through the same pipeline, clearly labelled. A man with a clipboard has come three days in a row with no delivery. The agent flags it as urgent, explains why, and at night writes the family a summary of her day." |
| **2:05–2:30** | **Ask Porchlight.** The Claude app: type *"How's Mom doing today?"*. It calls Porchlight's tools and answers with her morning, the package, the visitor and her routine | "And families don't need another app to check. Porchlight is an MCP server, the standard Alexa+ integrations use. So you can just ask your assistant: how's Mom today?" |
| **2:30–2:45** | One slide: Ring live stream → Bedrock vision (Haiku 4.5) → rules + memory → Strands agent (Sonnet 4.6) → Telegram, dashboard and MCP, all on EC2. Underneath: **21/21 situations messaged · 0 messages on normal days** | "It runs on AWS: Bedrock for vision and the agent, on EC2 with no keys on the box. Across 30 replayed days it caught 21 out of 21 situations, and sent nothing on normal days." |
| **2:45–2:55** | The dashboard, then the logo | "Porchlight. A light on at your parent's front door. Built on Ring and AWS." |

## Tips
- **Record in pieces** (live, replay, MCP, slide) and join them in iMovie. Speed up waiting parts 4×, especially the 2-minute package wait.
- **Shoot the live part first,** while the token is fresh.
- **Captions:** add them, since many judges watch without sound.
- **Upload:** YouTube, **Public** (not Unlisted, unless the rules allow it), English title: *Porchlight: a care agent for your parent's front door (Ring + AWS)*.
- **Music:** none, or a track from YouTube's free Audio Library. Nothing copyrighted.
