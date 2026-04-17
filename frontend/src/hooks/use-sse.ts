"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import type { ReviewUpdate } from "@/types";

export function useSSE(onMessage: (update: ReviewUpdate) => void) {
  const [status, setStatus] = useState<"connecting" | "connected" | "disconnected">("disconnected");
  const onMessageRef = useRef(onMessage);

  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  useEffect(() => {
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || "";
    const url = `${baseUrl}/reviews/stream`;

    setStatus("connecting");
    const es = new EventSource(url);

    es.onopen = () => {
      setStatus("connected");
    };

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as ReviewUpdate;
        onMessageRef.current(data);
      } catch {
        // ignore malformed events
      }
    };

    es.onerror = () => {
      setStatus("disconnected");
      // Auto-reconnect is handled by EventSource natively,
      // but we reflect the transient state here.
    };

    return () => {
      es.close();
    };
  }, []);

  return { status };
}
