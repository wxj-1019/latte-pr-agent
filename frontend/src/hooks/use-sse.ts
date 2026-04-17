"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import type { ReviewUpdate } from "@/types";

export function useSSE(_onMessage: (update: ReviewUpdate) => void) {
  const [status, setStatus] = useState<"connecting" | "connected" | "disconnected">("disconnected");

  useEffect(() => {
    // SSE is currently disabled until backend implements the endpoint
    setStatus("disconnected");
  }, []);

  return { status };
}
