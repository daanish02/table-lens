import type { EChartsOption } from "echarts";

export type ChartType = "line" | "bar" | "pie" | "scatter" | "stat" | "table";

// Matches the dark theme in globals.css — ECharts renders to canvas, so it
// needs real color values, not CSS custom properties.
const COLORS = {
  bg: "#0a0a0b",
  surface: "#111113",
  border: "#26262b",
  text: "#e4e4e7",
  textDim: "#8b8b93",
  accent: "#35c9be",
  series: ["#35c9be", "#e5484d", "#e5b93f", "#8b7fd6", "#4f9de0", "#e07fb0"],
};

const DATE_NAME_RE = /date|_at$|month|year|period|time/i;

function isDateLike(name: string, values: unknown[]): boolean {
  if (DATE_NAME_RE.test(name)) return true;
  const sample = values.find((v) => v !== null && v !== undefined);
  if (typeof sample !== "string") return false;
  return /^\d{4}-\d{2}-\d{2}/.test(sample) && !isNaN(Date.parse(sample));
}

function isNumeric(values: unknown[]): boolean {
  const sample = values.filter((v) => v !== null && v !== undefined);
  if (sample.length === 0) return false;
  return sample.every((v) => typeof v === "number" || (typeof v === "string" && v.trim() !== "" && !isNaN(Number(v))));
}

function colValues(rows: Record<string, unknown>[], col: string): unknown[] {
  return rows.map((r) => r[col]);
}

export function pickChartType(columns: string[], rows: Record<string, unknown>[]): ChartType {
  if (rows.length === 0 || columns.length === 0) return "table";
  if (rows.length === 1 && columns.length === 1) return "stat";
  if (columns.length === 1) return "table";

  const dateCol = columns.find((c) => isDateLike(c, colValues(rows, c)));
  const numericCols = columns.filter((c) => c !== dateCol && isNumeric(colValues(rows, c)));
  const nonNumericCols = columns.filter((c) => c !== dateCol && !numericCols.includes(c));

  if (dateCol && numericCols.length >= 1) return "line";
  if (numericCols.length === 2 && nonNumericCols.length === 0) return "scatter";
  // Exactly one category column drives pie/bar off its first numeric
  // column regardless of how many other numeric columns tag along (e.g. a
  // raw count alongside a computed percent) — those extra columns stay
  // visible in the SQL/table, they just don't turn this into a confusing
  // multi-series chart mixing counts and percentages on one axis.
  if (nonNumericCols.length === 1 && numericCols.length >= 1) {
    return rows.length <= 8 ? "pie" : "bar";
  }
  if (nonNumericCols.length >= 1 && numericCols.length >= 1) return "bar";
  return "table";
}

function baseOption(): EChartsOption {
  return {
    backgroundColor: "transparent",
    textStyle: { color: COLORS.text, fontFamily: "var(--mono)" },
    grid: { left: 48, right: 24, top: 24, bottom: 48, containLabel: true },
    tooltip: {
      trigger: "axis",
      backgroundColor: COLORS.surface,
      borderColor: COLORS.border,
      textStyle: { color: COLORS.text, fontSize: 12 },
    },
  };
}

