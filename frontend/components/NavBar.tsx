"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import ThemeToggle from "./ThemeToggle";

const LINKS = [
  { href: "/data", label: "data" },
  { href: "/ask", label: "ask" },
  { href: "/visualize", label: "visualize" },
];

/** Sitewide top nav — wordmark, page links (active one highlighted), theme toggle. */
export default function NavBar() {
  const pathname = usePathname();
  return (
    <nav style={styles.nav}>
      <Link href="/" style={styles.wordmark}>Table Lens</Link>
      <div style={styles.right}>
        <div style={styles.links}>
          {LINKS.map((l) => (
            <Link key={l.href} href={l.href} style={{ ...styles.link, ...(pathname?.startsWith(l.href) ? styles.linkActive : {}) }}>
              {l.label}
            </Link>
          ))}
        </div>
        <ThemeToggle />
      </div>
    </nav>
  );
}

const styles: Record<string, React.CSSProperties> = {
  nav: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "18px 24px",
    borderBottom: "1px solid var(--border)",
    background: "var(--bg)",
    position: "relative",
  },
  wordmark: {
    fontSize: 16.5,
    fontWeight: 600,
    letterSpacing: "-0.02em",
    color: "var(--text)",
    textDecoration: "none",
  },
  right: {
    display: "flex",
    alignItems: "center",
    gap: 24,
  },
  links: {
    display: "flex",
    gap: 20,
  },
  link: {
    fontSize: 14.5,
    color: "var(--text-dim)",
    textDecoration: "none",
  },
  linkActive: {
    color: "var(--accent)",
  },
};
