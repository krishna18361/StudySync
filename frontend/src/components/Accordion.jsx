import { useState } from "react";

/**
 * Reusable expandable section used across the workspace.
 * Smoothly animates open/close using the CSS grid rows technique.
 */
export default function Accordion({
  icon,
  title,
  count,
  subtitle,
  defaultOpen = false,
  accent = "navy",
  children,
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <section className={`acc acc-${accent} ${open ? "open" : ""}`}>
      <button
        type="button"
        className="acc-head"
        aria-expanded={open}
        onClick={() => setOpen((prev) => !prev)}
      >
        {icon ? <span className="acc-icon" aria-hidden="true">{icon}</span> : null}
        <span className="acc-title-wrap">
          <span className="acc-title">{title}</span>
          {subtitle ? <span className="acc-subtitle">{subtitle}</span> : null}
        </span>
        {count != null ? <span className="acc-count">{count}</span> : null}
        <span className="acc-chevron" aria-hidden="true">
          ▾
        </span>
      </button>
      <div className="acc-body">
        <div className="acc-clip">
          <div className="acc-pad">{children}</div>
        </div>
      </div>
    </section>
  );
}
