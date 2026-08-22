"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/data", label: "data" },
  { href: "/ask", label: "ask" },
];

export default function NavBar() {
  const pathname = usePathname();
  return (
    <nav style={styles.nav}>
      <Link href="/" style={styles.wordmark}>Table Lens</Link>
      <div style={styles.links}>
        {LINKS.map((l) => (
          <Link key={l.href} href={l.href} style={{ ...styles.link, ...(pathname?.startsWith(l.href) ? styles.linkActive : {}) }}>
            {l.label}
          </Link>
        ))}
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
    fontSize: 15,
    fontWeight: 600,
    letterSpacing: "-0.02em",
    color: "var(--text)",
    textDecoration: "none",
  },
  links: {
    display: "flex",
    gap: 20,
  },
  link: {
    fontSize: 13,
    color: "var(--text-dim)",
    textDecoration: "none",
  },
  linkActive: {
    color: "var(--accent)",
  },
};
