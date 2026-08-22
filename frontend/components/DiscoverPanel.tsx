"use client";

import { useEffect, useRef, useState } from "react";
import { apiClient } from "../lib/api-client";
import { logger } from "../lib/logger";

type DiscoverStatus = {
  run_id: string;
  status: "pending" | "running" | "done" | "failed";
  step: string | null;
  error: string | null;
  total_tables: number | null;
  tables_done: number | null;
};

type TableResult = {
  table_name: string;
  description: string;
};

type ColumnResult = {
  column_name: string;
  description: string;
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

export default function DiscoverPanel() {
  const [runId, setRunId] = useState<string | null>(null);
  const [status, setStatus] = useState<DiscoverStatus | null>(null);
  const [log, setLog] = useState<LogEntry[]>([]);
  const [starting, setStarting] = useState(false);
  const [results, setResults] = useState<TableResult[] | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [columns, setColumns] = useState<ColumnResult[] | null>(null);
  const [elapsedMs, setElapsedMs] = useState(0);
  const lastStep = useRef<string | null>(null);
  const startTimeRef = useRef<number | null>(null);
  const lastCompletionRef = useRef<number | null>(null);

  const isRunning = status?.status === "running" || status?.status === "pending";

  useEffect(() => {
    if (!runId || !status || status.status === "done" || status.status === "failed") return;

    const interval = setInterval(async () => {
      try {
        const next = await apiClient.get<DiscoverStatus>(`/api/discover/status/${runId}`);
        setStatus(next);
        if (next.step && next.step !== lastStep.current) {
          lastStep.current = next.step;
          const now = Date.now();
          setLog((prev) => [...prev, { step: next.step as string, at: now, display: new Date(now).toLocaleTimeString() }]);
        }
      } catch (err) {
        logger.error("status poll failed", err);
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
    try {
      const res = await apiClient.post<{ run_id: string }>("/api/discover", {});
      setRunId(res.run_id);
      setStatus({ run_id: res.run_id, status: "running", step: "started", error: null, total_tables: null, tables_done: null });
    } catch (err) {
      logger.error("failed to start discovery", err);
    } finally {
      setStarting(false);
    }
  }

  async function toggleTable(tableName: string) {
    if (expanded === tableName) {
      setExpanded(null);
      setColumns(null);
      return;
    }
    setExpanded(tableName);
    const r = await apiClient.get<{ columns: ColumnResult[] }>(`/api/discover/results/${tableName}`);
    setColumns(r.columns);
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
        <span style={styles.wordmark}>Table Lens</span>
        <span style={styles.subtitle}>discovery agent — e2e run</span>
      </div>

      <button
        onClick={handleRun}
        disabled={starting || isRunning}
        style={{
          ...styles.button,
          ...(starting || isRunning ? styles.buttonDisabled : {}),
        }}
      >
        {isRunning ? "running…" : starting ? "starting…" : "run discovery"}
      </button>

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

      {results && (
        <div style={styles.panel}>
          <div style={styles.panelTitle}>discovered tables ({results.length})</div>
          {results.map((t) => (
            <div key={t.table_name} style={styles.tableRow}>
              <div style={styles.tableRowHeader} onClick={() => toggleTable(t.table_name)}>
                <span style={styles.tableName}>{t.table_name}</span>
                <span style={styles.expandHint}>{expanded === t.table_name ? "−" : "+"}</span>
              </div>
              <div style={styles.tableDesc}>{t.description}</div>
              {expanded === t.table_name && columns && (
                <div style={styles.columnList}>
                  {columns.map((c) => (
                    <div key={c.column_name} style={styles.columnRow}>
                      <span style={styles.columnName}>{c.column_name}</span>
                      <span style={styles.dim}> — {c.description}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </main>
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
    maxWidth: 720,
    margin: "0 auto",
    padding: "64px 24px",
  },
  header: {
    display: "flex",
    alignItems: "baseline",
    gap: 12,
    marginBottom: 32,
  },
  wordmark: {
    fontSize: 18,
    fontWeight: 600,
    letterSpacing: "-0.02em",
  },
  subtitle: {
    fontSize: 13,
    color: "var(--text-dim)",
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
  },
  accentText: {
    color: "var(--accent)",
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
  tableRow: {
    borderBottom: "1px solid var(--border)",
    padding: "12px 16px",
  },
  tableRowHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    cursor: "pointer",
  },
  tableName: {
    fontSize: 13,
    color: "var(--accent)",
  },
  expandHint: {
    color: "var(--text-faint)",
    fontSize: 14,
  },
  tableDesc: {
    fontSize: 12,
    color: "var(--text-dim)",
    marginTop: 4,
    lineHeight: 1.5,
  },
  columnList: {
    marginTop: 10,
    paddingLeft: 12,
    borderLeft: "1px solid var(--border)",
  },
  columnRow: {
    fontSize: 12,
    padding: "3px 0",
  },
  columnName: {
    color: "var(--text)",
  },
};
