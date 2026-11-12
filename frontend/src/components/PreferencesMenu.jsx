import { useEffect, useRef, useState } from "react";
import { usePreferences } from "../theme";

const THEMES = [
  { id: "light", label: "Light", icon: "☀️" },
  { id: "dark", label: "Dark", icon: "🌙" },
  { id: "system", label: "Auto", icon: "🖥️" },
];

const SCALES = [
  { id: "sm", label: "Small" },
  { id: "md", label: "Medium" },
  { id: "lg", label: "Large" },
];

const LEADINGS = [
  { id: "compact", label: "Compact" },
  { id: "comfortable", label: "Cozy" },
  { id: "relaxed", label: "Airy" },
];

const FONTS = [
  { id: "sans", label: "Sans" },
  { id: "serif", label: "Serif" },
];

function Segment({ options, value, onChange, ariaLabel }) {
  return (
    <div className="seg" role="group" aria-label={ariaLabel}>
      {options.map((opt) => (
        <button
          key={opt.id}
          type="button"
          className={`seg-btn ${value === opt.id ? "on" : ""}`}
          aria-pressed={value === opt.id}
          onClick={() => onChange(opt.id)}
        >
          {opt.icon ? <span aria-hidden="true">{opt.icon}</span> : null}
          {opt.label}
        </button>
      ))}
    </div>
  );
}

/** Header control for appearance (dark mode) and reading preferences. */
export default function PreferencesMenu() {
  const { theme, setTheme, reading, updateReading, resetReading } = usePreferences();
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    function onDocClick(event) {
      if (wrapRef.current && !wrapRef.current.contains(event.target)) setOpen(false);
    }
    function onEsc(event) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onEsc);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onEsc);
    };
  }, [open]);

  return (
    <div className="pref-wrap" ref={wrapRef}>
      <button
        type="button"
        className={`pref-trigger ${open ? "on" : ""}`}
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="dialog"
        title="Appearance & reading preferences"
      >
        <span aria-hidden="true">🎨</span> Reading
      </button>

      {open ? (
        <div className="pref-panel" role="dialog" aria-label="Appearance and reading preferences">
          <div className="pref-group">
            <span className="pref-label">Appearance</span>
            <Segment options={THEMES} value={theme} onChange={setTheme} ariaLabel="Colour theme" />
          </div>

          <div className="pref-divider" />

          <div className="pref-group">
            <span className="pref-label">Text size</span>
            <Segment
              options={SCALES}
              value={reading.scale}
              onChange={(scale) => updateReading({ scale })}
              ariaLabel="Text size"
            />
          </div>

          <div className="pref-group">
            <span className="pref-label">Line spacing</span>
            <Segment
              options={LEADINGS}
              value={reading.leading}
              onChange={(leading) => updateReading({ leading })}
              ariaLabel="Line spacing"
            />
          </div>

          <div className="pref-group">
            <span className="pref-label">Reading font</span>
            <Segment
              options={FONTS}
              value={reading.font}
              onChange={(font) => updateReading({ font })}
              ariaLabel="Reading font"
            />
          </div>

          <button type="button" className="linkish pref-reset" onClick={resetReading}>
            Reset to defaults
          </button>
        </div>
      ) : null}
    </div>
  );
}
