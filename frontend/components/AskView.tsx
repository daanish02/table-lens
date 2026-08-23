"use client";

/** /ask page: a chat panel (SSE-streamed query-agent progress + typed
 * answer) split against a draggable SQL/results table view. */

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { apiClient } from "../lib/api-client";
import { logger } from "../lib/logger";
import { formatCell, formatCount } from "../lib/format";
import { downloadCsv, filenameFor } from "../lib/csv";

type ProgressLine = { text: string; ok?: boolean };

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  error?: boolean;
  elapsedMs?: number;
  steps?: ProgressLine[];
};

type QueryResult = {
  answer: string;
  sql: string | null;
  columns: string[] | null;
  rows: Record<string, unknown>[] | null;
  row_count: number | null;
  headline: string | null;
  elapsed_ms: number;
};

type StreamEvent =
  | { type: "tool_call"; tool: string; args: Record<string, unknown> }
  | { type: "tool_result"; tool: string; summary: string }
  | { type: "answer_delta"; text: string }
  | ({ type: "done" } & QueryResult);

function toolCallLabel(tool: string, args: Record<string, unknown>): string {
  switch (tool) {
    case "search_tables":
      return `searching tables for "${args.query}"`;
    case "search_columns":
      return `checking columns in ${args.table_name}`;
    case "run_sql":
      return "running SQL";
    default:
      return `calling ${tool}`;
  }
}

const PAGE_SIZE = 50;
// Generous enough not to false-positive on a legitimately long multi-round
// agent run — matches the backend's own bounded worst case now that every
// LLM call there has its own timeout.
const REQUEST_TIMEOUT_MS = 5 * 60 * 1000;
const MIN_V_SPLIT_PCT = 20;
const MAX_V_SPLIT_PCT = 85;
const DEFAULT_V_SPLIT_PCT = 70;
const MIN_CHAT_PCT = 20;
const MAX_CHAT_PCT = 60;
const DEFAULT_CHAT_PCT = 100 / 3;

