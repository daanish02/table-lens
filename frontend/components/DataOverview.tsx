"use client";

/** /data landing page: schema-wide stats, a "run discovery" trigger with
 * live progress polling, and the grid of discovered tables. */

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { apiClient, ApiError } from "../lib/api-client";
import { logger } from "../lib/logger";
import { formatCount, formatDateTime } from "../lib/format";
import { Skeleton, SkeletonCard } from "./Skeleton";
import ConfirmDialog from "./ConfirmDialog";

type DiscoverStatus = {
  run_id: string;
  status: "pending" | "running" | "done" | "failed";
  step: string | null;
  error: string | null;
  total_tables: number | null;
  tables_done: number | null;
};

type OverviewStats = {
  table_count: number;
  column_count: number;
  row_count: number;
};

type LastRun = {
  run_id: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  total_tables: number | null;
  tables_done: number | null;
} | null;

type OverviewResponse = {
  stats: OverviewStats;
  last_run: LastRun;
};

type TableResult = {
  table_name: string;
  description: string;
  row_count: number | null;
  column_count: number | null;
};

type LogEntry = {
  step: string;
  at: number; // ms since epoch, for duration math
  display: string; // localized time string, for rendering
};

type TableCompletion = {
  table: string;
  columns: number;
  durationMs: number;
};

// A backend restart loses in-memory run state (or the run_id becomes
// otherwise unreachable) — without a ceiling, the status poll below would
// retry every 1500ms forever with nothing ever telling the user it's stuck.
const MAX_STATUS_POLL_FAILURES = 5;

const PHASES = ["profiling", "describing", "embedding", "table_done"] as const;

function phaseOf(step: string): (typeof PHASES)[number] | "other" {
  const prefix = step.split(":")[0];
  return (PHASES as readonly string[]).includes(prefix) ? (prefix as (typeof PHASES)[number]) : "other";
}

