# Friction Log

Submitted with our Devpost entry (worth up to a 10% judging bonus). Log friction **as it happens**: task, steps, expected vs. actual, severity, workaround, suggestion.

Severity: **High** (blocked us) · **Medium** (cost real time) · **Low** (annoyance)

---

### 1. Snapshot endpoint: request body not documented at the endpoint
- **Task:** Download a snapshot from the Playground doorbell.
- **Steps:** `POST /v1/devices/{id}/media/image/download` with an empty JSON body.
- **Expected:** An image, or an error naming the missing fields.
- **Actual:** `403 REQUEST_FORBIDDEN`: "Cannot authorize: missing required timestamp fields in request body." A 403 suggests an auth problem, not a body problem. The required body `{"type":"at_timestamp","timestamp":<ms>}` only appears in a multi-camera code sample further down the docs.
- **Severity:** Medium
- **Workaround:** Searched the full API page for "timestamp".
- **Suggestion:** Return 400 with the schema, and put the body schema next to the endpoint in the reference.

### 2. Sandbox never records, so media download always returns 416
- **Task:** Get a snapshot or clip from a Playground live-view event.
- **Steps:** Triggered a live view (an `on_demand` event appears in history), then requested image and video download inside that event's time window.
- **Expected:** Sandbox media for the simulated event.
- **Actual:** `416 MEDIA_NOT_FOUND` every time. Nothing says the sandbox can't produce recordings.
- **Severity:** High (it changed our architecture)
- **Workaround:** Pulled frames from the WHEP live stream ourselves with `aiortc`.
- **Suggestion:** Give the Playground device recorded sample media, or document that media download isn't available in the sandbox.

### 3. Sandbox has a single doorbell, though sensor and Chime scopes are offered
- **Task:** Build a caregiving app that uses contact, temperature and air-quality sensors and Chime audio.
- **Steps:** Enabled every scope on the app, then `GET /v1/devices`.
- **Expected:** Synthetic sensors / Chime to match the scopes (the getting-started docs mention "synthetic Ring devices and events").
- **Actual:** One device, "Playground Device" (Doorbell Pro). All sensor capabilities `null`, no Chime, `audio.supported_actions: null`.
- **Severity:** High (we had to drop sensor features from the core design)
- **Workaround:** Redesigned around the doorbell only; sensor features run in a labelled replayer.
- **Suggestion:** Add synthetic sensors and a Chime to the Playground, or say which device types the sandbox covers.

### 4. Playground token expiry isn't shown
- **Task:** Keep developing against the sandbox.
- **Steps:** Generated a token, worked for a while, then calls started returning `401`.
- **Expected:** The expiry shown next to the token.
- **Actual:** The token silently expires after **30 minutes** (we found out by decoding the JWT).
- **Severity:** Medium
- **Workaround:** Decode `exp` from the JWT; regenerate before each session.
- **Suggestion:** Show a countdown in the Playground, and document how partner apps get a longer-lived dev token.

### 5. Sandbox live streams end after ~7–8 seconds
- **Task:** Watch the Package scene long enough to see the full clip.
- **Steps:** Opened a WHEP session from our code with the Playground popup closed.
- **Expected:** A stream for the documented 30 s (battery) / 60 s (wired) session limit.
- **Actual:** Ring closes the session after ~7–8 s.
- **Severity:** Low–Medium
- **Workaround:** Reconnect in a loop.
- **Suggestion:** Document the sandbox stream length, or match the production limits.

### 6. (Positive) Playground scene selection works for our own client
- Clicking Package / Vehicle / Motion in the Playground changes the footage our own WHEP client receives, and it persists after the popup closes. Very useful for demos. Worth documenting.

---

## AWS

### 7. `aws login` credentials don't work in boto3 without an extra package
- **Task:** Call Bedrock from Python (boto3) on a machine where the AWS CLI works.
- **Steps:** `aws sts get-caller-identity` works; `boto3.client("bedrock-runtime")` in a fresh venv.
- **Expected:** boto3 picks up the same credentials as the CLI.
- **Actual:** `MissingDependencyException: Using the login credential provider requires an additional dependency. You will need to pip install "botocore[crt]"`.
- **Severity:** Low (clear message, but every new environment hits it)
- **Workaround:** `pip install "botocore[crt]"`.
- **Suggestion:** Bundle the login provider's dependency, or mention it in the Bedrock Python quickstart.

### 8. Bedrock lists models the account can't call
- **Task:** Pick the newest Claude model for vision.
- **Steps:** `aws bedrock list-foundation-models` shows Sonnet 5.5 / Haiku 5.5 as `ACTIVE`; `converse` with them.
- **Expected:** Listed + ACTIVE means callable, or the listing shows access status.
- **Actual:** `AccessDeniedException: ... is not available for this account`. We found what works by trial calls.
- **Severity:** Low–Medium
- **Workaround:** Probe each model with a 5-token call.
- **Suggestion:** Show per-account access in `list-foundation-models` / `list-inference-profiles`.

### 9. (Positive) Strands structured output made the agent dependable
- `invoke_async(..., structured_output_model=PydanticModel)` gave us typed decisions after free-form tool use, with no JSON parsing code. Tools as plain decorated Python functions made the agent easy to test. The first working agent took under an hour.
