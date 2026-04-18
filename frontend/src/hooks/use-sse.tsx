"use client";

import { createContext, useContext, useEffect, useRef, useState, useCallback } from "react";
import type { ReactNode } from "react";
import type { ReviewUpdate } from "@/types";

type SSEStatus = "connecting" | "connected" | "disconnected";

interface SSEContextValue {
  status: SSEStatus;
  subscribe: (onMessage: (update: ReviewUpdate) => void) => () => void;
}

const SSEContext = createContext<SSEContextValue | null>(null);

export function SSEProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<SSEStatus>("disconnected");
  const subscribersRef = useRef<Set<(update: ReviewUpdate) => void>>(new Set());
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || "";
    const url = `${baseUrl}/reviews/stream`;

    setStatus("connecting");
    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => {
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
      setStatus("disconnected");
    };

    return () => {
      es.close();
      esRef.current = null;
    };
  }, []);

  const subscribe = useCallback((onMessage: (update: ReviewUpdate) => void) => {
    subscribersRef.current.add(onMessage);
    return () => {
      subscribersRef.current.delete(onMessage);
    };
  }, []);

  return (
    <SSEContext.Provider value={{ status, subscribe }}>
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
