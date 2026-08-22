"use client";

import { useEffect, useRef, useState } from "react";
import { apiClient } from "../lib/api-client";
import { logger } from "../lib/logger";

type DiscoverStatus = {
  run_id: string;
  status: "pending" | "running" | "done" | "failed";
  step: string | null;
  error: string | null;
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
  at: string;
};

export default function DiscoverPanel() {
  const [runId, setRunId] = useState<string | null>(null);
  const [status, setStatus] = useState<DiscoverStatus | null>(null);
  const [log, setLog] = useState<LogEntry[]>([]);
  const [starting, setStarting] = useState(false);
  const [results, setResults] = useState<TableResult[] | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [columns, setColumns] = useState<ColumnResult[] | null>(null);
  const lastStep = useRef<string | null>(null);

  useEffect(() => {
    if (!runId || !status || status.status === "done" || status.status === "failed") return;

    const interval = setInterval(async () => {
      try {
        const next = await apiClient.get<DiscoverStatus>(`/api/discover/status/${runId}`);
        setStatus(next);
        if (next.step && next.step !== lastStep.current) {
          lastStep.current = next.step;
          setLog((prev) => [...prev, { step: next.step as string, at: new Date().toLocaleTimeString() }]);
        }
      } catch (err) {
        logger.error("status poll failed", err);
      }
    }, 1500);

    return () => clearInterval(interval);
  }, [runId, status]);

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
    try {
      const res = await apiClient.post<{ run_id: string }>("/api/discover", {});
      setRunId(res.run_id);
      setStatus({ run_id: res.run_id, status: "running", step: "started", error: null });
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

  return (
    <main style={styles.page}>
      <div style={styles.header}>
        <span style={styles.wordmark}>table-lens</span>
        <span style={styles.subtitle}>discovery agent — e2e run</span>
      </div>

      <button
        onClick={handleRun}
        disabled={starting || status?.status === "running"}
        style={{
          ...styles.button,
          ...(starting || status?.status === "running" ? styles.buttonDisabled : {}),
        }}
      >
        {status?.status === "running" ? "running…" : starting ? "starting…" : "run discovery"}
      </button>

      {status && (
        <div style={styles.statusRow}>
          <StatusBadge status={status.status} />
          <span style={styles.dim}>run_id: {status.run_id}</span>
        </div>
      )}

      {status?.error && <div style={styles.errorBox}>{status.error}</div>}

      {log.length > 0 && (
        <div style={styles.panel}>
          <div style={styles.panelTitle}>steps</div>
          <div style={styles.logBox}>
            {log.map((entry, i) => (
              <div key={i} style={styles.logLine}>
                <span style={styles.dim}>{entry.at}</span> {entry.step}
              </div>
            ))}
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
  errorBox: {
    marginTop: 16,
    border: "1px solid var(--error)",
    background: "var(--error-dim)",
    color: "var(--error)",
    padding: "10px 14px",
    fontSize: 13,
    borderRadius: 2,
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
    maxHeight: 260,
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
