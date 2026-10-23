# Devpost submission: copy-paste text

Fill in the items marked **TODO** before submitting.

- **Project name:** Porchlight
- **Tagline (≤200 chars):** A care agent for your parent's front door. Porchlight watches their Ring doorbell, learns their normal day, and messages the family only when something needs attention. No cameras inside.
- **Track:** Ring (priority category: caretaking)
- **Mini challenges:** AWS Builder, Open Source
- **Repo:** https://github.com/Pavilion-devs/porchlight (public, MIT)
- **Live demo:** https://100-57-176-133.sslip.io (dashboard) · https://100-57-176-133.sslip.io/mcp (Ask Porchlight MCP server)
- **Video:** **TODO** YouTube link
- **Built with:** Ring Partner API (WHEP live view, devices, event history, v1.1 webhooks with HMAC), Ring Developer Playground, Amazon Bedrock (Claude Haiku 4.5 vision, Claude Sonnet 4.6 agent), Strands Agents SDK, Amazon EC2, AWS IAM, Python, FastAPI, aiortc, SQLite, MCP Python SDK, React, Vite, Telegram Bot API

---

## About the project

### Inspiration
Millions of older adults live alone, and their families live far away. The usual options are a daily phone call that misses most of the day, or cameras inside the home that many parents refuse. Most homes already have something in between: a video doorbell. The front door is where a day's routine shows. She picks up the paper, she goes for a walk, a package arrives, someone keeps coming by. We wanted the doorbell to speak up for her only when it matters.

### What it does
Porchlight watches the parent's Ring doorbell and turns it into a calm, smart family helper:
- **Package left outside:** "A package arrived at 10:06am and is still on the step. She hasn't been to the door since 7:48am."
- **Package taken** by someone who isn't her.
- **Repeat visitor:** "A man with a clipboard and no uniform has come three days in a row with no delivery."
- **Routine missed:** it learns when she usually first steps out. If she hasn't by her latest usual time, the family hears about it, with more urgency if she was up at 3am.
- **Night activity** at the door between 1am and 5am.
- **An evening summary** of her day.

Before messaging anyone, a **care agent investigates**. It checks the learned routine, recent door activity, visitor history and what the family was already told, then decides whether to send one specific, kind message and how urgent it is. The family gets a Telegram message with the doorbell photo, plus a dashboard that shows the live door view, the timeline, the agent's reasoning ("Why did the agent decide this?") and today compared with her usual day.

**Ask Porchlight:** Porchlight is also an **MCP server** (Streamable HTTP), the standard Alexa+ integrations use. Any assistant can answer *"How's Mom doing today?"* or *"Has that clipboard guy been back?"* from what the doorbell saw.

### How we built it
- **Ring:** a WHEP (WebRTC) client written with `aiortc` opens live-view sessions on the Playground doorbell. It reconnects every ~8 s, because sandbox sessions end, and samples a frame every 3 s, skipping unchanged frames. It also uses Ring device discovery, event history, and a v1.1 webhook handler with HMAC-SHA256 verification and request-id idempotency.
- **Vision:** Claude Haiku 4.5 on Amazon Bedrock (Converse API, forced tool call) turns each frame into structured facts: person, package, vehicle, activity, a visitor "signature" and concerns.
- **Brain:** cheap deterministic rules plus memory in SQLite. It learns the routine (median and spread over 14 days), tracks packages (tolerating a missed frame), matches repeat visitors by signature, and spots night activity.
- **Care agent:** the Strands Agents SDK with Claude Sonnet 4.6 on Bedrock. It has four tools (`get_recent_activity`, `get_routine_baseline`, `get_visitor_history`, `get_alerts_sent_today`) and returns a typed decision through Strands structured output. Every tool call streams to the dashboard as a "thought".
- **Replayer:** Ring's sandbox has one doorbell and no history, so the replayer seeds 14 days of believable routine and plays scripted days on a compressed clock. It sends **signed Ring-format webhooks through the same handler** as real ones. Live and replayed data never mix: every query, agent tool, summary and API response is scoped to one source.
- **Ask Porchlight:** six read-only MCP tools, built with the official MCP Python SDK, mounted at `/mcp`, with an optional bearer token.
- **Dashboard:** React and Vite, live over a WebSocket, served by the backend.
- **AWS:** one EC2 instance. Its IAM role can only invoke Anthropic models on Bedrock, so there are no keys on the box. Caddy provides HTTPS, systemd keeps it running, and `make deploy` ships an update in about a minute.