function formatElapsed(ms: number): string {
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`;
}

export default function AskView() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [progressLines, setProgressLines] = useState<ProgressLine[]>([]);
  const [streamingText, setStreamingText] = useState("");
  const [result, setResult] = useState<QueryResult | null>(null);
  const [page, setPage] = useState(1);
  const [vSplitPct, setVSplitPct] = useState(DEFAULT_V_SPLIT_PCT);
  const [chatPct, setChatPct] = useState(DEFAULT_CHAT_PCT);
  const [copied, setCopied] = useState(false);
  const [expandedSteps, setExpandedSteps] = useState<Set<number>>(new Set());

  const chatLogRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const resultsPanelRef = useRef<HTMLDivElement>(null);
  const draggingV = useRef(false);
  const draggingH = useRef(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Without this, navigating away (or unmounting) mid-request left the
  // fetch running against a component that no longer exists — wasted
  // backend work with nothing left to receive it.
  useEffect(() => () => abortControllerRef.current?.abort(), []);

  useEffect(() => {
    chatLogRef.current?.scrollTo({ top: chatLogRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading, progressLines, streamingText]);

  useEffect(() => {
    function onMove(e: MouseEvent) {
      if (draggingV.current && resultsPanelRef.current) {
        const rect = resultsPanelRef.current.getBoundingClientRect();
        const pct = ((e.clientY - rect.top) / rect.height) * 100;
        setVSplitPct(Math.min(MAX_V_SPLIT_PCT, Math.max(MIN_V_SPLIT_PCT, pct)));
      }
      if (draggingH.current && containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        const pct = ((e.clientX - rect.left) / rect.width) * 100;
        setChatPct(Math.min(MAX_CHAT_PCT, Math.max(MIN_CHAT_PCT, pct)));
      }
    }
    function onUp() {
      draggingV.current = false;
      draggingH.current = false;
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
    setProgressLines([]);
    setStreamingText("");

    let liveAnswer = "";
    let finalResult: QueryResult | null = null;
    const stepsAcc: ProgressLine[] = [];

    const controller = new AbortController();
    abortControllerRef.current = controller;
    const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

    try {
      await apiClient.streamPost<StreamEvent>("/api/query", { question, history }, (event) => {
        if (event.type === "tool_call") {
          const line: ProgressLine = { text: toolCallLabel(event.tool, event.args) };
          stepsAcc.push(line);
          setProgressLines((prev) => [...prev, line]);
        } else if (event.type === "tool_result" && event.tool === "run_sql") {
          const ok = !event.summary.startsWith("error");
          const line: ProgressLine = { text: event.summary, ok };
          stepsAcc.push(line);
          setProgressLines((prev) => [...prev, line]);
        } else if (event.type === "answer_delta") {
          liveAnswer += event.text;
          setStreamingText(liveAnswer);
        } else if (event.type === "done") {
          finalResult = {
            answer: event.answer,
            sql: event.sql,
            columns: event.columns,
            rows: event.rows,
            row_count: event.row_count,
            headline: event.headline,
            elapsed_ms: event.elapsed_ms,
          };
        }
      }, controller.signal);

      // Explicit cast, not just an annotation: TypeScript's control-flow
      // analysis for a `let` reassigned inside a closure passed to an
      // awaited function narrows the post-await read to `never` (a known
      // CFA limitation, reproducible in isolation) — the annotation alone
      // doesn't override it, the cast does.
      const settled = finalResult as QueryResult | null;
      const answerText = (settled && settled.answer) || liveAnswer || (settled && settled.headline) || "(no answer)";
      setMessages((prev) => [...prev, { role: "assistant", content: answerText, elapsedMs: settled?.elapsed_ms, steps: stepsAcc }]);
      if (settled && settled.sql) {
        setResult(settled);
        setPage(1);
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        // User-initiated stop or the request timeout — not a failure, so no
        // error bubble. Keep whatever partial answer had already streamed
        // in, if any, rather than silently discarding it.
        if (liveAnswer) {
          setMessages((prev) => [...prev, { role: "assistant", content: liveAnswer, steps: stepsAcc }]);
        }
      } else {
        logger.error("query failed", err);
        setMessages((prev) => [...prev, { role: "assistant", content: "Something went wrong answering that — try rephrasing the question.", error: true, steps: stepsAcc }]);
      }
    } finally {
      clearTimeout(timeoutId);
      abortControllerRef.current = null;
      setLoading(false);
      setProgressLines([]);
      setStreamingText("");
    }
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function toggleSteps(index: number) {
    setExpandedSteps((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  }

  async function copySql() {
    if (!result?.sql) return;
    try {
      await navigator.clipboard.writeText(result.sql);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch (err) {
      logger.error("copy failed", err);
    }
  }

  const rows = result?.rows ?? [];
  const columns = result?.columns ?? [];
  const totalPages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const pageRows = rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const lastQuestion = [...messages].reverse().find((m) => m.role === "user")?.content;

  return (
    <div style={styles.split} ref={containerRef}>
      <div style={{ ...styles.chatPanel, width: `${chatPct}%` }}>
        <div style={styles.chatLog} ref={chatLogRef}>
          {messages.length === 0 && (
            <div style={styles.emptyHint}>Ask a question about your data in plain English — no SQL or schema knowledge needed.</div>
          )}
          {messages.map((m, i) => (
            <div key={i} style={styles.bubbleRow}>
              {m.steps && m.steps.length > 0 && (
                <div style={styles.stepsWrap}>
                  <button style={styles.stepsToggle} onClick={() => toggleSteps(i)}>
                    {expandedSteps.has(i) ? "▾" : "▸"} {m.steps.length} step{m.steps.length === 1 ? "" : "s"}
                  </button>
                  {expandedSteps.has(i) && (
                    <div style={styles.progressBox}>
                      {m.steps.map((line, j) => (
                        <ProgressLineView key={j} line={line} />
                      ))}
                    </div>
                  )}
                </div>
              )}
              <div style={{ ...styles.bubble, ...(m.role === "user" ? styles.bubbleUser : styles.bubbleAssistant), ...(m.error ? styles.bubbleError : {}) }}>
                {m.role === "assistant" ? (
                  <div className="markdown-body">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
                  </div>
                ) : (
                  m.content
                )}
              </div>
              {m.elapsedMs !== undefined && <div style={styles.elapsedTag}>{formatElapsed(m.elapsedMs)}</div>}
            </div>
          ))}
          {loading && (
            <div style={styles.bubbleRow}>
              {progressLines.length > 0 && (
                <div style={styles.progressBox}>
                  {progressLines.map((line, i) => (
                    <ProgressLineView key={i} line={line} />
                  ))}
                </div>
              )}
              {streamingText ? (
                <div style={{ ...styles.bubble, ...styles.bubbleAssistant }}>
                  <div className="markdown-body">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{streamingText}</ReactMarkdown>
                  </div>
                  <span style={styles.cursor}>▍</span>
                </div>
              ) : (
                progressLines.length === 0 && (
                  <div style={{ ...styles.bubble, ...styles.bubbleAssistant, ...styles.dim }}>thinking…</div>
                )
              )}
            </div>
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
          {loading ? (
            <button style={styles.sendButton} onClick={() => abortControllerRef.current?.abort()}>
              stop
            </button>
          ) : (
            <button style={styles.sendButton} onClick={handleSend} disabled={!input.trim()}>
              send
            </button>
          )}
        </div>
      </div>

      <div
        style={styles.hDivider}
        onMouseDown={(e) => {
          draggingH.current = true;
          e.preventDefault();
        }}
      >
        <div style={styles.hDividerHandle} />
      </div>

      <div style={styles.resultsPanel} ref={resultsPanelRef}>
        <div style={{ ...styles.tableSection, height: `${vSplitPct}%` }}>
          {!result && <div style={styles.emptyHint}>Results will appear here once you ask a question.</div>}
          {result && (
            <>
              <div style={styles.metaRow}>
                <div style={styles.meta}>{formatCount(result.row_count)} rows</div>
                {result.rows && result.rows.length > 0 && (
                  <button
                    style={styles.copyButton}
                    onClick={() => downloadCsv(filenameFor(lastQuestion ?? "table-lens-results"), columns, result.rows!)}
                  >
                    download csv
                  </button>
                )}
              </div>
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
          style={styles.vDivider}
          onMouseDown={(e) => {
            draggingV.current = true;
            e.preventDefault();
          }}
        >
          <div style={styles.vDividerHandle} />
        </div>

        <div style={{ ...styles.sqlSection, height: `${100 - vSplitPct}%` }}>
          <div style={styles.sqlHeader}>
            <div style={styles.sectionTitle}>sql</div>
            {result?.sql && (
              <button style={styles.copyButton} onClick={copySql}>{copied ? "copied" : "copy"}</button>
            )}
          </div>
          <pre style={styles.sqlBox}>{result?.sql ?? "—"}</pre>
        </div>
      </div>
    </div>
  );
}

function ProgressLineView({ line }: { line: ProgressLine }) {
  if (line.ok === undefined) {
    return <div style={styles.progressLine}>{line.text}</div>;
  }
  return (
    <div style={styles.progressLine}>
      <span style={line.ok ? styles.progressOk : styles.progressErr}>{line.ok ? "✓" : "✗"}</span> {line.text}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  split: {
    display: "flex",
    height: "calc(100vh - 55px - 45px)", // full viewport minus nav bar and footer
  },
  chatPanel: {
    flexShrink: 0,
    display: "flex",
    flexDirection: "column",
    minWidth: 0,
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
    fontFamily: "var(--sans)",
    fontSize: 13,
    color: "var(--text-faint)",
    lineHeight: 1.5,
    padding: "8px 4px",
  },
  bubbleRow: {
    display: "flex",
    flexDirection: "column",
  },
  bubble: {
    fontFamily: "var(--sans)",
    fontSize: 14,
    lineHeight: 1.6,
    padding: "8px 12px",
    borderRadius: 2,
    maxWidth: "90%",
    whiteSpace: "pre-wrap",
  },
  bubbleUser: {
    alignSelf: "flex-end",
    // Same teal tint as --accent-dim, but opaque — --accent-dim is a low-
    // alpha rgba() (genuinely translucent by design), which let the fixed
    // background mesh show through once its stacking was fixed to
    // properly sit below normal content. color-mix() bakes the same blend
    // into a solid color, still theme-aware since it reads --accent/--bg.
    background: "color-mix(in srgb, var(--accent) 12%, var(--bg))",
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
  elapsedTag: {
    alignSelf: "flex-start",
    fontSize: 10,
    color: "var(--text-faint)",
    marginTop: 3,
    marginLeft: 2,
  },
  dim: {
    color: "var(--text-dim)",
    fontSize: 12,
  },
  progressBox: {
    alignSelf: "flex-start",
    display: "flex",
    flexDirection: "column",
    gap: 3,
    marginBottom: 6,
  },
  stepsWrap: {
    alignSelf: "flex-start",
    display: "flex",
    flexDirection: "column",
  },
  stepsToggle: {
    alignSelf: "flex-start",
    background: "transparent",
    border: "none",
    color: "var(--text-faint)",
    fontFamily: "var(--mono)",
    fontSize: 11,
    padding: "2px 2px 4px",
    cursor: "pointer",
  },
  progressLine: {
    fontSize: 11,
    color: "var(--text-faint)",
    fontFamily: "var(--mono)",
  },
  progressOk: {
    color: "var(--accent)",
  },
  progressErr: {
    color: "var(--error)",
  },
  cursor: {
    display: "inline-block",
    color: "var(--accent)",
    animation: "blink-cursor 1s steps(1) infinite",
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
    fontFamily: "var(--sans)",
    fontSize: 14,
    padding: "8px 10px",
    borderRadius: 2,
  },
  sendButton: {
    // Same reasoning as bubbleUser above — see it for why "transparent"
    // is a problem now that the background mesh's stacking is fixed.
    background: "var(--bg)",
    border: "1px solid var(--accent)",
    color: "var(--accent)",
    padding: "0 16px",
    fontFamily: "var(--mono)",
    fontSize: 12,
    cursor: "pointer",
    borderRadius: 2,
  },
  hDivider: {
    width: 10,
    flexShrink: 0,
    cursor: "col-resize",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    borderLeft: "1px solid var(--border)",
    borderRight: "1px solid var(--border)",
    background: "var(--surface)",
  },
  hDividerHandle: {
    width: 3,
    height: 32,
    borderRadius: 2,
    background: "var(--border-strong)",
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
    flexShrink: 0,
  },
  metaRow: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
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
    background: "var(--bg)",
    border: "1px solid var(--border)",
    color: "var(--text)",
    padding: "5px 12px",
    fontFamily: "var(--mono)",
    fontSize: 12,
    cursor: "pointer",
    borderRadius: 2,
  },
  vDivider: {
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
  vDividerHandle: {
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
  sqlHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 8,
    flexShrink: 0,
  },
  sectionTitle: {
    fontSize: 11,
    letterSpacing: "0.08em",
    textTransform: "uppercase",
    color: "var(--text-faint)",
  },
  copyButton: {
    background: "var(--bg)",
    border: "1px solid var(--border)",
    color: "var(--text-dim)",
    padding: "3px 10px",
    fontFamily: "var(--mono)",
    fontSize: 11,
    cursor: "pointer",
    borderRadius: 2,
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
