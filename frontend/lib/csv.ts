/** Client-side CSV export — no backend endpoint, the data's already in the
 * browser (a finished query/chart result), so round-tripping it through the
 * server would just be slower for no benefit. */

/** Turns a question/title into a safe, short filename base for a
 * download — shared by CSV and PNG exports so a chart/result's filename
 * matches what it's actually about instead of a fixed generic name. */
export function filenameFor(text: string): string {
  return text.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60) || "table-lens";
}

function escapeCell(v: unknown): string {
  if (v === null || v === undefined) return "";
  const s = String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

/** Builds a CSV string from column order + row objects and triggers a
 * browser download via a temporary object URL. */
export function downloadCsv(filename: string, columns: string[], rows: Record<string, unknown>[]): void {
  const lines = [columns.map(escapeCell).join(",")];
  for (const row of rows) {
    lines.push(columns.map((c) => escapeCell(row[c])).join(","));
  }
  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename.endsWith(".csv") ? filename : `${filename}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
