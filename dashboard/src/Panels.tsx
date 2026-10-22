import { useEffect, useRef, useState } from "react";
import type { Baseline, DailySummary, PorchEvent, RoutineItem, Source } from "../../shared/types";
import { clock, timeIn } from "./format";

// --- Today's summary --------------------------------------------------------------------------------

const MOOD = {
  calm: { label: "Calm day", cls: "mood-calm" },
  watch: { label: "Worth a look", cls: "mood-watch" },
  concern: { label: "Worth a call", cls: "mood-concern" },
};

export function Summary({ summary, parent }: { summary: DailySummary | null; parent: string }) {
  if (!summary) return null;
  const mood = MOOD[summary.mood] ?? MOOD.calm;
  return (
    <section className="card summary">
      <div className="card-head">
        <h2>Today at {parent}'s</h2>
        <span className={`mood ${mood.cls}`}><i className="dot" />{mood.label}</span>
      </div>
      <p className="summary-headline">{summary.headline}</p>
      {summary.body && <p className="muted">{summary.body}</p>}
      <div className="stats">
        <Stat n={summary.visitors} label={summary.visitors === 1 ? "visitor" : "visitors"} />
        <Stat n={summary.deliveries} label={summary.deliveries === 1 ? "delivery" : "deliveries"} />
        <Stat n={summary.alerts} label={summary.alerts === 1 ? "message sent" : "messages sent"} />
      </div>
    </section>
  );
}

function Stat({ n, label }: { n: number; label: string }) {
  return (
    <div className="stat">
      <b>{n}</b>
      <span>{label}</span>
    </div>
  );
}

// --- Routine: today vs usual -------------------------------------------------------------------------

const ROUTINE_STATUS: Record<RoutineItem["status"], { label: string; cls: string }> = {
  ok: { label: "As usual", cls: "rs-ok" },
  late: { label: "Unusual time", cls: "rs-late" },
  missed: { label: "Missed", cls: "rs-missed" },
  pending: { label: "Later today", cls: "rs-pending" },
};

export function Routine({ baseline }: { baseline: Baseline | null }) {
  if (!baseline) return null;
  const learned = baseline.days_learned;
  return (
    <section className="card routine">
      <div className="card-head">
        <h2>{baseline.parent_name}'s usual day</h2>
        <span className="muted small">{learned ? `Learned from ${learned} days` : "Still learning"}</span>
      </div>
      {!learned && (
        <p className="muted small">
          Porchlight needs a few days of door activity before it knows what's normal. Until then it won't raise
          routine alerts.
        </p>
      )}
      <ul className="routine-list">
        {baseline.items
          .filter((i) => learned || i.usual === "no activity")
          .map((i) => {
            const st = ROUTINE_STATUS[i.status];
            return (
              <li key={i.label}>
                <div>
                  <div className="routine-label">{i.label}</div>
                  <div className="muted small">
                    Usually {i.usual === "no activity" ? "no activity" : `~${clock(i.usual)}`}
                    {i.window_minutes > 0 && ` (±${i.window_minutes} min)`}
                  </div>
                </div>
                <div className="routine-today">
                  <span className={`rs ${st.cls}`}>{st.label}</span>
                  <span className="muted small">
                    {i.today ? (i.today === "no activity" ? "Quiet" : `Today ${clock(i.today)}`) : "—"}
                  </span>
                </div>
              </li>
            );
          })}
      </ul>
    </section>
  );
}

// --- The agent thinking -------------------------------------------------------------------------------

export function Thinking({ thoughts, tz }: { thoughts: PorchEvent[]; tz: string }) {
  const recent = thoughts.slice(-7);
  const last = recent[recent.length - 1];
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, []);
  // Thoughts that were already there when the page loaded are history, not "thinking now".
  const history = useRef<Set<string> | null>(null);
  if (history.current === null && thoughts.length) history.current = new Set(thoughts.map((t) => t.id));
  const [seenAt, setSeenAt] = useState<Record<string, number>>({});
  useEffect(() => {
    if (last && !seenAt[last.id] && !history.current?.has(last.id)) setSeenAt((s) => ({ ...s, [last.id]: Date.now() }));
  }, [last, seenAt]);
  const busy = !!last && now - (seenAt[last.id] ?? 0) < 6000;

  return (
    <section className="card thinking">
      <div className="card-head">
        <h2>Care agent</h2>
        <span className={`agent-state ${busy ? "busy" : ""}`}>
          <i className="dot" />
          {busy ? "Thinking…" : "Watching the door"}
        </span>
      </div>
      {!recent.length ? (
        <p className="muted small">
          When something happens, the agent checks her routine, recent activity and past visitors before deciding
          whether to message the family. Its steps show up here.
        </p>
      ) : (
        <ol className="thoughts">
          {recent.map((t) => (
            <li key={t.id} className={t.id === last?.id ? "latest enter" : "enter"}>
              <time>{timeIn(t.time, tz)}</time>
              <div>
                <strong>{t.title}</strong>
                <span>{t.id === last?.id ? <Typed text={t.summary} /> : t.summary}</span>
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function Typed({ text }: { text: string }) {
  const [n, setN] = useState(0);
  useEffect(() => {
    setN(0);
    const t = window.setInterval(() => setN((v) => (v >= text.length ? v : v + 2)), 18);
    return () => window.clearInterval(t);
  }, [text]);
  return <>{text.slice(0, n)}{n < text.length && <i className="caret" />}</>;
}

// --- Replay controls ------------------------------------------------------------------------------------

const SCENARIOS = [
  { id: "full_day", label: "A whole day", hint: "About a minute: package, a repeat visitor, evening summary" },
  { id: "package", label: "Package left out", hint: "Delivered at 10am, still outside after lunch" },
  { id: "repeat_visitor", label: "Repeat visitor", hint: "The same stranger, third day this week" },
  { id: "routine_missed", label: "Missed morning", hint: "Up at 3am, then not out by her usual time" },
  { id: "night_activity", label: "Up at night", hint: "At the front door at 3:12am" },
];

export function Replay({ running, onStart, source }: {
  running: string | null; onStart: (s: string) => Promise<void>; source: Source;
}) {
  const [error, setError] = useState<string | null>(null);
  return (
    <section className="card replay">
      <div className="card-head">
        <h2>Replay a day</h2>
        {running && <span className="badge badge-replay">Playing</span>}
      </div>
      <p className="muted small">
        Ring's sandbox doorbell has no history, so these scripted days run through the same pipeline as the real
        doorbell (signed Ring webhooks, vision, agent). Everything they create is marked REPLAY.
      </p>
      <div className="scenarios">
        {SCENARIOS.map((s) => (
          <button
            key={s.id}
            className={`scenario ${running === s.id ? "is-running" : ""}`}
            disabled={!!running}
            onClick={() => {
              setError(null);
              onStart(s.id).catch((e: Error) => setError(e.message));
            }}
          >
            <span>{running === s.id ? "▶ Playing…" : s.label}</span>
            <small>{s.hint}</small>
          </button>
        ))}
      </div>
      {error && <p className="error small">{error}</p>}
      {source === "ring_live" && !running && (
        <p className="muted small">Starting one switches the dashboard to the replayed day.</p>
      )}
    </section>
  );
}
