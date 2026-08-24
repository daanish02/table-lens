"use client";

import { useEffect, useState } from "react";

const QUERY = "(max-width: 768px)";

// SSR-safe lazy initializer (same pattern as TableDetail.tsx's
// readThemeColors) — reads the real viewport width synchronously on first
// client render instead of assuming desktop and correcting after mount,
// which would otherwise flash the wrong layout for a phone visitor.
function matches(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia(QUERY).matches;
}

/** True when the viewport is at or below the single breakpoint this app
 * uses to switch from the desktop split-panel layout to a stacked one. */
export function useIsNarrow(): boolean {
  const [narrow, setNarrow] = useState(matches);

  useEffect(() => {
    const mql = window.matchMedia(QUERY);
    const onChange = () => setNarrow(mql.matches);
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, []);

  return narrow;
}
