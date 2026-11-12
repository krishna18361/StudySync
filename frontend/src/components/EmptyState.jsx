/**
 * Shared empty / zero-data state used across the workspace.
 * Keeps the icon, heading, copy and call-to-action visually consistent.
 */
export default function EmptyState({ icon = "📚", title, message, action, compact = false, children }) {
  return (
    <div className={`empty-state ${compact ? "compact" : ""}`}>
      <div className="empty-icon" aria-hidden="true">
        {icon}
      </div>
      {title ? <h2>{title}</h2> : null}
      {message ? <p className="muted">{message}</p> : null}
      {children}
      {action}
    </div>
  );
}
