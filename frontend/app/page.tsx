import Link from "next/link";

export default function HomePage() {
  return (
    <main style={styles.page}>
      <h1 style={styles.title}>Table Lens</h1>
      <p style={styles.lead}>
        An AI-native conversational BI tool. Ask questions about your data in plain English —
        an agent discovers your schema, understands what it means, and answers by querying it directly.
      </p>

      <div style={styles.sections}>
        <Link href="/data" style={styles.card}>
          <div style={styles.cardTitle}>Data →</div>
          <div style={styles.cardDesc}>
            Browse discovered tables and columns, run schema discovery, inspect stats and
            distributions, view raw rows.
          </div>
        </Link>

        <Link href="/ask" style={styles.card}>
          <div style={styles.cardTitle}>Ask →</div>
          <div style={styles.cardDesc}>
            Ask questions in plain English, get validated SQL, paginated results, and a
            plain-English summary.
          </div>
        </Link>
      </div>
    </main>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    maxWidth: 720,
    margin: "0 auto",
    padding: "64px 24px",
  },
  title: {
    fontSize: 28,
    fontWeight: 600,
    letterSpacing: "-0.02em",
    margin: 0,
  },
  lead: {
    fontSize: 14,
    color: "var(--text-dim)",
    lineHeight: 1.6,
    marginTop: 16,
    maxWidth: 520,
  },
  sections: {
    display: "flex",
    flexDirection: "column",
    gap: 12,
    marginTop: 40,
  },
  card: {
    display: "block",
    border: "1px solid var(--border)",
    borderRadius: 2,
    padding: "18px 20px",
    textDecoration: "none",
    color: "var(--text)",
    background: "var(--bg)",
  },
  cardTitle: {
    fontSize: 14,
    color: "var(--accent)",
    marginBottom: 6,
  },
  cardDesc: {
    fontSize: 12,
    color: "var(--text-dim)",
    lineHeight: 1.5,
  },
};
