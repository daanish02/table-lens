/** Client-side CSV export — no backend endpoint, the data's already in the
 * browser (a finished query/chart result), so round-tripping it through the
 * server would just be slower for no benefit. */

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
