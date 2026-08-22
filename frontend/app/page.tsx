import Link from "next/link";

export default function HomePage() {
  return (
    <main style={styles.page}>
      <h1 style={styles.title}>Table Lens</h1>
      <p style={styles.lead}>
        An AI-native conversational BI tool. Ask questions about your data in
        plain English — an agent discovers your schema, understands what it
        means, and answers by querying it directly.
      </p>

      <hr style={styles.rule} />

      <p style={styles.about}>
        The database behind this instance is a property &amp; casualty insurance
        book — customers, policies, agents, claims, underwriting, fraud flags,
        call-center interactions, and audit trails — modeling how a mid-size
        insurer&apos;s data actually looks spread across departments, not one
        tidy spreadsheet.
      </p>

      <p style={styles.about}>
        It&apos;s messy, the way real operational data is: 50 tables, 2,215
        columns, and over 5 million rows, ranging from small lookup tables to a
        500,000-row audit log. Column types and null rates vary wildly table to
        table, denormalized monthly snapshots sit next to raw transactional
        logs, timestamps are stored without timezone, some tables run 15+
        columns wide, and a few ambiguous table names as well. This is
        the kind of database Table Lens actually has to reason about — not one
        built to make discovery look easy.
      </p>

      <hr style={styles.rule} />

      <div style={styles.sections}>
        <Link href="/data" style={styles.card}>
          <div style={styles.cardTitle}>Data →</div>
          <div style={styles.cardDesc}>
            Browse discovered tables and columns, run schema discovery, inspect
            stats and distributions, view raw rows.
          </div>
        </Link>

        <Link href="/ask" style={styles.card}>
          <div style={styles.cardTitle}>Ask →</div>
          <div style={styles.cardDesc}>
            Ask questions in plain English, get validated SQL, paginated
            results, and a plain-English summary.
          </div>
        </Link>

        <Link href="/visualize" style={styles.card}>
          <div style={styles.cardTitle}>Visualize →</div>
          <div style={styles.cardDesc}>
            Describe the chart you want, get an auto-picked visualization, one
            at a time or built up into a saved dashboard.
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
    fontSize: 15.5,
    color: "var(--text-dim)",
    lineHeight: 1.6,
    marginTop: 16,
    maxWidth: 520,
  },
  rule: {
    border: "none",
    borderTop: "1px solid var(--border)",
    margin: "28px 0",
  },
  about: {
    fontSize: 14.5,
    color: "var(--text-dim)",
    lineHeight: 1.65,
    margin: "16px 0",
  },
  sections: {
    display: "flex",
    flexDirection: "column",
    gap: 12,
    marginTop: 8,
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
    fontSize: 15.5,
    color: "var(--accent)",
    marginBottom: 6,
  },
  cardDesc: {
    fontSize: 13.5,
    color: "var(--text-dim)",
    lineHeight: 1.5,
  },
};
