// Porchlight backend <-> dashboard contract. Source of truth: CONTRACT.md

export type EventType =
  | "observation"
  | "agent_thought"
  | "package_unattended"
  | "package_taken"
  | "repeat_visitor"
  | "routine_missed"
  | "night_activity"
  | "alert_sent"
  | "daily_summary"
  | "resolved";

export type Severity = "info" | "notice" | "urgent";
export type Source = "ring_live" | "replay";

export interface PorchEvent {
  id: string;
  time: string; // ISO 8601 UTC
  type: EventType;
  severity: Severity;
  title: string;
  summary: string;
  reasoning?: string; // why the agent did this
  frame_url?: string; // e.g. "/api/frames/abc.jpg"
  source: Source;
  related_id?: string; // for alert_sent / resolved: the event they belong to
  device_id?: string;
}

export interface LiveView {
  time: string;
  frame_url: string | null;
  description: string; // what the AI sees right now
  person: boolean;
  package: boolean;
  vehicle: boolean;
  source: Source;
}

export interface DailySummary {
  date: string; // YYYY-MM-DD in the parent's timezone
  headline: string; // "Normal day. Two visitors, one delivery, all fine."
  body: string;
  visitors: number;
  deliveries: number;
  alerts: number;
  mood: "calm" | "watch" | "concern";
}

export interface RoutineItem {
  label: string; // "First time outside"
  usual: string; // "09:40" (local time)
  window_minutes: number; // +/- tolerance
  today: string | null; // "09:52", or null if it hasn't happened
  status: "ok" | "late" | "missed" | "pending";
}

export interface Baseline {
  parent_name: string;
  days_learned: number;
  items: RoutineItem[];
  source: Source;
}

export interface Status {
  stream: "connected" | "reconnecting" | "stopped" | "token_expired";
  ring_token_expires_in_s: number | null;
  demo_running: string | null; // scenario name, or null
  parent_name: string;
  timezone: string; // IANA, e.g. "America/Los_Angeles"
}

export type WsMessage =
  | { kind: "event"; data: PorchEvent }
  | { kind: "live"; data: LiveView }
  | { kind: "status"; data: Status };
