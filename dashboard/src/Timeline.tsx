import { useMemo, useState } from "react";
import type { PorchEvent } from "../../shared/types";
import { frameUrl } from "./api";
import { ICONS, SITUATIONS, dayIn, parseAlert, timeIn } from "./format";

interface Props {
  events: PorchEvent[]; // one source, oldest first
  tz: string;
}

/** Newest first: situations as cards (with the family text and "resolved" attached), observations as rows. */
export function Timeline({ events, tz }: Props) {
  const { items, alerts, resolved } = useMemo(() => {
    const alerts = new Map<string, PorchEvent>();
    const resolved = new Map<string, PorchEvent>();
    const items: PorchEvent[] = [];
    for (const e of events) {
      if (e.type === "alert_sent" && e.related_id) alerts.set(e.related_id, e);
      else if (e.type === "resolved" && e.related_id) resolved.set(e.related_id, e);
      else if (e.type !== "agent_thought" && e.type !== "alert_sent" && e.type !== "resolved") items.push(e);
    }
    return { items: items.reverse(), alerts, resolved };
  }, [events]);

  if (!items.length) {
    return (
      <section className="card timeline">
        <Header count={0} />
        <div className="empty">
          <div className="empty-icon">🏮</div>
          <p>Nothing at the door yet.</p>
          <p className="muted small">Events appear here the moment the doorbell sees something.</p>
        </div>
      </section>
    );
  }

  let lastDay = "";
  return (
    <section className="card timeline">
      <Header count={items.filter((e) => SITUATIONS.includes(e.type)).length} />
      <ol className="feed">
        {items.map((e) => {
          const day = dayIn(e.time, tz);
          const divider = day !== lastDay ? <li key={`d-${day}`} className="day">{day}</li> : null;
          lastDay = day;
          return [
            divider,
            e.type === "observation" ? (
              <Observation key={e.id} e={e} tz={tz} />
            ) : e.type === "daily_summary" ? (
              <SummaryItem key={e.id} e={e} tz={tz} />
            ) : (
              <Situation key={e.id} e={e} tz={tz} alert={alerts.get(e.id)} resolved={resolved.get(e.id)} />
            ),
          ];
        })}
      </ol>
    </section>
  );
}

function Header({ count }: { count: number }) {
  return (
    <div className="card-head">
      <h2>At the door today</h2>
      <span className="muted small">{count ? `${count} thing${count > 1 ? "s" : ""} worth knowing` : "All quiet"}</span>
    </div>
  );
}

function Observation({ e, tz }: { e: PorchEvent; tz: string }) {
  const img = frameUrl(e.frame_url);
  return (
    <li className="obs enter">
      <time>{timeIn(e.time, tz)}</time>
      {img ? <img src={img} alt="" /> : <span className="obs-dot" />}
      <div>
        <strong>{e.title}</strong>
        <span className="muted"> · {e.summary}</span>
      </div>
    </li>
  );
}

function Situation({ e, tz, alert, resolved }: { e: PorchEvent; tz: string; alert?: PorchEvent; resolved?: PorchEvent }) {
  const [why, setWhy] = useState(false);
  const img = frameUrl(e.frame_url);
  const sent = alert ? parseAlert(alert) : null;
  return (
    <li className={`sit sev-${e.severity} ${resolved ? "is-resolved" : ""} enter`}>
      <div className="sit-head">
        <span className="sit-icon">{ICONS[e.type] ?? "•"}</span>
        <div className="sit-title">
          <strong>{e.title}</strong>
          <time>{timeIn(e.time, tz)}</time>
        </div>
        {e.severity === "urgent" && <span className="pill pill-urgent">Urgent</span>}
        {e.severity === "notice" && <span className="pill pill-notice">Worth knowing</span>}
      </div>
      <div className="sit-body">
        <p>{e.summary}</p>
        {img && <img className="sit-img" src={img} alt="" />}
      </div>
      {sent && (
        <div className="sent">
          <div className="sent-meta">
            📱 Sent to {sent.to}
            {sent.channel && <span className="muted"> · {sent.channel}</span>}
          </div>
          <div className="bubble">{sent.message}</div>
        </div>
      )}
      {!sent && e.severity === "info" && <div className="muted small not-sent">The agent decided this didn't need a message.</div>}
      {resolved && (
        <div className="resolved">
          <span>✓</span> Resolved at {timeIn(resolved.time, tz)}: {resolved.summary}
        </div>
      )}
      {e.reasoning && (
        <button className="why" onClick={() => setWhy(!why)}>
          {why ? "Hide" : "Why did the agent decide this?"}
        </button>
      )}
      {why && <p className="reasoning">{e.reasoning}</p>}
    </li>
  );
}

function SummaryItem({ e, tz }: { e: PorchEvent; tz: string }) {
  return (
    <li className="sit sev-summary enter">
      <div className="sit-head">
        <span className="sit-icon">📝</span>
        <div className="sit-title">
          <strong>Evening summary</strong>
          <time>{timeIn(e.time, tz)}</time>
        </div>
      </div>
      <p className="summary-headline">{e.summary}</p>
      {e.reasoning && <p className="muted">{e.reasoning}</p>}
    </li>
  );
}