### Challenges we ran into
- **The sandbox never records,** so snapshots and clips return 416. We built our own frame pipeline from the WHEP stream.
- **Sandbox streams end after about 8 seconds,** and Playground tokens expire after 30 minutes. We added reconnect loops, a token countdown on the dashboard, and `make push-token`.
- **One doorbell, no history:** we built an honest, clearly labelled replayer that uses the real webhook path.
- **A bug we caught on the real stream:** the agent quoted the replayed day while reasoning about the live doorbell. We scoped every query by source and added a regression test.

### Accomplishments that we're proud of
- **The full live chain works on a real Ring stream:** frame → vision → package tracked → agent investigates → family message.
- **Evaluation:** across 30 replayed days with the real agent on Bedrock, **21 of 21 situations reached the family, 15 normal days sent 0 messages, and the agent made the same decision every run in 9 of 10 cases.** [`eval/AGENT_EVAL.md`](https://github.com/Pavilion-devs/porchlight/blob/main/eval/AGENT_EVAL.md) has the method and caveats.
- **The agent is honest when it doesn't know.** With no history on the live doorbell it says "We don't have enough history yet to know if that's normal for her".
- **Anyone can run it:** `make setup && make run-offline && make demo` works with no Ring or AWS account. There are 18 tests, a `make check` setup doctor, and a friction log.

### What we learned
An agent is most useful when deterministic rules decide *when* to think and the LLM decides *what to say* and *whether to say it*. It also helps when every step the agent takes is visible to the family.

### What's next for Porchlight
- Real staging users on real doorbells, with refresh tokens.
- Ring sensors (contact, motion) and Chime for "Mom, your package is outside" spoken at the door.
- Publishing Ask Porchlight as an Alexa+ integration.
- Weekly trend reports for the family and for care professionals.
- Moving the agent to Amazon Bedrock AgentCore, with AgentCore Memory for the routine.

---

## AWS Builder: services and how we use them
- **Amazon Bedrock, Converse API:**
  - Claude Haiku 4.5 (`us.anthropic.claude-haiku-4-5-20251001-v1:0`) describes every changed doorbell frame as structured JSON, using a forced tool call. See `backend/porchlight/vision.py`.
  - Claude Sonnet 4.6 (`us.anthropic.claude-sonnet-4-6`) powers the care agent and the evening summary.
- **Strands Agents SDK:** the `CareAgent` uses `BedrockModel`, four `@tool` functions over our memory, and `structured_output_model` for typed decisions. See `backend/porchlight/agent.py`.
- **Amazon EC2 + AWS IAM:** production runs on a t3.small. The instance profile `porchlight-ec2` allows only `bedrock:InvokeModel`/`Converse` on Anthropic models, so there are no credentials on disk. See `deploy/`.
- **Evaluation on AWS:** the agent evaluation ran on the same instance through the same role (`eval/agent_eval.py`).

## Open Source
- **Contribution URL:** https://github.com/AmazonAppDev/ring-api-helloworld/pull/48
- **Our repo:** https://github.com/Pavilion-devs/porchlight
- **GitHub username:** Pavilion-devs
- **What we did:** we added `scripts/describe_frame.py` to Amazon's official Ring API sample. It sends a frame from a Ring camera to Claude on Amazon Bedrock and gets back structured JSON (person, package, vehicle, activity, concern) using a forced tool call. The README now has a short "Add AI" section.
- **Why it matters:** the sample shows how to get video out of Ring, but not how to understand it. This is the smallest working bridge from a Ring frame to an AI decision, and it's the same technique Porchlight's vision step uses. Porchlight itself is also MIT-licensed, including the Ring WHEP frame watcher, the webhook signer/verifier, and the replayer that sends signed Ring-format webhooks for sandbox testing.

---

## Product feedback

**Ring Partner API (Amazon Vision API)**
- **What we used it for:**
  - `GET /v1/devices` (with `include=status,capabilities,location,configurations`)
  - `GET /v1/history/devices/{id}/events`
  - WHEP live view (`POST`/`DELETE …/media/streaming/whep/sessions`)
  - the image download endpoint
  - v1.1 webhook payloads with HMAC-SHA256 signatures
- **What worked well:**
  - WHEP is standard, so a non-browser client (Python + aiortc) worked with only a recvonly offer.
  - JSON:API responses with `include` are clean.
  - The webhook signature scheme is simple and well specified.
- **What needs work:**
  - The image download body is only shown in a sample. A missing body returns 403 instead of 400.
  - The sandbox never records, so download always returns 416.
  - Webhooks can't be triggered from the sandbox.
  - Details are in the friction log, entries 1, 2 and 10.
- **Would we build with it again:** Yes. The live stream plus webhooks is a strong base for caretaking and home automation.

**Ring Developer Playground (sandbox)**
- **What worked well:**
  - It took minutes to go from zero to a real stream.
  - Package / Vehicle / Motion scene selection also drives our own WHEP client, which was great for demos.
- **What needs work:**
  - Tokens expire after 30 minutes and the Playground doesn't show it.
  - Streams end after about 8 seconds.
  - There's one doorbell even though sensor and Chime scopes are offered.
  - No webhooks.
- **Onboarding:** fast to start, but slow to learn the sandbox's limits. A one-page "what the sandbox can and can't do" would save hours.

**Ring knowledge MCP server (developer docs over MCP)**
- **What we used it for:** checking webhook delivery requirements from inside our coding assistant.
- **What worked well:** precise, citable answers.
- **Suggestion:** link it from the Playground page.

**Amazon Bedrock**
- **What we used it for:** Converse for vision (Haiku 4.5) and the agent (Sonnet 4.6), with US cross-region inference profiles.
- **What worked well:** Converse's forced `toolChoice` gives dependable JSON from images in about 1.3 s.
- **What needs work:**
  - `list-foundation-models` shows models as ACTIVE that the account can't call.
  - `aws login` credentials need `botocore[crt]` in boto3.
- **Would we use it again:** Yes.

**Strands Agents SDK**
- **What worked well:**
  - Tools are plain decorated Python functions.
  - `structured_output_model` gave typed decisions after free-form tool use.
  - Our first working agent took under an hour.
- **Suggestion:** a documented hook for streaming tool-call events to a UI. We wrapped our tools to publish "thoughts".
- **Would we use it again:** Yes.

**Amazon EC2 + IAM:** an instance profile with a narrow Bedrock policy made the deployment keyless and robust.

## Feature requests
| Request | Why it matters | Urgency |
|---|---|---|
| Playground actions emit signed webhooks to the app's Webhook URL (or a "send test webhook" button) | Webhooks are the main event channel and can't be tested without hardware | **Critical** |
| Sandbox recordings, so image and clip download work | The media endpoints are untestable in the sandbox; every vision app needs them | Important |
| Synthetic sensors and a Chime in the Playground | Caretaking and home automation, Ring's priority categories, depend on them | Important |
| Show token expiry in the Playground, and a longer-lived dev token | 30-minute silent expiry interrupts every dev session | Important |
| Match production stream length in the sandbox (or document ~8 s) | Avoids surprise reconnect logic | Nice-to-have |
| `list-foundation-models` shows per-account access | Saves trial-and-error calls | Nice-to-have |

## Friction log
See [`docs/FRICTION_LOG.md`](https://github.com/Pavilion-devs/porchlight/blob/main/docs/FRICTION_LOG.md): 11 entries, each with the task, steps, expected vs actual, severity, workaround and suggestion.
