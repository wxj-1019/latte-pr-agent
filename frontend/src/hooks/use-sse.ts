"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import type { ReviewUpdate } from "@/types";

export function useSSE(onMessage: (update: ReviewUpdate) => void) {
  const [status, setStatus] = useState<"connecting" | "connected" | "disconnected">("connecting");
  const esRef = useRef<EventSource | null>(null);
  const retryCountRef = useRef(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const connect = useCallback(() => {
    if (esRef.current) return;

    setStatus("connecting");
    const es = new EventSource("/api/sse/reviews");
    esRef.current = es;

    es.onopen = () => {
      setStatus("connected");
      retryCountRef.current = 0;
    };

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data) as ReviewUpdate;
        onMessage(data);
      } catch {
        // ignore malformed data
      }
    };

    es.onerror = () => {
      es.close();
      esRef.current = null;
      setStatus("disconnected");

      if (retryCountRef.current < 10) {
        const delay = Math.min(1000 * Math.pow(1.5, retryCountRef.current), 10000);
        retryCountRef.current += 1;
        timerRef.current = setTimeout(() => {
          connect();
        }, delay);
      }
    };
  }, [onMessage]);

  useEffect(() => {
    connect();
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
    };
  }, [connect]);

  return { status };
}
