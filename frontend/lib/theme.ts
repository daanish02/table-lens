/** Reads the active light/dark theme from the DOM (see globals.css /
 * layout.tsx's no-flash script — dark is the default, light is the
 * explicit [data-theme="light"] opt-in). */

export type Theme = "light" | "dark";

/** Current theme, synchronously — safe to call during SSR (returns "dark"
 * server-side, since there's no DOM to read yet). */
export function getCurrentTheme(): Theme {
  if (typeof document === "undefined") return "dark";
  return document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
}
