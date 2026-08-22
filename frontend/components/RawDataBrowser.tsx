"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiClient } from "../lib/api-client";
import { logger } from "../lib/logger";

type BrowseResponse = {
  table: string;
  page: number;
  page_size: number;
  total_rows: number;
  columns: string[];
  rows: Record<string, unknown>[];
};

const PAGE_SIZE = 50;

function formatCell(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "boolean") return v ? "true" : "false";
  return String(v);
}

export default function RawDataBrowser({ table }: { table: string }) {
  const [page, setPage] = useState(1);
  const [data, setData] = useState<BrowseResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    setError(null);
    apiClient
      .get<BrowseResponse>(`/api/data/${table}?page=${page}&page_size=${PAGE_SIZE}`)
      .then((r) => setData(r))
      .catch((err) => {
        logger.error("failed to load table rows", err);
        setError(`could not load "${table}" — it may not have been discovered yet`);
      })
      .finally(() => setLoading(false));
  }, [table, page]);

  const totalPages = data ? Math.max(1, Math.ceil(data.total_rows / data.page_size)) : 1;

  return (
    <main style={styles.page}>
      <Link href="/data" style={styles.backLink}>← back to data overview</Link>
      <h1 style={styles.title}>{table}</h1>

      {error && <div style={styles.errorBox}>{error}</div>}
      {loading && !data && <div style={styles.dim}>loading…</div>}

      {data && (
        <>
          <div style={styles.meta}>
            {data.total_rows.toLocaleString()} rows · page {data.page} of {totalPages}
          </div>

          <div style={styles.tableWrap}>
            <table style={styles.table}>
              <thead>
                <tr>
                  {data.columns.map((c) => (
                    <th key={c} style={styles.th}>{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.rows.map((row, i) => (
                  <tr key={i}>
                    {data.columns.map((c) => (
                      <td key={c} style={styles.td}>{formatCell(row[c])}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div style={styles.pager}>
            <button style={styles.pagerButton} disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              ← prev
            </button>
            <span style={styles.dim}>{page} / {totalPages}</span>
            <button style={styles.pagerButton} disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
              next →
            </button>
          </div>
        </>
      )}
    </main>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    maxWidth: 1100,
    margin: "0 auto",
    padding: "48px 24px",
  },
  backLink: {
    fontSize: 12,
    color: "var(--text-dim)",
    textDecoration: "none",
  },
  title: {
    fontSize: 20,
    fontWeight: 600,
    letterSpacing: "-0.02em",
    margin: "12px 0 4px",
  },
  meta: {
    fontSize: 12,
    color: "var(--text-dim)",
    marginBottom: 16,
  },
  dim: {
    color: "var(--text-dim)",
    fontSize: 12,
  },
  errorBox: {
    marginTop: 16,
    border: "1px solid var(--error)",
    background: "var(--error-dim)",
    color: "var(--error)",
    padding: "10px 14px",
    fontSize: 13,
    borderRadius: 2,
  },
  tableWrap: {
    border: "1px solid var(--border)",
    borderRadius: 2,
    overflow: "auto",
    maxWidth: "100%",
    maxHeight: "70vh",
  },
  table: {
    borderCollapse: "collapse",
    fontSize: 12,
    width: "max-content",
  },
  th: {
    position: "sticky",
    top: 0,
    background: "var(--surface)",
    borderBottom: "1px solid var(--border)",
    borderRight: "1px solid var(--border)",
    padding: "8px 10px",
    textAlign: "left",
    color: "var(--text-faint)",
    whiteSpace: "nowrap",
  },
  td: {
    borderBottom: "1px solid var(--border)",
    borderRight: "1px solid var(--border)",
    padding: "6px 10px",
    whiteSpace: "nowrap",
    color: "var(--text)",
  },
  pager: {
    display: "flex",
    alignItems: "center",
    gap: 16,
    marginTop: 16,
  },
  pagerButton: {
    background: "transparent",
    border: "1px solid var(--border)",
    color: "var(--text)",
    padding: "6px 14px",
    fontFamily: "var(--mono)",
    fontSize: 12,
    cursor: "pointer",
    borderRadius: 2,
  },
};
