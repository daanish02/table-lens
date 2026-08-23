"use client";

import { useEffect, useRef } from "react";

/** Accessible confirm/cancel modal — focus-trapped, Escape-to-close, focus
 * restored to the trigger element on close. Renders nothing while !open. */
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
  const cancelRef = useRef<HTMLButtonElement>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);
  const triggerElementRef = useRef<Element | null>(null);

  useEffect(() => {
    if (!open) return;
    triggerElementRef.current = document.activeElement;
    cancelRef.current?.focus();

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        onCancel();
        return;
      }
      // Basic focus trap — only two focusable elements (cancel/confirm), so
      // Tab/Shift+Tab just needs to wrap between them instead of escaping
      // to whatever's behind the overlay.
      if (e.key === "Tab") {
        const first = cancelRef.current;
        const last = confirmRef.current;
        if (!first || !last) return;
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      // Restore focus to whatever opened the dialog, so keyboard users
      // don't lose their place after it closes.
      if (triggerElementRef.current instanceof HTMLElement) {
        triggerElementRef.current.focus();
      }
    };
  }, [open, onCancel]);

  if (!open) return null;
  return (
    <div style={styles.overlay} onClick={onCancel}>
      <div
        style={styles.box}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        aria-describedby="confirm-dialog-message"
      >
        <div id="confirm-dialog-title" style={styles.title}>{title}</div>
        <div id="confirm-dialog-message" style={styles.message}>{message}</div>
        <div style={styles.actions}>
          <button ref={cancelRef} style={styles.cancelButton} onClick={onCancel}>cancel</button>
          <button ref={confirmRef} style={styles.confirmButton} onClick={onConfirm}>{confirmLabel}</button>
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
