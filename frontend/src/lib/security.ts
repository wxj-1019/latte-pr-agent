/**
 * HTML entity escape for defense-in-depth content rendering.
 * React JSX already escapes variables by default, but this adds
 * an extra layer of safety for code/content display components.
 */
export function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
