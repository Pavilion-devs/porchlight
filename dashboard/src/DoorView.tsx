import { useEffect, useState } from "react";
import type { LiveView, PorchEvent, Source } from "../../shared/types";
import { frameUrl } from "./api";
import { ago, timeIn } from "./format";

interface Props {
  source: Source;
  live: LiveView | null;
  events: PorchEvent[]; // already filtered to `source`
  tz: string;
  streamOk: boolean;
}

/** What the doorbell sees right now (live), or the latest moment of the replayed day. */
export function DoorView({ source, live, events, tz, streamOk }: Props) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, []);

  let img: string | null = null;
  let caption = "";
  let when = "";
  let chips = { person: false, package: false, vehicle: false };

  if (source === "ring_live") {
    img = frameUrl(live?.frame_url);
    caption = live?.description ?? "Waiting for the Ring stream…";
    when = live?.frame_url ? `Updated ${ago(now - new Date(live.time).getTime())}` : "";
    chips = { person: !!live?.person, package: !!live?.package, vehicle: !!live?.vehicle };
  } else {
    const obs = [...events].reverse().find((e) => e.type === "observation");
    img = frameUrl(obs?.frame_url); // scripted moments without a real Ring frame show the porch drawing
    caption = obs ? `${obs.title}. ${obs.summary}` : "Press a scenario below to replay a day at the door.";
    when = obs ? `${timeIn(obs.time, tz)} on the replayed day` : "";
  }

  return (
    <section className="card door">
      <div className="door-frame">
        {img ? <img src={img} alt="Latest frame from the Ring doorbell" /> : <DoorPlaceholder />}
        <div className="door-badges">
          {source === "ring_live" ? (
            <span className={`badge ${streamOk ? "badge-live" : "badge-muted"}`}>
              <i className="dot" /> {streamOk ? "LIVE · Ring doorbell" : "Ring stream offline"}
            </span>
          ) : (
            <span className="badge badge-replay">REPLAY · scripted day</span>
          )}
        </div>
        {source === "ring_live" && live?.frame_url && (
          <div className="door-chips">
            <Chip on={chips.person} label="Person" />
            <Chip on={chips.package} label="Package" />
            <Chip on={chips.vehicle} label="Vehicle" />
          </div>
        )}
      </div>
      <div className="door-caption">
        <div className="eyebrow">What Porchlight sees</div>
        <p>{caption}</p>
        {when && <div className="muted small">{when}</div>}
      </div>
    </section>
  );
}

function Chip({ on, label }: { on: boolean; label: string }) {
  return <span className={`chip ${on ? "chip-on" : ""}`}>{label}</span>;
}

function DoorPlaceholder() {
  return (
    <svg className="door-placeholder" viewBox="0 0 320 180" aria-hidden>
      <defs>
        <radialGradient id="glow" cx="50%" cy="22%" r="60%">
          <stop offset="0" stopColor="#f2b544" stopOpacity=".35" />
          <stop offset="1" stopColor="#f2b544" stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect width="320" height="180" fill="#14161c" />
      <rect width="320" height="180" fill="url(#glow)" />
      <rect x="128" y="46" width="64" height="112" rx="3" fill="#1e2129" stroke="#2c303b" />
      <circle cx="180" cy="104" r="3" fill="#f2b544" />
      <rect x="150" y="26" width="20" height="10" rx="2" fill="#f2b544" opacity=".9" />
      <rect x="0" y="158" width="320" height="22" fill="#191b22" />
    </svg>
  );
}
