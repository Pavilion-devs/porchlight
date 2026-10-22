import { useEffect, useMemo, useState } from "react";
import type { Source, Status } from "../../shared/types";
import { DoorView } from "./DoorView";
import { timeIn } from "./format";
import { Replay, Routine, Summary, Thinking } from "./Panels";
import { Timeline } from "./Timeline";
import { usePorch } from "./usePorch";

export default function App() {
  const p = usePorch();
  const tz = p.status?.timezone ?? "America/Los_Angeles";
  const parent = p.status?.parent_name ?? "Mom";
  const now = useNow();

  const mine = useMemo(() => p.events.filter((e) => e.source === p.source), [p.events, p.source]);
  const thoughts = useMemo(() => mine.filter((e) => e.type === "agent_thought"), [mine]);
  // The sandbox ends each live session after ~8 s and we reconnect, so treat "seen in the last 30 s" as live.
  const streamOk = p.status?.stream === "connected" || now - p.streamSeenAt < 30_000;

  return (
    <div className="app">
      <header className="top">
        <div className="brand">
          <Lamp />
          <div>
            <div className="brand-name">Porchlight</div>
            <div className="muted small">{parent}'s front door</div>
          </div>
        </div>
        <SourceSwitch source={p.source} onChange={p.setSource} />
        <div className="top-right">
          <StreamPill status={p.status} statusAt={p.statusAt} streamOk={streamOk} connected={p.connected} now={now} />
          <div className="clock">
            <b>{timeIn(new Date(now).toISOString(), tz)}</b>
            <span className="muted small">at {parent}'s</span>
          </div>
        </div>
      </header>

      {p.source === "replay" && (
        <div className="replay-banner">
          You're watching a <b>replayed day</b>: scripted events through the real pipeline, so you can see a full day
          in a minute. Switch to <button onClick={() => p.setSource("ring_live")}>Live door</button> for the real
          Ring doorbell.
        </div>
      )}

      <main className="grid">
        <div className="col">
          <DoorView source={p.source} live={p.live} events={mine} tz={tz} streamOk={streamOk} />
          <Summary summary={p.summary} parent={parent} />
        </div>
        <div className="col col-feed">
          <Timeline events={mine} tz={tz} />
        </div>
        <div className="col">
          <Thinking thoughts={thoughts} tz={tz} />
          <Routine baseline={p.baseline} />
          <Replay running={p.status?.demo_running ?? null} onStart={p.startDemo} source={p.source} />
        </div>
      </main>

      <footer className="foot muted small">
        Porchlight sees only the front door. No cameras inside the home. Built on the Ring Developer sandbox and
        Amazon Bedrock.
      </footer>
    </div>
  );
}

function useNow() {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, []);
  return now;
}

function SourceSwitch({ source, onChange }: { source: Source; onChange: (s: Source) => void }) {
  return (
    <div className="switch" role="tablist" aria-label="Which data to show">
      <button role="tab" aria-selected={source === "ring_live"} onClick={() => onChange("ring_live")}>
        <i className="dot dot-live" /> Live door
      </button>
      <button role="tab" aria-selected={source === "replay"} onClick={() => onChange("replay")}>
        Replayed day
      </button>
    </div>
  );
}

function StreamPill({ status, statusAt, streamOk, connected, now }: {
  status: Status | null; statusAt: number; streamOk: boolean; connected: boolean; now: number;
}) {
  if (!connected) return <span className="pill pill-urgent">Reconnecting to Porchlight…</span>;
  if (!status) return null;
  const left = status.ring_token_expires_in_s == null ? null
    : status.ring_token_expires_in_s - Math.round((now - statusAt) / 1000);
  if (status.stream === "token_expired" || (left != null && left <= 0)) {
    return <span className="pill pill-urgent" title="Generate a new Playground token">Ring token expired</span>;
  }
  if (streamOk) {
    return (
      <span className="pill pill-ok">
        <i className="dot" /> Ring connected{left != null && <span className="muted"> · token {Math.ceil(left / 60)} min</span>}
      </span>
    );
  }
  return <span className="pill pill-muted">{status.stream === "stopped" ? "Ring stream off" : "Connecting to Ring…"}</span>;
}

function Lamp() {
  return (
    <svg className="lamp" viewBox="0 0 40 40" aria-hidden>
      <circle cx="20" cy="19" r="17" fill="#f2b544" opacity=".14" />
      <circle cx="20" cy="19" r="10" fill="#f2b544" opacity=".22" />
      <path d="M14 10h12l-2.5 11h-7z" fill="#f2b544" />
      <rect x="15" y="22" width="10" height="3.5" rx="1.2" fill="#efe6d6" />
      <rect x="19" y="4" width="2" height="6" fill="#efe6d6" opacity=".6" />
    </svg>
  );
}
