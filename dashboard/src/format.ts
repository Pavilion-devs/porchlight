import type { EventType, PorchEvent } from "../../shared/types";

export const SITUATIONS: EventType[] = [
  "package_unattended", "package_taken", "repeat_visitor", "routine_missed", "night_activity",
];

export const ICONS: Partial<Record<EventType, string>> = {
  package_unattended: "📦", package_taken: "🚨", repeat_visitor: "🧍", routine_missed: "⏰",
  night_activity: "🌙", daily_summary: "📝", observation: "👁",
};

export function timeIn(iso: string, tz: string): string {
  return new Date(iso)
    .toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", timeZone: tz })
    .replace(" AM", "am").replace(" PM", "pm");
}

export function dayIn(iso: string, tz: string): string {
  return new Date(iso).toLocaleDateString("en-US", { weekday: "long", month: "short", day: "numeric", timeZone: tz });
}

/** "07:52" (local, from the backend) -> "7:52am" */
export function clock(hhmm: string | null): string {
  if (!hhmm || !/^\d{1,2}:\d{2}$/.test(hhmm)) return hhmm ?? "";
  const [h, m] = hhmm.split(":").map(Number);
  return `${h % 12 || 12}:${String(m).padStart(2, "0")}${h < 12 ? "am" : "pm"}`;
}

export function ago(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000));
  if (s < 5) return "just now";
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  return `${Math.round(s / 3600)}h ago`;
}

/** alert_sent summary is `📱 <channel> → <name>: "<message>"` */
export function parseAlert(e: PorchEvent): { channel: string; to: string; message: string } {
  const m = e.summary.match(/^📱\s*(.+?)\s*→\s*(.+?):\s*"([\s\S]*)"$/);
  return m ? { channel: m[1], to: m[2], message: m[3] } : { channel: "", to: "family", message: e.summary };
}