function formatDuration(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

export default function DataOverview() {
  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [status, setStatus] = useState<DiscoverStatus | null>(null);
  const [log, setLog] = useState<LogEntry[]>([]);
  const [starting, setStarting] = useState(false);
  const [results, setResults] = useState<TableResult[] | null>(null);
  const [resultsLoading, setResultsLoading] = useState(true);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [overviewError, setOverviewError] = useState(false);
  const [resultsError, setResultsError] = useState(false);
  const [statusLost, setStatusLost] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const [overviewReloadKey, setOverviewReloadKey] = useState(0);
  const [resultsReloadKey, setResultsReloadKey] = useState(0);
  const lastStep = useRef<string | null>(null);
  const startTimeRef = useRef<number | null>(null);
  const lastCompletionRef = useRef<number | null>(null);
  const statusPollFailures = useRef(0);

  const isRunning = status?.status === "running" || status?.status === "pending";

  function loadOverview() {
    setOverviewError(false);
    apiClient
      .get<OverviewResponse>("/api/discover/overview")
      .then(setOverview)
      .catch((err) => {
        logger.error("failed to load overview", err);
        setOverviewError(true);
      });
  }

  useEffect(loadOverview, [overviewReloadKey]);

  function loadResults() {
    setResultsError(false);
    setResultsLoading(true);
    apiClient
      .get<{ tables: TableResult[] }>("/api/discover/results")
      .then((r) => setResults(r.tables))
      .catch((err) => {
        // /api/discover/results always returns 200 (empty tables array when
        // no run has completed yet) — it never 404s, so any exception here
        // is a genuine failure (network/server), not a legitimate empty state.
        logger.error("failed to load discovered tables", err);
        setResultsError(true);
      })
      .finally(() => setResultsLoading(false));
  }

  useEffect(loadResults, [resultsReloadKey]);

  useEffect(() => {
    if (!runId || !status || status.status === "done" || status.status === "failed") return;
    if (statusLost) return;

    const interval = setInterval(async () => {
      try {
        const next = await apiClient.get<DiscoverStatus>(`/api/discover/status/${runId}`);
        statusPollFailures.current = 0;
        setStatus(next);
        if (next.step && next.step !== lastStep.current) {
          lastStep.current = next.step;
          const now = Date.now();
          setLog((prev) => [...prev, { step: next.step as string, at: now, display: new Date(now).toLocaleTimeString() }]);
        }
      } catch (err) {
        logger.error("status poll failed", err);
        statusPollFailures.current += 1;
        if (statusPollFailures.current >= MAX_STATUS_POLL_FAILURES) {
          setStatusLost(true);
        }
      }
    }, 1500);

    return () => clearInterval(interval);
  }, [runId, status]);

  // Ticking elapsed-time clock while a run is in flight.
  useEffect(() => {
    if (!isRunning || startTimeRef.current === null) return;
    const tick = setInterval(() => setElapsedMs(Date.now() - (startTimeRef.current as number)), 1000);
    return () => clearInterval(tick);
  }, [isRunning]);

  useEffect(() => {
    if (status?.status === "done") {
      apiClient.get<{ tables: TableResult[] }>("/api/discover/results").then((r) => setResults(r.tables));
      apiClient.get<OverviewResponse>("/api/discover/overview").then(setOverview);
    }
  }, [status?.status]);

  async function handleRun() {
    setStarting(true);
    setResults(null);
    setLog([]);
    lastStep.current = null;
    startTimeRef.current = Date.now();
    lastCompletionRef.current = Date.now();
    setElapsedMs(0);
    statusPollFailures.current = 0;
    setStatusLost(false);
    setStartError(null);
    try {
      const res = await apiClient.post<{ run_id: string }>("/api/discover", {});
      setRunId(res.run_id);
      setStatus({ run_id: res.run_id, status: "running", step: "started", error: null, total_tables: null, tables_done: null });
    } catch (err) {
      logger.error("failed to start discovery", err);
      if (err instanceof ApiError && err.status === 409) {
        setStartError("A discovery run is already in progress (started elsewhere, or a previous one is still finishing) — try again in a bit.");
      } else if (err instanceof ApiError && err.status === 429) {
        setStartError("Discovery can only be triggered a few times per hour — try again later.");
      } else {
        setStartError("Couldn't start discovery — check your connection and try again.");
      }
    } finally {
      setStarting(false);
    }
  }

  // table_done:<name>:<col_count> entries, paired with the time since the
  // previous completion, for the per-table duration shown in the log.
  const completions: TableCompletion[] = [];
  {
    let prevAt = startTimeRef.current ?? 0;
    for (const entry of log) {
      if (phaseOf(entry.step) === "table_done") {
        const [, table, colsStr] = entry.step.split(":");
        completions.push({ table, columns: Number(colsStr), durationMs: entry.at - prevAt });
        prevAt = entry.at;
      }
    }
  }

  const totalTables = status?.total_tables ?? null;
  const tablesDone = status?.tables_done ?? null;
  const pct = totalTables && tablesDone !== null ? Math.round((tablesDone / totalTables) * 100) : null;

  const avgPaceMs = completions.length > 0 ? completions.reduce((a, c) => a + c.durationMs, 0) / completions.length : null;
  const remaining = totalTables !== null && tablesDone !== null ? totalTables - tablesDone : null;
  const etaMs = avgPaceMs !== null && remaining !== null ? avgPaceMs * remaining : null;

  const profilingSteps = log.filter((e) => phaseOf(e.step) === "profiling");
  const profilingDone = status ? phaseOf(status.step ?? "") !== "profiling" && log.some((e) => e.step === "inferring_relationships" || phaseOf(e.step) !== "profiling" && phaseOf(e.step) !== "other") : false;

  return (
    <main style={styles.page}>
      <div style={styles.header}>
        <span style={styles.subtitle}>data overview</span>
      </div>

      <div style={styles.statsHeader}>
        {overviewError ? (
          <div style={styles.inlineError}>
            couldn't load overview stats
            <button style={styles.retryButton} onClick={() => setOverviewReloadKey((k) => k + 1)}>retry</button>
          </div>
        ) : overview ? (
          <>
            <StatCell label="tables" value={formatCount(overview.stats.table_count)} />
            <StatCell label="columns" value={formatCount(overview.stats.column_count)} />
            <StatCell label="rows" value={formatCount(overview.stats.row_count)} />
            <StatCell
              label="last run"
              value={
                overview.last_run
                  ? overview.last_run.status === "done"
                    ? overview.last_run.finished_at
                      ? formatDateTime(overview.last_run.finished_at)
                      : "done"
                    : `${overview.last_run.status}${overview.last_run.finished_at ? " · " + formatDateTime(overview.last_run.finished_at) : ""}`
                  : "never"
              }
            />
          </>
        ) : (
          [0, 1, 2, 3].map((i) => (
            <div key={i} style={styles.statCell}>
              <Skeleton width={i === 3 ? 130 : 50} height={16} />
              <div style={{ marginTop: 4 }}>
                <Skeleton width={60} height={10} />
              </div>
            </div>
          ))
        )}
      </div>

      {statusLost && (
        <div style={styles.errorBox}>
          Lost track of this discovery run — the backend may have restarted. It may still be running server-side; refresh to check the latest status.
        </div>
      )}

      {startError && <div style={styles.errorBox}>{startError}</div>}

      <button
        onClick={() => setConfirmOpen(true)}
        disabled={starting || isRunning}
        style={{
          ...styles.button,
          ...(starting || isRunning ? styles.buttonDisabled : {}),
        }}
      >
        {isRunning ? "running…" : starting ? "starting…" : "run discovery"}
      </button>

      <ConfirmDialog
        open={confirmOpen}
        title="Run discovery?"
        message="This scans the whole database and can take a while for large schemas. Only tables/columns that actually changed since the last run cost anything, but a first run or a big schema change can still take several minutes."
        confirmLabel="run discovery"
        onCancel={() => setConfirmOpen(false)}
        onConfirm={() => {
          setConfirmOpen(false);
          handleRun();
        }}
      />

      {status && (
        <div style={styles.statusRow}>
          <StatusBadge status={status.status} />
          <span style={styles.dim}>run_id: {status.run_id}</span>
        </div>
      )}

      {status?.error && <div style={styles.errorBox}>{status.error}</div>}

      {totalTables !== null && tablesDone !== null && (
        <div style={styles.progressBlock}>
          <div style={styles.progressBarTrack}>
            <div style={{ ...styles.progressBarFill, width: `${pct}%` }} />
          </div>
          <div style={styles.progressMeta}>
            <span>{pct}%</span>
            <span>{tablesDone} / {totalTables} tables</span>
          </div>
          <div style={styles.progressMeta}>
            <span>elapsed: {formatDuration(elapsedMs)}</span>
            {isRunning && etaMs !== null && <span>est. remaining: ~{formatDuration(etaMs)}</span>}
            {isRunning && avgPaceMs !== null && <span>avg pace: ~{Math.round(avgPaceMs / 1000)}s/table</span>}
          </div>
        </div>
      )}

      {log.length > 0 && (
        <div style={styles.panel}>
          <div style={styles.panelTitle}>
            profiling {profilingDone ? "— done" : `— ${profilingSteps.length} tables`}
          </div>
          <div style={styles.panelTitle}>describing + embedding</div>
          <div style={styles.logBox}>
            {completions.map((c, i) => (
              <div key={i} style={styles.logLine}>
                <span style={styles.accentText}>✓</span> {c.table}
                <span style={styles.dim}> — {c.columns} cols, {(c.durationMs / 1000).toFixed(1)}s</span>
              </div>
            ))}
            {status?.step && phaseOf(status.step) !== "table_done" && isRunning && (
              <div style={styles.logLine}>
                <span style={styles.dim}>⋯</span> {status.step}
              </div>
            )}
          </div>
        </div>
      )}

      {resultsLoading && (
        <div style={styles.tableGridSection}>
          <div style={styles.sectionTitle}>discovered tables</div>
          <div style={styles.tableGrid}>
            {Array.from({ length: 6 }).map((_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
        </div>
      )}

      {!resultsLoading && resultsError && (
        <div style={styles.tableGridSection}>
          <div style={styles.inlineError}>
            couldn't load discovered tables
            <button style={styles.retryButton} onClick={() => setResultsReloadKey((k) => k + 1)}>retry</button>
          </div>
        </div>
      )}

      {!resultsLoading && !resultsError && results && (
        <div style={styles.tableGridSection}>
          <div style={styles.sectionTitle}>discovered tables ({results.length})</div>
          <div style={styles.tableGrid}>
            {results.map((t) => (
              <Link key={t.table_name} href={`/data/browse/${t.table_name}`} style={styles.tableCard}>
                <div style={styles.tableCardName}>{t.table_name}</div>
                <div style={styles.tableCardMeta}>
                  {formatCount(t.row_count)} rows · {formatCount(t.column_count)} cols
                </div>
                <div style={styles.tableCardDesc}>{t.description}</div>
              </Link>
            ))}
          </div>
        </div>
      )}
    </main>
  );
}

function StatCell({ label, value }: { label: string; value: string }) {
  return (
    <div style={styles.statCell}>
      <div style={styles.statValue}>{value}</div>
      <div style={styles.statLabel}>{label}</div>
    </div>
  );
}

function StatusBadge({ status }: { status: DiscoverStatus["status"] }) {
  const color =
    status === "done" ? "var(--accent)" : status === "failed" ? "var(--error)" : "var(--text-dim)";
  return (
    <span style={{ ...styles.badge, color, borderColor: color }}>{status}</span>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    maxWidth: 960,
    margin: "0 auto",
    padding: "64px 24px",
  },
  header: {
    display: "flex",
    alignItems: "baseline",
    gap: 12,
    marginBottom: 24,
  },
  subtitle: {
    fontSize: 13,
    color: "var(--text-dim)",
  },
  statsHeader: {
    display: "flex",
    flexWrap: "wrap",
    gap: 24,
    border: "1px solid var(--border)",
    borderRadius: 2,
    padding: "16px 20px",
    marginBottom: 24,
    background: "var(--bg)",
  },
  statCell: {
    display: "flex",
    flexDirection: "column",
    gap: 2,
  },
  statValue: {
    fontSize: 16,
    color: "var(--text)",
  },
  statLabel: {
    fontSize: 11,
    letterSpacing: "0.06em",
    textTransform: "uppercase",
    color: "var(--text-faint)",
  },
  button: {
    background: "transparent",
    border: "1px solid var(--accent)",
    color: "var(--accent)",
    padding: "10px 20px",
    fontFamily: "var(--mono)",
    fontSize: 13,
    letterSpacing: "0.02em",
    cursor: "pointer",
    borderRadius: 2,
  },
  buttonDisabled: {
    opacity: 0.5,
    cursor: "default",
  },
  statusRow: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    marginTop: 20,
    fontSize: 13,
  },
  badge: {
    border: "1px solid",
    padding: "2px 8px",
    borderRadius: 2,
    fontSize: 12,
    letterSpacing: "0.04em",
    textTransform: "uppercase",
  },
  dim: {
    color: "var(--text-dim)",
    fontSize: 12,
  },
  accentText: {
    color: "var(--accent)",
  },
  errorBox: {
    marginTop: 16,
    border: "1px solid var(--error)",
    // Opaque equivalent of --error-dim (a translucent rgba by design) —
    // see AskView.tsx's bubbleUser for why alpha backgrounds are a problem now.
    background: "color-mix(in srgb, var(--error) 12%, var(--bg))",
    color: "var(--error)",
    padding: "10px 14px",
    fontSize: 13,
    borderRadius: 2,
  },
  inlineError: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    color: "var(--error)",
    fontSize: 13,
  },
  retryButton: {
    background: "transparent",
    border: "1px solid var(--error)",
    color: "var(--error)",
    padding: "4px 10px",
    fontFamily: "var(--mono)",
    fontSize: 12,
    cursor: "pointer",
    borderRadius: 2,
  },
  progressBlock: {
    marginTop: 20,
  },
  progressBarTrack: {
    height: 6,
    background: "var(--surface)",
    border: "1px solid var(--border)",
    borderRadius: 2,
    overflow: "hidden",
  },
  progressBarFill: {
    height: "100%",
    background: "var(--accent)",
  },
  progressMeta: {
    display: "flex",
    justifyContent: "space-between",
    fontSize: 12,
    color: "var(--text-dim)",
    marginTop: 6,
  },
  panel: {
    marginTop: 32,
    border: "1px solid var(--border)",
    borderRadius: 2,
    background: "var(--bg)",
  },
  panelTitle: {
    fontSize: 11,
    letterSpacing: "0.08em",
    textTransform: "uppercase",
    color: "var(--text-faint)",
    padding: "12px 16px",
    borderBottom: "1px solid var(--border)",
  },
  logBox: {
    padding: "8px 16px 14px",
    maxHeight: 320,
    overflowY: "auto",
  },
  logLine: {
    fontSize: 12,
    padding: "3px 0",
    color: "var(--text)",
  },
  tableGridSection: {
    marginTop: 32,
  },
  sectionTitle: {
    fontSize: 11,
    letterSpacing: "0.08em",
    textTransform: "uppercase",
    color: "var(--text-faint)",
    marginBottom: 12,
  },
  tableGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(min(280px, 100%), 1fr))",
    gap: 12,
  },
  tableCard: {
    display: "block",
    border: "1px solid var(--border)",
    borderRadius: 2,
    padding: "14px 16px",
    textDecoration: "none",
    color: "var(--text)",
    background: "var(--surface)",
  },
  tableCardName: {
    fontSize: 16,
    fontWeight: 600,
    color: "var(--accent)",
  },
  tableCardMeta: {
    fontSize: 11,
    color: "var(--text-faint)",
    marginTop: 4,
  },
  tableCardDesc: {
    fontFamily: "var(--sans)",
    fontSize: 13,
    color: "var(--text)",
    marginTop: 8,
    lineHeight: 1.6,
    display: "-webkit-box",
    WebkitLineClamp: 3,
    WebkitBoxOrient: "vertical",
    overflow: "hidden",
  },
};
