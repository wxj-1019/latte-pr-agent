/**
 * Production-safe logger wrapper.
 * Suppresses console output in production builds to prevent information leakage.
 * TODO: integrate Sentry or similar error tracking service for production.
 */

const isProd = process.env.NODE_ENV === "production";

export const logger = {
  log: (...args: unknown[]): void => {
    if (!isProd) console.log(...args);
  },
  warn: (...args: unknown[]): void => {
    if (!isProd) console.warn(...args);
  },
  error: (...args: unknown[]): void => {
    if (!isProd) console.error(...args);
    // TODO: send to Sentry in production
  },
};
