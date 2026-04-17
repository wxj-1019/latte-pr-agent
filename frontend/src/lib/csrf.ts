/**
 * CSRF token management for frontend API requests.
 * Generates a per-session token stored in sessionStorage.
 */

const CSRF_TOKEN_KEY = "latte_csrf_token";

function generateToken(): string {
  const array = new Uint8Array(32);
  if (typeof window !== "undefined" && window.crypto) {
    window.crypto.getRandomValues(array);
  }
  return Array.from(array)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

export function getCsrfToken(): string {
  if (typeof window === "undefined") return "";
  let token = sessionStorage.getItem(CSRF_TOKEN_KEY);
  if (!token) {
    token = generateToken();
    sessionStorage.setItem(CSRF_TOKEN_KEY, token);
  }
  return token;
}

export function clearCsrfToken(): void {
  if (typeof window !== "undefined") {
    sessionStorage.removeItem(CSRF_TOKEN_KEY);
  }
}

export function csrfHeaders(): Record<string, string> {
  const token = getCsrfToken();
  return token ? { "X-CSRF-Token": token } : {};
}
