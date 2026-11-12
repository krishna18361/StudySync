import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

const ToastContext = createContext(null);

const ICONS = { success: "✓", error: "!", info: "i" };

let idSeq = 0;

/**
 * Lightweight toast system. Wrap the app in <ToastProvider> and call
 * `const toast = useToast()` anywhere below it.
 */
export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const timers = useRef({});

  const dismiss = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    if (timers.current[id]) {
      clearTimeout(timers.current[id]);
      delete timers.current[id];
    }
  }, []);

  const push = useCallback(
    (toast) => {
      const id = ++idSeq;
      const item = {
        id,
        type: toast.type || "info",
        title: toast.title || "",
        message: toast.message || "",
        duration: toast.duration ?? 4200,
      };
      setToasts((prev) => [...prev.slice(-3), item]);
      if (item.duration > 0) {
        timers.current[id] = setTimeout(() => dismiss(id), item.duration);
      }
      return id;
    },
    [dismiss]
  );

  useEffect(() => {
    const pending = timers.current;
    return () => {
      Object.values(pending).forEach(clearTimeout);
    };
  }, []);

  const value = useMemo(
    () => ({
      push,
      dismiss,
      success: (title, message, opts) => push({ type: "success", title, message, ...opts }),
      error: (title, message, opts) => push({ type: "error", title, message, duration: 6000, ...opts }),
      info: (title, message, opts) => push({ type: "info", title, message, ...opts }),
    }),
    [push, dismiss]
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast-stack" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast-${t.type}`}>
            <span className="toast-icon" aria-hidden="true">
              {ICONS[t.type] || ICONS.info}
            </span>
            <div className="toast-body">
              {t.title ? <strong className="toast-title">{t.title}</strong> : null}
              {t.message ? <span className="toast-msg">{t.message}</span> : null}
            </div>
            <button
              type="button"
              className="toast-close"
              onClick={() => dismiss(t.id)}
              aria-label="Dismiss notification"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within a ToastProvider");
  return ctx;
}
