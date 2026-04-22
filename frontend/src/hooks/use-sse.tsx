"use client";

import { createContext, useContext, useEffect, useRef, useState, useCallback } from "react";
import type { ReactNode } from "react";
import type { ReviewUpdate } from "@/types";

type SSEStatus = "connecting" | "connected" | "disconnected" | "reconnecting";

interface SSEContextValue {
  status: SSEStatus;
  subscribe: (onMessage: (update: ReviewUpdate) => void) => () => void;
  reconnect: () => void;
}

const SSEContext = createContext<SSEContextValue | null>(null);

const MAX_RETRIES = 10;
const BASE_DELAY_MS = 3000;

export function SSEProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<SSEStatus>("disconnected");
  const subscribersRef = useRef<Set<(update: ReviewUpdate) => void>>(new Set());
  const esRef = useRef<EventSource | null>(null);
  const retryCountRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isMountedRef = useRef(true);
  const backendAvailableRef = useRef(true);
  const connectRef = useRef<() => void>(() => {});

  const openEventSource = useCallback((url: string) => {
    if (!isMountedRef.current) return;

    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => {
      if (!isMountedRef.current) return;
      backendAvailableRef.current = true;
      retryCountRef.current = 0;
      setStatus("connected");
    };

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as ReviewUpdate;
        subscribersRef.current.forEach((cb) => cb(data));
      } catch {
        // ignore malformed events
      }
    };

    es.onerror = () => {
      es.close();
      esRef.current = null;
      if (!isMountedRef.current) return;
      setStatus("disconnected");
      backendAvailableRef.current = false;

      if (retryCountRef.current < MAX_RETRIES) {
        const delay = Math.min(BASE_DELAY_MS * 2 ** retryCountRef.current, 30000);
        retryCountRef.current++;
        reconnectTimerRef.current = setTimeout(() => {
          if (isMountedRef.current) connectRef.current();
        }, delay);
      }
    };
  }, []);

  const connect = useCallback(() => {
    if (!isMountedRef.current) return;
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || "";
    const url = `${baseUrl}/reviews/stream`;

    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }

    const currentRetry = retryCountRef.current;
    setStatus(currentRetry > 0 ? "reconnecting" : "connecting");

    // Quick health check before opening SSE to avoid console noise when backend is down
    if (baseUrl && !backendAvailableRef.current) {
      fetch(`${baseUrl}/health`, { method: "GET", cache: "no-store" })
        .then((res) => {
          if (res.ok) backendAvailableRef.current = true;
        })
        .catch(() => {
          /* backend still down */
        })
        .finally(() => {
          if (!isMountedRef.current) return;
          if (!backendAvailableRef.current) {
            setStatus("disconnected");
            if (retryCountRef.current < MAX_RETRIES) {
              const delay = Math.min(BASE_DELAY_MS * 2 ** retryCountRef.current, 30000);
              retryCountRef.current++;
              reconnectTimerRef.current = setTimeout(() => {
                if (isMountedRef.current) connectRef.current();
              }, delay);
            }
          } else {
            // Backend is back, proceed with SSE connection
            openEventSource(url);
          }
        });
      return;
    }

    openEventSource(url);
  }, [openEventSource]);

  connectRef.current = connect;

  useEffect(() => {
    isMountedRef.current = true;
    connectRef.current();
    return () => {
      isMountedRef.current = false;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
    };
  }, []);

  const reconnect = useCallback(() => {
    retryCountRef.current = 0;
    backendAvailableRef.current = true;
    connectRef.current();
  }, []);

  const subscribe = useCallback((onMessage: (update: ReviewUpdate) => void) => {
    subscribersRef.current.add(onMessage);
    return () => {
      subscribersRef.current.delete(onMessage);
    };
  }, []);

  return (
    <SSEContext.Provider value={{ status, subscribe, reconnect }}>
      {children}
    </SSEContext.Provider>
  );
}

export function useSSE() {
  const ctx = useContext(SSEContext);
  if (!ctx) {
    throw new Error("useSSE 必须在 SSEProvider 内使用");
  }
  return ctx;
}