export function buildEChartsOption(chartType: ChartType, columns: string[], rows: Record<string, unknown>[]): EChartsOption | null {
  if (rows.length === 0 || columns.length < 2) return null;

  const dateCol = columns.find((c) => isDateLike(c, colValues(rows, c)));
  const numericCols = columns.filter((c) => c !== dateCol && isNumeric(colValues(rows, c)));
  const nonNumericCols = columns.filter((c) => c !== dateCol && !numericCols.includes(c));
  const categoryCol = nonNumericCols[0];

  if (chartType === "line") {
    const xCol = dateCol ?? categoryCol ?? columns[0];
    const seriesCols = numericCols.length > 0 ? numericCols : columns.filter((c) => c !== xCol);
    return {
      ...baseOption(),
      legend: seriesCols.length > 1 ? { textStyle: { color: COLORS.textDim, fontSize: 11 } } : undefined,
      xAxis: { type: "category", data: rows.map((r) => String(r[xCol])), axisLine: { lineStyle: { color: COLORS.border } } },
      yAxis: { type: "value", splitLine: { lineStyle: { color: COLORS.border } } },
      series: seriesCols.map((c, i) => ({
        name: c,
        type: "line",
        data: rows.map((r) => Number(r[c])),
        smooth: true,
        itemStyle: { color: COLORS.series[i % COLORS.series.length] },
      })),
    };
  }

  if (chartType === "bar") {
    const xCol = categoryCol ?? dateCol ?? columns[0];
    // Exactly one category column: chart just its primary numeric column
    // (matches the pie builder below) — extra numeric columns (e.g. a
    // computed percent alongside a raw count) stay in the SQL/table
    // instead of becoming a confusing mixed-scale multi-series bar.
    const seriesCols =
      nonNumericCols.length === 1 && numericCols.length > 0
        ? [numericCols[0]]
        : numericCols.length > 0
          ? numericCols
          : columns.filter((c) => c !== xCol);
    return {
      ...baseOption(),
      legend: seriesCols.length > 1 ? { textStyle: { color: COLORS.textDim, fontSize: 11 } } : undefined,
      xAxis: {
        type: "category",
        data: rows.map((r) => String(r[xCol])),
        axisLine: { lineStyle: { color: COLORS.border } },
        axisLabel: { color: COLORS.textDim, fontSize: 11, rotate: rows.length > 8 ? 30 : 0 },
      },
      yAxis: { type: "value", splitLine: { lineStyle: { color: COLORS.border } }, axisLabel: { color: COLORS.textDim, fontSize: 11 } },
      series: seriesCols.map((c, i) => ({
        name: c,
        type: "bar",
        data: rows.map((r) => Number(r[c])),
        itemStyle: { color: COLORS.series[i % COLORS.series.length] },
      })),
    };
  }

  if (chartType === "pie") {
    const labelCol = categoryCol ?? columns[0];
    const valueCol = numericCols[0] ?? columns[1];
    return {
      ...baseOption(),
      tooltip: { trigger: "item", backgroundColor: COLORS.surface, borderColor: COLORS.border, textStyle: { color: COLORS.text, fontSize: 12 } },
      legend: { orient: "vertical", right: 10, top: "middle", textStyle: { color: COLORS.textDim, fontSize: 11 } },
      series: [{
        type: "pie",
        radius: ["40%", "70%"],
        data: rows.map((r, i) => ({ name: String(r[labelCol]), value: Number(r[valueCol]), itemStyle: { color: COLORS.series[i % COLORS.series.length] } })),
        label: { color: COLORS.text, fontSize: 11 },
        itemStyle: { borderColor: COLORS.bg, borderWidth: 2 },
      }],
    };
  }

  if (chartType === "scatter") {
    const [xCol, yCol] = numericCols.length >= 2 ? numericCols : [columns[0], columns[1]];
    return {
      ...baseOption(),
      tooltip: { trigger: "item", backgroundColor: COLORS.surface, borderColor: COLORS.border, textStyle: { color: COLORS.text, fontSize: 12 } },
      xAxis: { type: "value", name: xCol, nameTextStyle: { color: COLORS.textDim }, splitLine: { lineStyle: { color: COLORS.border } }, axisLabel: { color: COLORS.textDim, fontSize: 11 } },
      yAxis: { type: "value", name: yCol, nameTextStyle: { color: COLORS.textDim }, splitLine: { lineStyle: { color: COLORS.border } }, axisLabel: { color: COLORS.textDim, fontSize: 11 } },
      series: [{
        type: "scatter",
        data: rows.map((r) => [Number(r[xCol]), Number(r[yCol])]),
        itemStyle: { color: COLORS.accent },
      }],
    };
  }

  return null;
}
