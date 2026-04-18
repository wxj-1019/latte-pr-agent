/**
 * Runtime environment variable validation.
 * Checks that required variables are present in the browser or build environment.
 */

import { logger } from "./logger";

const REQUIRED_BROWSER_ENV: string[] = [];

const OPTIONAL_BROWSER_ENV = ["NEXT_PUBLIC_API_URL"];

export function validateEnv(): { valid: boolean; errors: string[]; warnings: string[] } {
  const errors: string[] = [];
  const warnings: string[] = [];

  if (typeof window === "undefined") {
    // Server-side build-time checks can be stricter
    return { valid: true, errors, warnings };
  }

  for (const key of REQUIRED_BROWSER_ENV) {
    if (!process.env[key]) {
      errors.push(`缺少必需的环境变量: ${key}`);
    }
  }

  for (const key of OPTIONAL_BROWSER_ENV) {
    if (!process.env[key]) {
      warnings.push(`缺少可选的环境变量: ${key}`);
    }
  }

  return {
    valid: errors.length === 0,
    errors,
    warnings,
  };
}

export function logEnvIssues(): void {
  const { valid, errors, warnings } = validateEnv();
  if (!valid) {
    logger.error("[Latte PR Agent] Environment validation failed:", errors);
  }
  if (warnings.length > 0) {
    logger.warn("[Latte PR Agent] Environment validation warnings:", warnings);
  }
}
