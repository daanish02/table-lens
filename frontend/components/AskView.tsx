"use client";

import { useEffect, useRef, useState } from "react";
import { apiClient } from "../lib/api-client";
import { logger } from "../lib/logger";
import { formatCell, formatCount } from "../lib/format";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  error?: boolean;
};

type QueryResult = {
  answer: string;
  sql: string | null;
  columns: string[] | null;
  rows: Record<string, unknown>[] | null;
  row_count: number | null;
  headline: string | null;
};

const PAGE_SIZE = 50;
const MIN_SPLIT_PCT = 20;
const MAX_SPLIT_PCT = 85;
const DEFAULT_SPLIT_PCT = 70;

export default function AskView() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [page, setPage] = useState(1);
  const [splitPct, setSplitPct] = useState(DEFAULT_SPLIT_PCT);

  const chatLogRef = useRef<HTMLDivElement>(null);
  const resultsPanelRef = useRef<HTMLDivElement>(null);
  const draggingRef = useRef(false);

  useEffect(() => {
    chatLogRef.current?.scrollTo({ top: chatLogRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    function onMove(e: MouseEvent) {
      if (!draggingRef.current || !resultsPanelRef.current) return;
      const rect = resultsPanelRef.current.getBoundingClientRect();
      const pct = ((e.clientY - rect.top) / rect.height) * 100;
      setSplitPct(Math.min(MAX_SPLIT_PCT, Math.max(MIN_SPLIT_PCT, pct)));
    }
    function onUp() {
      draggingRef.current = false;
    }
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, []);

  async function handleSend() {
    const question = input.trim();
    if (!question || loading) return;

    const history = messages.map((m) => ({ role: m.role, content: m.content }));
    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setInput("");
    setLoading(true);

    try {
      const res = await apiClient.post<QueryResult>("/api/query", { question, history });
      setMessages((prev) => [...prev, { role: "assistant", content: res.answer || res.headline || "(no answer)" }]);
      if (res.sql) {
        setResult(res);
        setPage(1);
      }
    } catch (err) {
      logger.error("query failed", err);
      setMessages((prev) => [...prev, { role: "assistant", content: "Something went wrong answering that — try rephrasing the question.", error: true }]);
    } finally {
      setLoading(false);
    }
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  const rows = result?.rows ?? [];
  const columns = result?.columns ?? [];
  const totalPages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const pageRows = rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  return (
    <div style={styles.split}>
      <div style={styles.chatPanel}>
        <div style={styles.chatLog} ref={chatLogRef}>
          {messages.length === 0 && (
            <div style={styles.emptyHint}>Ask a question about your data — e.g. "how many claims are approved?"</div>
          )}
          {messages.map((m, i) => (
            <div key={i} style={{ ...styles.bubble, ...(m.role === "user" ? styles.bubbleUser : styles.bubbleAssistant), ...(m.error ? styles.bubbleError : {}) }}>
              {m.content}
            </div>
          ))}
          {loading && (
            <div style={{ ...styles.bubble, ...styles.bubbleAssistant, ...styles.dim }}>thinking…</div>
          )}
        </div>
        <div style={styles.inputRow}>
          <textarea
            style={styles.textarea}
            placeholder="ask a question…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            rows={2}
          />
          <button style={styles.sendButton} onClick={handleSend} disabled={loading || !input.trim()}>
            send
          </button>
        </div>
      </div>

      <div style={styles.resultsPanel} ref={resultsPanelRef}>
        <div style={{ ...styles.tableSection, height: `${splitPct}%` }}>
          {!result && <div style={styles.emptyHint}>Results will appear here once you ask a question.</div>}
          {result && (
            <>
              <div style={styles.meta}>{formatCount(result.row_count)} rows</div>
              <div style={styles.tableWrap}>
                <table style={styles.table}>
                  <thead>
                    <tr>
                      {columns.map((c) => (
                        <th key={c} style={styles.th}>{c}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {pageRows.map((row, i) => (
                      <tr key={i}>
                        {columns.map((c) => (
                          <td key={c} style={styles.td}>{formatCell(row[c])}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {totalPages > 1 && (
                <div style={styles.pager}>
                  <button style={styles.pagerButton} disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>← prev</button>
                  <span style={styles.dim}>{page} / {totalPages}</span>
                  <button style={styles.pagerButton} disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>next →</button>
                </div>
              )}
            </>
          )}
        </div>

        <div
          style={styles.divider}
          onMouseDown={(e) => {
            draggingRef.current = true;
            e.preventDefault();
          }}
        >
          <div style={styles.dividerHandle} />
        </div>

        <div style={{ ...styles.sqlSection, height: `${100 - splitPct}%` }}>
          <div style={styles.sectionTitle}>sql</div>
          <pre style={styles.sqlBox}>{result?.sql ?? "—"}</pre>
        </div>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  split: {
    display: "flex",
    height: "calc(100vh - 55px)", // full viewport minus nav bar
  },
  chatPanel: {
    width: 380,
    flexShrink: 0,
    display: "flex",
    flexDirection: "column",
    borderRight: "1px solid var(--border)",
  },
  chatLog: {
    flex: 1,
    overflowY: "auto",
    padding: "16px",
    display: "flex",
    flexDirection: "column",
    gap: 10,
  },
  emptyHint: {
    fontSize: 12,
    color: "var(--text-faint)",
    lineHeight: 1.5,
    padding: "8px 4px",
  },
  bubble: {
    fontSize: 13,
    lineHeight: 1.5,
    padding: "8px 12px",
    borderRadius: 2,
    maxWidth: "90%",
    whiteSpace: "pre-wrap",
  },
  bubbleUser: {
    alignSelf: "flex-end",
    background: "var(--accent-dim)",
    color: "var(--text)",
  },
  bubbleAssistant: {
    alignSelf: "flex-start",
    background: "var(--surface)",
    color: "var(--text)",
    border: "1px solid var(--border)",
  },
  bubbleError: {
    borderColor: "var(--error)",
    color: "var(--error)",
  },
  dim: {
    color: "var(--text-dim)",
    fontSize: 12,
  },
  inputRow: {
    display: "flex",
    gap: 8,
    padding: "12px",
    borderTop: "1px solid var(--border)",
  },
  textarea: {
    flex: 1,
    resize: "none",
    background: "var(--surface)",
    border: "1px solid var(--border)",
    color: "var(--text)",
    fontFamily: "var(--mono)",
    fontSize: 13,
    padding: "8px 10px",
    borderRadius: 2,
  },
  sendButton: {
    background: "transparent",
    border: "1px solid var(--accent)",
    color: "var(--accent)",
    padding: "0 16px",
    fontFamily: "var(--mono)",
    fontSize: 12,
    cursor: "pointer",
    borderRadius: 2,
  },
  resultsPanel: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    minWidth: 0,
  },
  tableSection: {
    padding: "16px 20px",
    overflow: "hidden",
    display: "flex",
    flexDirection: "column",
    minHeight: 0,
  },
  meta: {
    fontSize: 12,
    color: "var(--text-dim)",
    marginBottom: 10,
    flexShrink: 0,
  },
  tableWrap: {
    border: "1px solid var(--border)",
    borderRadius: 2,
    overflow: "auto",
    flex: 1,
    minHeight: 0,
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
    marginTop: 10,
    flexShrink: 0,
  },
  pagerButton: {
    background: "transparent",
    border: "1px solid var(--border)",
    color: "var(--text)",
    padding: "5px 12px",
    fontFamily: "var(--mono)",
    fontSize: 12,
    cursor: "pointer",
    borderRadius: 2,
  },
  divider: {
    height: 10,
    flexShrink: 0,
    cursor: "row-resize",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    borderTop: "1px solid var(--border)",
    borderBottom: "1px solid var(--border)",
    background: "var(--surface)",
  },
  dividerHandle: {
    width: 32,
    height: 3,
    borderRadius: 2,
    background: "var(--border-strong)",
  },
  sqlSection: {
    padding: "12px 20px",
    overflow: "hidden",
    display: "flex",
    flexDirection: "column",
    minHeight: 0,
  },
  sectionTitle: {
    fontSize: 11,
    letterSpacing: "0.08em",
    textTransform: "uppercase",
    color: "var(--text-faint)",
    marginBottom: 8,
    flexShrink: 0,
  },
  sqlBox: {
    flex: 1,
    minHeight: 0,
    margin: 0,
    overflow: "auto",
    background: "var(--bg)",
    border: "1px solid var(--border)",
    borderRadius: 2,
    padding: "10px 12px",
    fontFamily: "var(--mono)",
    fontSize: 12,
    color: "var(--text)",
    whiteSpace: "pre-wrap",
  },
};
