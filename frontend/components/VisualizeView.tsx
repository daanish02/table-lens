"use client";

/** /visualize page: same chat-driven query flow as AskView, but each
 * finished result is handed to the visualize agent to build a chart —
 * single mode replaces the current chart, dashboard mode accumulates them. */

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { EChartsOption } from "echarts";
import { apiClient } from "../lib/api-client";
import { logger } from "../lib/logger";
import { formatCount } from "../lib/format";
import { getCurrentTheme } from "../lib/theme";
import EChart, { EChartHandle } from "./EChart";
import { downloadCsv, filenameFor } from "../lib/csv";
import { useIsNarrow } from "../lib/useIsNarrow";

type Mode = "single" | "dashboard";

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

// Produced by the visualize agent (backend) — see app/visualize/agent.py.
// chart_type is a string, not a fixed union: the backend validates it
// against its own allowed set, the frontend just renders whatever comes
// back rather than re-encoding that list a second time.
type ChartSpec = {
  title: string;
  chart_type: string;
  option: Record<string, unknown> | null;
  error?: string;
};

type ChartCard = {
  localId: string;
  question: string;
  sql: string;
  columns: string[]; // column order for CSV export, kept separate from rows so it's stable even if a row is missing a key
  rows: Record<string, unknown>[]; // kept for the "stat" single-value display — the LLM's option is legitimately null for that type
  spec: ChartSpec | null; // null while the visualize agent is still working
  loadFailed: boolean;
  savedId: string | null;
  saving: boolean;
};

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

