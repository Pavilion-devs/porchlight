import { useCallback, useEffect, useRef, useState } from "react";
import type { Baseline, DailySummary, LiveView, PorchEvent, Source, Status, WsMessage } from "../../shared/types";
import { api, wsUrl } from "./api";

export interface Porch {
  connected: boolean; // WebSocket to our backend
  status: Status | null;
  statusAt: number; // when status arrived (for the token countdown)
  streamSeenAt: number; // last time the Ring stream reported "connected"
  live: LiveView | null;
  events: PorchEvent[];
  summary: DailySummary | null;
  baseline: Baseline | null;
  source: Source;
  setSource: (s: Source) => void;
  startDemo: (scenario: string) => Promise<void>;
}

const REFRESH_TYPES = new Set(["observation", "routine_missed", "daily_summary", "resolved", "alert_sent"]);

export function usePorch(): Porch {
  const [connected, setConnected] = useState(false);
  const [status, setStatus] = useState<Status | null>(null);
  const [statusAt, setStatusAt] = useState(0);
  const [streamSeenAt, setStreamSeenAt] = useState(0);
  const [live, setLive] = useState<LiveView | null>(null);
  const [events, setEvents] = useState<PorchEvent[]>([]);
  const [summary, setSummary] = useState<DailySummary | null>(null);
  const [baseline, setBaseline] = useState<Baseline | null>(null);
  const [source, setSourceState] = useState<Source>("ring_live");
  const pinned = useRef(false); // the user picked a source themselves
  const sourceRef = useRef(source);
  sourceRef.current = source;

  const setSource = useCallback((s: Source) => {
    pinned.current = true;
    setSourceState(s);
  }, []);

  // Summary + routine for the selected source, refreshed when something relevant happens.
  const refreshTimer = useRef<number>();
  const refresh = useCallback((delay = 400) => {
    window.clearTimeout(refreshTimer.current);
    refreshTimer.current = window.setTimeout(() => {
      const s = sourceRef.current;
      api.summary(s).then(setSummary).catch(() => undefined);
      api.baseline(s).then(setBaseline).catch(() => undefined);
    }, delay);
  }, []);

  useEffect(() => refresh(0), [source, refresh]);
  useEffect(() => {
    const t = window.setInterval(() => refresh(0), 30_000);
    return () => window.clearInterval(t);
  }, [refresh]);

  const onStatus = useCallback((s: Status) => {
    setStatus(s);
    setStatusAt(Date.now());
    if (s.stream === "connected") setStreamSeenAt(Date.now());
    if (s.demo_running && !pinned.current) setSourceState("replay");
  }, []);

  // Initial load, then the WebSocket keeps everything current.
  useEffect(() => {
    let socket: WebSocket | null = null;
    let retry: number | undefined;
    let closed = false;

    const load = async () => {
      const [ev, lv, st] = await Promise.all([api.events(), api.live(), api.status()]);
      setEvents(ev);
      setLive(lv);
      onStatus(st);
      if (!pinned.current && !st.demo_running) {
        const latest = ev[ev.length - 1];
        if (latest) setSourceState(latest.source);
      }
    };

    const connect = () => {
      socket = new WebSocket(wsUrl());
      socket.onopen = () => {
        setConnected(true);
        load().catch(() => undefined);
      };
      socket.onmessage = (m) => {
        const msg: WsMessage = JSON.parse(m.data);
        if (msg.kind === "event") {
          setEvents((prev) => (prev.some((e) => e.id === msg.data.id) ? prev : [...prev, msg.data]));
          if (msg.data.source === sourceRef.current && REFRESH_TYPES.has(msg.data.type)) refresh();
        } else if (msg.kind === "live") {
          setLive(msg.data);
        } else if (msg.kind === "status") {
          onStatus(msg.data);
        }
      };
      socket.onclose = () => {
        setConnected(false);
        if (!closed) retry = window.setTimeout(connect, 2000);
      };
    };
    connect();
    return () => {
      closed = true;
      window.clearTimeout(retry);
      socket?.close();
    };
  }, [onStatus, refresh]);

  const startDemo = useCallback(
    async (scenario: string) => {
      await api.startDemo(scenario);
      // The backend wipes the previous replay before playing a new one.
      setEvents((prev) => prev.filter((e) => e.source !== "replay"));
      pinned.current = false;
      setSourceState("replay");
      refresh(300);
    },
    [refresh],
  );

  return {
    connected, status, statusAt, streamSeenAt, live, events, summary, baseline, source, setSource, startDemo,
  };
}
