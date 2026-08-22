"use client";

export default function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "confirm",
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  if (!open) return null;
  return (
    <div style={styles.overlay} onClick={onCancel}>
      <div style={styles.box} onClick={(e) => e.stopPropagation()}>
        <div style={styles.title}>{title}</div>
        <div style={styles.message}>{message}</div>
        <div style={styles.actions}>
          <button style={styles.cancelButton} onClick={onCancel}>cancel</button>
          <button style={styles.confirmButton} onClick={onConfirm}>{confirmLabel}</button>
        </div>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  overlay: {
    position: "fixed",
    inset: 0,
    background: "rgba(0,0,0,0.6)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 100,
  },
  box: {
    background: "var(--surface)",
    border: "1px solid var(--border-strong)",
    borderRadius: 2,
    padding: "24px 28px",
    maxWidth: 380,
    width: "90%",
  },
  title: {
    fontSize: 14,
    color: "var(--text)",
    fontWeight: 600,
    marginBottom: 10,
  },
  message: {
    fontSize: 13,
    color: "var(--text-dim)",
    lineHeight: 1.5,
    marginBottom: 20,
  },
  actions: {
    display: "flex",
    justifyContent: "flex-end",
    gap: 10,
  },
  cancelButton: {
    background: "transparent",
    border: "1px solid var(--border)",
    color: "var(--text-dim)",
    padding: "8px 16px",
    fontFamily: "var(--mono)",
    fontSize: 12,
    cursor: "pointer",
    borderRadius: 2,
  },
  confirmButton: {
    background: "transparent",
    border: "1px solid var(--accent)",
    color: "var(--accent)",
    padding: "8px 16px",
    fontFamily: "var(--mono)",
    fontSize: 12,
    cursor: "pointer",
    borderRadius: 2,
  },
};
