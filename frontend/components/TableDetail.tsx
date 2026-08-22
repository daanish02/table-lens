"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiClient } from "../lib/api-client";
import { logger } from "../lib/logger";
import { formatCount, formatCell } from "../lib/format";
import { Skeleton, SkeletonCard } from "./Skeleton";
import EChart from "./EChart";

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

type TableMeta = {
  table_name: string;
  description: string;
  row_count: number | null;
  column_count: number | null;
};

const PAGE_SIZE = 50;

export default function TableDetail({ table }: { table: string }) {
  const [page, setPage] = useState(1);
  const [data, setData] = useState<BrowseResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [columns, setColumns] = useState<ColumnResult[] | null>(null);
  const [columnsLoading, setColumnsLoading] = useState(true);
  const [meta, setMeta] = useState<TableMeta | null>(null);

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
      .get<{ table: TableMeta | null; columns: ColumnResult[] }>(`/api/discover/results/${table}`)
      .then((r) => {
        setColumns(r.columns);
        setMeta(r.table);
      })
      .catch((err) => logger.error("failed to load column info", err))
      .finally(() => setColumnsLoading(false));
  }, [table]);

  const totalPages = data ? Math.max(1, Math.ceil(data.total_rows / data.page_size)) : 1;

  return (
    <main style={styles.page}>
      <Link href="/data" style={styles.backLink}>← back to data overview</Link>
      <h1 style={styles.title}>{table}</h1>

      {columnsLoading && (
        <div style={{ marginTop: 8, marginBottom: 20 }}>
          <Skeleton width={420} height={13} />
          <div style={{ marginTop: 8 }}>
            <Skeleton width={160} height={11} />
          </div>
        </div>
      )}

      {!columnsLoading && meta && (
        <div style={styles.tableMeta}>
          {meta.description && <div style={styles.tableMetaDesc}>{meta.description}</div>}
          <div style={styles.tableMetaStats}>
            {meta.row_count != null && <span>{formatCount(meta.row_count)} rows</span>}
            {meta.column_count != null && <span>{formatCount(meta.column_count)} columns</span>}
          </div>
        </div>
      )}

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
            {data.total_rows.toLocaleString("en-US")} rows · page {data.page} of {totalPages}
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

      {hasHistogram && (
        <ProfileBarChart
          labels={profile!.histogram.map(([edge]) => formatAxisNumber(edge))}
          counts={profile!.histogram.map(([, c]) => c)}
        />
      )}
      {hasTopValues && (
        <ProfileBarChart
          labels={profile!.top_values.map(([v]) => String(v))}
          counts={profile!.top_values.map(([, c]) => c)}
        />
      )}

      {profile && (
        <div style={styles.statGrid}>
          <StatBlock label="null" value={`${(profile.null_rate * 100).toFixed(1)}%`} />
          <StatBlock label="distinct" value={formatCount(profile.distinct_count)} />
          {profile.mean_value != null && <StatBlock label="mean" value={profile.mean_value.toFixed(2)} />}
          {profile.p50 != null && <StatBlock label="p50" value={String(profile.p50)} />}
          {profile.p95 != null && <StatBlock label="p95" value={String(profile.p95)} />}
          {profile.min_value != null && <StatBlock label="min" value={String(profile.min_value)} />}
          {profile.max_value != null && <StatBlock label="max" value={String(profile.max_value)} />}
        </div>
      )}
    </div>
  );
}

function StatBlock({ label, value }: { label: string; value: string }) {
  return (
    <div style={styles.statBlock}>
      <div style={styles.statBlockValue}>{value}</div>
      <div style={styles.statBlockLabel}>{label}</div>
    </div>
  );
}

function formatAxisNumber(n: number): string {
  const abs = Math.abs(n);
  if (abs >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  if (Number.isInteger(n)) return String(n);
  return n.toFixed(2);
}

function useThemeColors() {
  const [colors, setColors] = useState({ accent: "#0d9488", text: "#52525b", grid: "#d4d4d9" });
  useEffect(() => {
    const style = getComputedStyle(document.documentElement);
    setColors({
      accent: style.getPropertyValue("--accent").trim() || "#0d9488",
      text: style.getPropertyValue("--text-dim").trim() || "#52525b",
      grid: style.getPropertyValue("--border").trim() || "#d4d4d9",
    });
  }, []);
  return colors;
}

function ProfileBarChart({ labels, counts }: { labels: string[]; counts: number[] }) {
  const { accent, text, grid } = useThemeColors();
  const option = {
    grid: { left: 4, right: 4, top: 8, bottom: 28, containLabel: true },
    tooltip: { trigger: "axis" as const, axisPointer: { type: "shadow" as const } },
    xAxis: {
      type: "category" as const,
      data: labels,
      axisLine: { lineStyle: { color: grid } },
      axisTick: { show: false },
      axisLabel: { color: text, fontSize: 10, interval: 0, rotate: labels.length > 8 ? 45 : 0 },
    },
    yAxis: {
      type: "value" as const,
      axisLine: { show: false },
      axisLabel: { color: text, fontSize: 10 },
      splitLine: { lineStyle: { color: grid } },
    },
    series: [
      {
        type: "bar" as const,
        data: counts,
        itemStyle: { color: accent, opacity: 0.85 },
        barMaxWidth: 28,
      },
    ],
  };
  return <EChart option={option} height={150} />;
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
  tableMeta: {
    marginTop: 8,
    marginBottom: 20,
  },
  tableMetaDesc: {
    fontFamily: "var(--sans)",
    fontSize: 14,
    lineHeight: 1.6,
    color: "var(--text-dim)",
  },
  tableMetaStats: {
    display: "flex",
    gap: 14,
    marginTop: 10,
    fontSize: 11,
    letterSpacing: "0.04em",
    textTransform: "uppercase",
    color: "var(--text-faint)",
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
    gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
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
    fontFamily: "var(--sans)",
    fontSize: 12,
    color: "var(--text-dim)",
    marginTop: 4,
    marginBottom: 10,
    lineHeight: 1.55,
  },
  statGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(64px, 1fr))",
    gap: "10px 8px",
    marginTop: 12,
    paddingTop: 10,
    borderTop: "1px solid var(--border)",
  },
  statBlock: {
    display: "flex",
    flexDirection: "column",
    gap: 2,
  },
  statBlockValue: {
    fontFamily: "var(--mono)",
    fontSize: 13,
    color: "var(--text)",
  },
  statBlockLabel: {
    fontSize: 10,
    letterSpacing: "0.05em",
    textTransform: "uppercase",
    color: "var(--text-faint)",
  },
};
