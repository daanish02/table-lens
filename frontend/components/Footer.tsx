"use client";

import { AUTHOR_HANDLE, AUTHOR_GITHUB_URL, getAuthorEmail } from "../lib/site";

/** Sitewide footer — author credit + a contact link that builds its
 * mailto: address client-side (see the onClick below). */
export default function Footer() {
  return (
    <footer style={styles.footer}>
      <span>
        Built by{" "}
        <a href={AUTHOR_GITHUB_URL} target="_blank" rel="noopener noreferrer" className="footer-link" style={styles.link}>
          @{AUTHOR_HANDLE}
        </a>
      </span>
      <a
        href="#"
        className="footer-link"
        style={styles.link}
        onClick={(e) => {
          // Address is built and navigated to in one step, client-side
          // only — the real mailto: string never sits in the DOM/HTML for
          // scrapers to harvest, only "#" ever appears as the href.
          e.preventDefault();
          window.location.href = `mailto:${getAuthorEmail()}`;
        }}
      >
        contact me here
      </a>
    </footer>
  );
}

const styles: Record<string, React.CSSProperties> = {
  footer: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    flexWrap: "wrap",
    rowGap: 4,
    padding: "14px 24px",
    borderTop: "1px solid var(--border)",
    background: "var(--bg)",
    fontSize: 12.5,
    color: "var(--text-faint)",
  },
  link: {
    color: "var(--text-faint)",
    textDecoration: "none",
  },
};