function formatElapsed(ms: number): string {
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`;
}

let localIdCounter = 0;
function nextLocalId(): string {
  localIdCounter += 1;
  return `chart-${localIdCounter}`;
}

const VIZ_SUGGESTIONS = [
  "Claims by status",
  "Monthly premium revenue this year",
  "Average claim amount by incident type",
  "Active agents by region",
  "Claims volume by month vs last year",
  "Risk score vs loss ratio by risk category",
];

const MIN_CHAT_PCT = 20;
const MAX_CHAT_PCT = 60;
const DEFAULT_CHAT_PCT = 100 / 3;
// Generous enough not to false-positive on a legitimately long multi-round
// agent run — matches the backend's own bounded worst case now that every
// LLM call there has its own timeout.
const REQUEST_TIMEOUT_MS = 5 * 60 * 1000;

export default function VisualizeView() {
  const [mode, setMode] = useState<Mode>("single");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [progressLines, setProgressLines] = useState<ProgressLine[]>([]);
  const [streamingText, setStreamingText] = useState("");
  const [charts, setCharts] = useState<ChartCard[]>([]);
  const [expandedSteps, setExpandedSteps] = useState<Set<number>>(new Set());
  const [expandedSql, setExpandedSql] = useState<Set<string>>(new Set());
  const [chatPct, setChatPct] = useState(DEFAULT_CHAT_PCT);
  const [savingDashboard, setSavingDashboard] = useState(false);
  const narrow = useIsNarrow();

  const chatLogRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
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
      if (draggingH.current && containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        const pct = ((e.clientX - rect.left) / rect.width) * 100;
        setChatPct(Math.min(MAX_CHAT_PCT, Math.max(MIN_CHAT_PCT, pct)));
      }
    }
    function onUp() {
      draggingH.current = false;
    }
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, []);

  async function autoSaveChart(card: ChartCard) {
    if (!card.spec) return;
    try {
      const res = await apiClient.post<{ id: string }>("/api/charts", {
        title: card.spec.title,
        question: card.question,
        sql: card.sql,
        chart_type: card.spec.chart_type,
        chart_config: card.spec.option ?? {},
        result_cache: {},
      });
      setCharts((prev) => prev.map((c) => (c.localId === card.localId ? { ...c, savedId: res.id, saving: false } : c)));
    } catch (err) {
      // Non-blocking: the chart itself is already built and shown, this
      // only failed to persist it. The user can retry via "save chart".
      logger.warn("auto-save chart failed", err);
      setCharts((prev) => prev.map((c) => (c.localId === card.localId ? { ...c, saving: false } : c)));
    }
  }

  async function saveChartManually(card: ChartCard) {
    setCharts((prev) => prev.map((c) => (c.localId === card.localId ? { ...c, saving: true } : c)));
    await autoSaveChart(card);
  }

  async function saveDashboard() {
    const savedIds = charts.filter((c) => c.savedId).map((c) => c.savedId as string);
    if (savedIds.length === 0) return;
    const title = window.prompt("Dashboard title?", "My Dashboard");
    if (!title) return;
    setSavingDashboard(true);
    try {
      await apiClient.post("/api/dashboards", { title, chart_ids: savedIds });
    } catch (err) {
      // Non-blocking: the individual charts are already saved, only the
      // dashboard grouping failed. The user can retry.
      logger.warn("save dashboard failed", err);
    } finally {
      setSavingDashboard(false);
    }
  }

  // Query agent's finished result -> visualize agent, verbatim. The
  // visualize agent never re-runs anything; it only decides how to
  // present what's already here.
  async function buildChart(localId: string, question: string, result: QueryResult) {
    try {
      const spec = await apiClient.post<ChartSpec>("/api/visualize", {
        question,
        sql: result.sql,
        headline: result.headline,
        columns: result.columns,
        rows: result.rows,
        theme: getCurrentTheme(),
      });
      setCharts((prev) => prev.map((c) => (c.localId === localId ? { ...c, spec } : c)));
      if (mode === "dashboard") {
        autoSaveChart({
          localId, question, sql: result.sql as string,
          columns: result.columns as string[], rows: result.rows as Record<string, unknown>[],
          spec, loadFailed: false, savedId: null, saving: false,
        });
      }
    } catch (err) {
      logger.error("visualize agent failed", err);
      setCharts((prev) => prev.map((c) => (c.localId === localId ? { ...c, loadFailed: true } : c)));
    }
  }

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

      // See AskView.tsx for why this needs an explicit cast, not just an
      // annotation — a documented TS control-flow-analysis limitation with
      // `let` reassigned inside a closure passed to an awaited function.
      const settled = finalResult as QueryResult | null;
      const answerText = (settled && settled.answer) || liveAnswer || (settled && settled.headline) || "(no answer)";
      setMessages((prev) => [...prev, { role: "assistant", content: answerText, elapsedMs: settled?.elapsed_ms, steps: stepsAcc }]);

      if (settled && settled.sql && settled.columns && settled.rows && settled.rows.length > 0) {
        const localId = nextLocalId();
        const card: ChartCard = {
          localId,
          question,
          sql: settled.sql,
          columns: settled.columns,
          rows: settled.rows,
          spec: null,
          loadFailed: false,
          savedId: null,
          saving: false,
        };
        setCharts((prev) => (mode === "single" ? [card] : [...prev, card]));
        buildChart(localId, question, settled);
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

  function toggleSql(localId: string) {
    setExpandedSql((prev) => {
      const next = new Set(prev);
      if (next.has(localId)) next.delete(localId);
      else next.add(localId);
      return next;
    });
  }

  return (
    <div style={{ ...styles.split, ...(narrow ? styles.splitNarrow : {}) }} ref={containerRef}>
      <div style={{ ...styles.chatPanel, ...(narrow ? styles.chatPanelNarrow : { width: `${chatPct}%` }) }}>
        <div style={styles.modeRow}>
          <button
            style={{ ...styles.modeButton, ...(mode === "single" ? styles.modeButtonActive : {}) }}
            onClick={() => setMode("single")}
            title="Each question replaces the chart shown"
          >
            single
          </button>
          <button
            style={{ ...styles.modeButton, ...(mode === "dashboard" ? styles.modeButtonActive : {}) }}
            onClick={() => setMode("dashboard")}
            title="Each question adds a new chart to the dashboard"
          >
            dashboard
          </button>
        </div>
        <div style={styles.chatLog} ref={chatLogRef}>
          {messages.length === 0 && (
            <div>
              <div style={styles.emptyHint}>
                Ask a question and it'll be turned into a chart automatically. {mode === "dashboard" ? "Each answer adds a chart to the dashboard on the right." : "Each question replaces the chart on the right."}
              </div>
              <div style={styles.suggestions}>
                {VIZ_SUGGESTIONS.map((q) => (
                  <button
                    key={q}
                    style={styles.suggestionChip}
                    onClick={() => {
                      setInput(q);
                      textareaRef.current?.focus();
                    }}
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
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
            ref={textareaRef}
            style={styles.textarea}
            placeholder="describe the chart you want…"
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

      {!narrow && (
        <div
          style={styles.hDivider}
          onMouseDown={(e) => {
            draggingH.current = true;
            e.preventDefault();
          }}
        >
          <div style={styles.hDividerHandle} />
        </div>
      )}

      <div style={{ ...styles.canvasPanel, ...(narrow ? styles.canvasPanelNarrow : {}) }}>
        {mode === "dashboard" && charts.length > 0 && (
          <div style={styles.dashboardHeader}>
            <span style={styles.dim}>{charts.length} chart{charts.length === 1 ? "" : "s"}</span>
            <button style={styles.saveDashboardButton} onClick={saveDashboard} disabled={savingDashboard || charts.every((c) => !c.savedId)}>
              {savingDashboard ? "saving…" : "save as dashboard"}
            </button>
          </div>
        )}

        {charts.length === 0 && <div style={styles.emptyHint}>Charts will appear here once you ask a question.</div>}

        <div style={mode === "dashboard" ? styles.grid : styles.singleWrap}>
          {charts.map((card) => (
            <ChartCardView
              key={card.localId}
              card={card}
              compact={mode === "dashboard"}
              sqlExpanded={expandedSql.has(card.localId)}
              onToggleSql={() => toggleSql(card.localId)}
              onSave={mode === "single" ? () => saveChartManually(card) : undefined}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function ChartCardView({
  card,
  compact,
  sqlExpanded,
  onToggleSql,
  onSave,
}: {
  card: ChartCard;
  compact: boolean;
  sqlExpanded: boolean;
  onToggleSql: () => void;
  onSave?: () => void;
}) {
  const spec = card.spec;
  const [copied, setCopied] = useState(false);
  const chartRef = useRef<EChartHandle>(null);
  const narrow = useIsNarrow();

  async function copySql() {
    try {
      await navigator.clipboard.writeText(card.sql);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch (err) {
      logger.error("copy failed", err);
    }
  }

  const filenameBase = filenameFor(spec?.title ?? card.question);

  return (
    <div style={compact ? styles.chartCardCompact : styles.chartCard}>
      <div style={styles.chartCardTitle}>{spec?.title ?? card.question}</div>

      {!spec && !card.loadFailed && <div style={styles.dim}>designing chart…</div>}

      {card.loadFailed && <div style={styles.dim}>Couldn't build a chart for this — see SQL for the raw data.</div>}

      {spec && spec.option && (
        <EChart
          ref={chartRef}
          option={spec.option as EChartsOption}
          height={narrow ? (compact ? 200 : 240) : compact ? 260 : 360}
        />
      )}

      {spec && spec.chart_type === "stat" && card.rows[0] && (
        <div style={styles.statValue}>{formatCount(Number(Object.values(card.rows[0])[0]))}</div>
      )}

      {spec && !spec.option && spec.chart_type !== "stat" && (
        <div style={styles.dim}>No clear chart shape for this result — see SQL for the raw data.</div>
      )}

      <div style={styles.chartCardFooter}>
        <button style={styles.footerButton} onClick={onToggleSql}>{sqlExpanded ? "hide sql" : "view sql"}</button>
        {sqlExpanded && (
          <button style={styles.footerButton} onClick={copySql}>{copied ? "copied" : "copy"}</button>
        )}
        {spec && spec.option && (
          <button style={styles.footerButton} onClick={() => chartRef.current?.downloadPng(filenameBase)}>
            download png
          </button>
        )}
        {card.rows.length > 0 && (
          <button style={styles.footerButton} onClick={() => downloadCsv(filenameBase, card.columns, card.rows)}>
            download csv
          </button>
        )}
        {onSave && spec && (
          <button style={styles.footerButton} onClick={onSave} disabled={card.saving || !!card.savedId}>
            {card.savedId ? "saved" : card.saving ? "saving…" : "save chart"}
          </button>
        )}
        {compact && card.savedId && <span style={styles.savedTag}>saved</span>}
      </div>

      {sqlExpanded && <pre style={styles.sqlBox}>{card.sql}</pre>}
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
    // See AskView.tsx's identical split rule for why this is flex: 1 and
    // not a hardcoded height calc.
    flex: 1,
    minHeight: 0,
  },
  // Below the ~768px breakpoint (useIsNarrow): stack chat above the chart
  // canvas instead of a side-by-side split — see AskView.tsx's identical
  // splitNarrow for the full reasoning (drag divider hidden, not made
  // touch-operable).
  splitNarrow: {
    flexDirection: "column",
  },
  chatPanelNarrow: {
    width: "100%",
    height: "55vh",
  },
  canvasPanelNarrow: {
    width: "100%",
  },
  chatPanel: {
    flexShrink: 0,
    display: "flex",
    flexDirection: "column",
    minWidth: 0,
  },
  modeRow: {
    display: "flex",
    gap: 8,
    padding: "14px 12px",
  },
  modeButton: {
    flex: 1,
    // Same reasoning as bubbleUser in AskView.tsx — "transparent" let the
    // background mesh show through once its stacking was fixed to sit
    // properly below normal content; solid var(--bg) keeps the same
    // outline-button look with an opaque fill.
    background: "var(--bg)",
    border: "1px solid var(--border)",
    color: "var(--text-dim)",
    padding: "9px 0",
    fontFamily: "var(--mono)",
    fontSize: 12,
    cursor: "pointer",
    borderRadius: 2,
  },
  modeButtonActive: {
    borderColor: "var(--accent)",
    color: "var(--accent)",
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
  suggestions: {
    display: "flex",
    flexWrap: "wrap" as const,
    gap: 6,
    marginTop: 12,
  },
  suggestionChip: {
    background: "var(--surface)",
    border: "1px solid var(--border)",
    color: "var(--text-dim)",
    fontFamily: "var(--sans)",
    fontSize: 12,
    padding: "5px 10px",
    borderRadius: 2,
    cursor: "pointer",
    textAlign: "left" as const,
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
    // Same teal tint as --accent-dim, but opaque — see AskView.tsx's
    // bubbleUser for why --accent-dim's alpha is a problem here now.
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
  progressBox: {
    alignSelf: "flex-start",
    display: "flex",
    flexDirection: "column",
    gap: 3,
    marginBottom: 6,
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
    // Same reasoning as bubbleUser above.
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
  canvasPanel: {
    flex: 1,
    minWidth: 0,
    overflowY: "auto",
    padding: "20px 24px",
  },
  dashboardHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 16,
  },
  saveDashboardButton: {
    background: "var(--bg)",
    border: "1px solid var(--accent)",
    color: "var(--accent)",
    padding: "6px 14px",
    fontFamily: "var(--mono)",
    fontSize: 12,
    cursor: "pointer",
    borderRadius: 2,
  },
  singleWrap: {
    display: "flex",
    flexDirection: "column",
  },
  grid: {
    display: "grid",
    // min(360px, 100%) instead of a bare 360px — auto-fill's floor would
    // otherwise force at least 360px per column even on a viewport
    // narrower than that, overflowing the page horizontally.
    gridTemplateColumns: "repeat(auto-fill, minmax(min(360px, 100%), 1fr))",
    gap: 16,
  },
  chartCard: {
    border: "1px solid var(--border)",
    borderRadius: 2,
    padding: "18px 20px",
    background: "var(--bg)",
  },
  chartCardCompact: {
    border: "1px solid var(--border)",
    borderRadius: 2,
    padding: "14px 16px",
    background: "var(--bg)",
  },
  chartCardTitle: {
    fontSize: 15,
    fontWeight: 600,
    color: "var(--text)",
    marginBottom: 10,
  },
  statValue: {
    fontSize: 40,
    fontWeight: 600,
    color: "var(--accent)",
    padding: "20px 0",
    textAlign: "center",
  },
  chartCardFooter: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    marginTop: 10,
  },
  footerButton: {
    background: "var(--bg)",
    border: "1px solid var(--border)",
    color: "var(--text-dim)",
    padding: "4px 10px",
    fontFamily: "var(--mono)",
    fontSize: 11,
    cursor: "pointer",
    borderRadius: 2,
  },
  savedTag: {
    fontSize: 10,
    color: "var(--accent)",
  },
  sqlBox: {
    marginTop: 10,
    background: "var(--surface)",
    border: "1px solid var(--border)",
    borderRadius: 2,
    padding: "10px 12px",
    fontFamily: "var(--mono)",
    fontSize: 11,
    color: "var(--text)",
    whiteSpace: "pre-wrap",
    overflowX: "auto",
  },
};
