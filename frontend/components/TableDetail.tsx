"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiClient } from "../lib/api-client";
import { logger } from "../lib/logger";
import { formatCount } from "../lib/format";
import { Skeleton, SkeletonCard } from "./Skeleton";

type BrowseResponse = {
  table: string;
  page: number;
  page_size: number;
  total_rows: number;
  columns: string[];
  rows: Record<string, unknown>[];
};

type ColumnProfile = {
  row_count: number;
  null_rate: number;
  distinct_count: number;
  min_value: unknown;
  max_value: unknown;
  mean_value: number | null;
  p50: number | null;
  p95: number | null;
  top_values: [unknown, number][];
  histogram: [number, number][];
};

type ColumnResult = {
  column_name: string;
  description: string;
  profile: ColumnProfile | null;
};

const PAGE_SIZE = 50;

function formatCell(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "boolean") return v ? "true" : "false";
  return String(v);
}

export default function TableDetail({ table }: { table: string }) {
  const [page, setPage] = useState(1);
  const [data, setData] = useState<BrowseResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [columns, setColumns] = useState<ColumnResult[] | null>(null);
  const [columnsLoading, setColumnsLoading] = useState(true);

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

  useEffect(() => {
    setColumnsLoading(true);
    apiClient
      .get<{ columns: ColumnResult[] }>(`/api/discover/results/${table}`)
      .then((r) => setColumns(r.columns))
      .catch((err) => logger.error("failed to load column info", err))
      .finally(() => setColumnsLoading(false));
  }, [table]);

  const totalPages = data ? Math.max(1, Math.ceil(data.total_rows / data.page_size)) : 1;

  return (
    <main style={styles.page}>
      <Link href="/data" style={styles.backLink}>← back to data overview</Link>
      <h1 style={styles.title}>{table}</h1>

      {error && <div style={styles.errorBox}>{error}</div>}

      {loading && !data && (
        <>
          <div style={{ marginBottom: 16 }}>
            <Skeleton width={180} height={12} />
          </div>
          <div style={styles.tableWrap}>
            <table style={styles.table}>
              <tbody>
                {Array.from({ length: 10 }).map((_, i) => (
                  <tr key={i}>
                    {Array.from({ length: 6 }).map((_, j) => (
                      <td key={j} style={styles.td}>
                        <Skeleton width={70 + ((i + j) % 3) * 20} height={10} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

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

      {columnsLoading && (
        <div style={styles.columnSection}>
          <div style={styles.sectionTitle}>columns</div>
          <div style={styles.columnGrid}>
            {Array.from({ length: 8 }).map((_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
        </div>
      )}

      {!columnsLoading && columns && (
        <div style={styles.columnSection}>
          <div style={styles.sectionTitle}>columns ({columns.length})</div>
          <div style={styles.columnGrid}>
            {columns.map((c) => (
              <ColumnCard key={c.column_name} col={c} />
            ))}
          </div>
        </div>
      )}
    </main>
  );
}

function ColumnCard({ col }: { col: ColumnResult }) {
  const profile = col.profile;
  const hasHistogram = profile && profile.histogram.length > 0;
  const hasTopValues = profile && !hasHistogram && profile.top_values.length > 0;

  return (
    <div style={styles.columnCard}>
      <div style={styles.columnCardName}>{col.column_name}</div>
      {col.description && <div style={styles.columnCardDesc}>{col.description}</div>}

      {hasHistogram && <BarChart data={profile!.histogram} />}
      {hasTopValues && (
        <BarChart
          data={profile!.top_values.map(([, c], i) => [i, c] as [number, number])}
          labels={profile!.top_values.map(([v]) => String(v))}
        />
      )}

      {profile && (
        <div style={styles.columnCardStats}>
          <span>null: {(profile.null_rate * 100).toFixed(1)}%</span>
          <span>distinct: {formatCount(profile.distinct_count)}</span>
          {profile.mean_value != null && <span>mean: {profile.mean_value.toFixed(2)}</span>}
          {profile.p50 != null && <span>p50: {profile.p50}</span>}
          {profile.p95 != null && <span>p95: {profile.p95}</span>}
          {profile.min_value != null && <span>min: {String(profile.min_value)}</span>}
          {profile.max_value != null && <span>max: {String(profile.max_value)}</span>}
        </div>
      )}
    </div>
  );
}

function BarChart({ data, labels }: { data: [number, number][]; labels?: string[] }) {
  const width = 200;
  const height = 48;
  const max = Math.max(...data.map(([, c]) => c), 1);
  const barWidth = width / data.length;
  return (
    <div>
      <svg width={width} height={height} style={{ display: "block" }}>
        {data.map(([bucket, count], i) => {
          const h = (count / max) * height;
          return (
            <rect
              key={bucket}
              x={i * barWidth}
              y={height - h}
              width={Math.max(barWidth - 1, 1)}
              height={h}
              style={{ fill: "var(--accent)", opacity: 0.8 }}
            />
          );
        })}
      </svg>
      {labels && (
        <div style={styles.barLabels}>
          {labels.map((l, i) => (
            <span key={i} style={styles.barLabel}>{l}</span>
          ))}
        </div>
      )}
    </div>
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
    background: "var(--bg)",
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
  columnSection: {
    marginTop: 40,
  },
  sectionTitle: {
    fontSize: 11,
    letterSpacing: "0.08em",
    textTransform: "uppercase",
    color: "var(--text-faint)",
    marginBottom: 12,
  },
  columnGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
    gap: 12,
  },
  columnCard: {
    border: "1px solid var(--border)",
    borderRadius: 2,
    padding: "12px 14px",
    background: "var(--bg)",
  },
  columnCardName: {
    fontSize: 13,
    color: "var(--text)",
  },
  columnCardDesc: {
    fontSize: 11,
    color: "var(--text-dim)",
    marginTop: 4,
    marginBottom: 10,
    lineHeight: 1.4,
  },
  columnCardStats: {
    display: "flex",
    flexWrap: "wrap",
    gap: 8,
    fontSize: 10,
    color: "var(--text-dim)",
    marginTop: 8,
  },
  barLabels: {
    display: "flex",
    justifyContent: "space-between",
    fontSize: 9,
    color: "var(--text-faint)",
    marginTop: 2,
  },
  barLabel: {
    maxWidth: 24,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
};
