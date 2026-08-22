"use client";

import { useEffect, useState } from "react";
import { getCurrentTheme, type Theme } from "../lib/theme";

const STORAGE_KEY = "table-lens-theme";

export default function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("dark");

  useEffect(() => {
    setTheme(getCurrentTheme());
  }, []);

  function toggle() {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    if (next === "light") {
      document.documentElement.setAttribute("data-theme", "light");
    } else {
      document.documentElement.removeAttribute("data-theme");
    }
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // localStorage can throw (private browsing, blocked storage) — the
      // toggle still works for this page load, it just won't persist.
    }
  }

  return (
    <button onClick={toggle} style={styles.toggle} aria-label="toggle color theme">
      {theme === "light" ? "dark" : "light"}
    </button>
  );
}

const styles: Record<string, React.CSSProperties> = {
  toggle: {
    background: "transparent",
    border: "1px solid var(--border)",
    color: "var(--text-dim)",
    padding: "4px 10px",
    fontFamily: "var(--mono)",
    fontSize: 11,
    cursor: "pointer",
    borderRadius: 2,
  },
};
