"use client";

import { useEffect } from "react";
import { logEnvIssues } from "@/lib/env-check";

export function EnvCheck() {
  useEffect(() => {
    logEnvIssues();
  }, []);
  return null;
}
