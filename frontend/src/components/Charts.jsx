import { useState } from "react";

// Theme-aware colours — resolved from the design tokens so charts follow
// light / dark mode automatically.
const ACCENT = "var(--navy)"; // navy blue (primary)
const SUCCESS = "var(--navy-deep)"; // navy (deep)
const WEAK = "var(--weak)"; // terracotta (deep)
const NAVY = "var(--ink)"; // navy-charcoal (ink)

function asPct(value) {
  return Math.round(Math.max(0, Math.min(1, value || 0)) * 100);
}

function fmtDate(value) {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  return `${d.toLocaleDateString(undefined, { month: "short", day: "numeric" })} · ${d.toLocaleTimeString(
    undefined,
    { hour: "2-digit", minute: "2-digit" }
  )}`;
}

/**
 * Interactive line/area chart showing quiz score progression over attempts.
 */
export function ScoreTrendChart({ history }) {
  const [hover, setHover] = useState(null);
  const data = history || [];

  if (data.length === 0) {
    return <p className="muted chart-empty">Take a quiz to see your score trend over time.</p>;
  }

  const W = 720;
  const H = 280;
  const padL = 48;
  const padR = 24;
  const padT = 22;
  const padB = 48;
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;
  const n = data.length;

  const xAt = (i) => (n === 1 ? padL + innerW / 2 : padL + (innerW * i) / (n - 1));
  const yAt = (s) => padT + innerH * (1 - Math.max(0, Math.min(1, s)));

  const pts = data.map((item, i) => ({ x: xAt(i), y: yAt(item.score), item, i }));
  const linePath = pts.map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
  const baseline = (padT + innerH).toFixed(1);
  const areaPath = `${linePath} L${pts[pts.length - 1].x.toFixed(1)},${baseline} L${pts[0].x.toFixed(1)},${baseline} Z`;
  const gridVals = [0, 0.25, 0.5, 0.75, 1];
  const active = hover !== null ? pts[hover] : null;

  return (
    <div className="chart-wrap">
      <svg viewBox={`0 0 ${W} ${H}`} className="chart-svg" role="img" aria-label="Quiz score trend">
        <defs>
          <linearGradient id="scoreAreaFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={ACCENT} stopOpacity="0.30" />
            <stop offset="100%" stopColor={ACCENT} stopOpacity="0.02" />
          </linearGradient>
        </defs>

        {gridVals.map((g) => {
          const y = yAt(g);
          return (
            <g key={g}>
              <line x1={padL} y1={y} x2={W - padR} y2={y} className="chart-grid" />
              <text x={padL - 10} y={y + 4} textAnchor="end" className="chart-axis-label">
                {Math.round(g * 100)}%
              </text>
            </g>
          );
        })}

        {active ? (
          <line x1={active.x} y1={padT} x2={active.x} y2={padT + innerH} className="chart-crosshair" />
        ) : null}

        <path d={areaPath} fill="url(#scoreAreaFill)" />
        <path d={linePath} className="chart-line" fill="none" />

        {pts.map((p) => (
          <g key={p.i}>
            <circle
              cx={p.x}
              cy={p.y}
              r={hover === p.i ? 7.5 : 5}
              className="chart-dot"
              fill={p.item.score >= 0.6 ? SUCCESS : WEAK}
              onMouseEnter={() => setHover(p.i)}
              onMouseLeave={() => setHover(null)}
            />
            <text x={p.x} y={H - padB + 24} textAnchor="middle" className="chart-axis-label">
              #{p.i + 1}
            </text>
          </g>
        ))}
      </svg>

      {active ? (
        <div
          className="chart-tooltip"
          style={{ left: `${(active.x / W) * 100}%`, top: `${(active.y / H) * 100}%` }}
        >
          <strong style={{ color: active.item.score >= 0.6 ? SUCCESS : WEAK }}>
            {asPct(active.item.score)}%
          </strong>
          <span>Difficulty: {active.item.difficulty}</span>
          <span>{fmtDate(active.item.created_at)}</span>
        </div>
      ) : null}
    </div>
  );
}

/**
 * Topic-wise Performance — interactive horizontal bars of accuracy per topic,
 * strongest first.
 */
export function TopicBars({ topics }) {
  const [hover, setHover] = useState(null);
  const data = [...(topics || [])]
    .filter((t) => (t.total || 0) > 0)
    .sort((a, b) => (b.accuracy || 0) - (a.accuracy || 0));
  if (data.length === 0) {
    return <p className="muted chart-empty">No topic data yet.</p>;
  }
  return (
    <div className="topic-bars">
      {data.map((t, i) => {
        const p = asPct(t.accuracy);
        const weak = t.accuracy < 0.6;
        return (
          <div
            key={t.topic}
            className="topic-bar-row"
            onMouseEnter={() => setHover(i)}
            onMouseLeave={() => setHover(null)}
          >
            <div className="topic-bar-head">
              <span className="topic-name">{t.topic}</span>
              <span className="topic-score" style={{ color: weak ? WEAK : SUCCESS }}>
                {t.correct}/{t.total} · {p}%
              </span>
            </div>
            <div className="topic-bar-track">
              <div
                className="topic-bar-fill"
                style={{
                  width: `${Math.max(p, 2)}%`,
                  background: weak ? WEAK : SUCCESS,
                  opacity: hover === null || hover === i ? 1 : 0.55,
                }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

// Canonical skill order + display labels (matches the backend skill keys).
const SKILL_ORDER = ["conceptual", "recall", "application", "problem_solving"];
const SKILL_LABELS = {
  conceptual: "Conceptual Understanding",
  recall: "Recall",
  application: "Application",
  problem_solving: "Problem Solving",
};

/**
 * Answer Analysis — stacked horizontal bars comparing correct / incorrect /
 * skipped answers for each topic.
 */
export function AnswerAnalysisChart({ topics }) {
  const data = [...(topics || [])]
    .filter((t) => (t.total || 0) > 0)
    .sort((a, b) => (b.total || 0) - (a.total || 0));

  if (data.length === 0) {
    return <p className="muted chart-empty">Answer analysis appears after you submit a quiz.</p>;
  }

  return (
    <div className="answer-analysis">
      <div className="stack-legend">
        <span>
          <i className="sw sw-correct" /> Correct
        </span>
        <span>
          <i className="sw sw-incorrect" /> Incorrect
        </span>
        <span>
          <i className="sw sw-skipped" /> Skipped
        </span>
      </div>

      {data.map((t) => {
        const skipped = t.skipped || 0;
        const incorrect = Math.max(0, t.total - t.correct - skipped);
        const cp = (t.correct / t.total) * 100;
        const ip = (incorrect / t.total) * 100;
        const sp = (skipped / t.total) * 100;
        return (
          <div key={t.topic} className="stack-row">
            <div className="stack-head">
              <span className="topic-name">{t.topic}</span>
              <span className="stack-counts muted">
                <b className="c-correct">{t.correct}✓</b>
                <b className="c-incorrect">{incorrect}✗</b>
                {skipped ? <b className="c-skipped">{skipped}–</b> : null}
              </span>
            </div>
            <div
              className="stack-track"
              role="img"
              aria-label={`${t.topic}: ${Math.round(cp)}% correct, ${Math.round(
                ip
              )}% incorrect, ${Math.round(sp)}% skipped`}
            >
              {cp > 0 ? <div className="stack-seg seg-correct" style={{ width: `${cp}%` }} /> : null}
              {ip > 0 ? <div className="stack-seg seg-incorrect" style={{ width: `${ip}%` }} /> : null}
              {sp > 0 ? <div className="stack-seg seg-skipped" style={{ width: `${sp}%` }} /> : null}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/**
 * Skill Mastery — radar chart across conceptual understanding, recall,
 * application and problem solving. Falls back to bars with fewer than 3 skills.
 */
export function SkillRadarChart({ skills }) {
  const [hover, setHover] = useState(null);

  const byKey = {};
  (skills || []).forEach((s) => {
    byKey[s.skill] = s;
  });
  const data = SKILL_ORDER.filter((k) => byKey[k] && byKey[k].total > 0).map((k) => ({
    key: k,
    label: SKILL_LABELS[k] || k,
    accuracy: byKey[k].accuracy,
    correct: byKey[k].correct,
    total: byKey[k].total,
  }));

  if (data.length === 0) {
    return (
      <p className="muted chart-empty">
        Skill mastery is measured from your quiz answers — take a quiz to begin.
      </p>
    );
  }

  if (data.length < 3) {
    return (
      <div className="topic-bars">
        {data.map((s) => {
          const p = asPct(s.accuracy);
          const weak = s.accuracy < 0.6;
          return (
            <div key={s.key} className="topic-bar-row">
              <div className="topic-bar-head">
                <span className="topic-name">{s.label}</span>
                <span className="topic-score" style={{ color: weak ? WEAK : SUCCESS }}>
                  {s.correct}/{s.total} · {p}%
                </span>
              </div>
              <div className="topic-bar-track">
                <div
                  className="topic-bar-fill"
                  style={{ width: `${Math.max(p, 2)}%`, background: weak ? WEAK : SUCCESS }}
                />
              </div>
            </div>
          );
        })}
      </div>
    );
  }

  const W = 480;
  const H = 380;
  const cx = W / 2;
  const cy = H / 2 + 6;
  const R = 120;
  const n = data.length;
  const angleAt = (i) => -Math.PI / 2 + (2 * Math.PI * i) / n;
  const pointAt = (i, r) => [cx + r * Math.cos(angleAt(i)), cy + r * Math.sin(angleAt(i))];
  const levels = [0.25, 0.5, 0.75, 1];
  const ringPath = (r) => data.map((_, i) => pointAt(i, r).map((v) => v.toFixed(1)).join(",")).join(" ");
  const dataPath = data
    .map((s, i) => pointAt(i, Math.max(0.05, Math.min(1, s.accuracy)) * R).map((v) => v.toFixed(1)).join(","))
    .join(" ");
  const active = hover !== null ? hover : null;

  return (
    <div className="chart-wrap">
      <svg viewBox={`0 0 ${W} ${H}`} className="chart-svg" role="img" aria-label="Skill mastery radar">
        {levels.map((lvl) => (
          <polygon key={lvl} points={ringPath(lvl * R)} className="chart-ring" />
        ))}
        {data.map((s, i) => {
          const [ex, ey] = pointAt(i, R);
          return <line key={s.key} x1={cx} y1={cy} x2={ex} y2={ey} className="chart-grid" />;
        })}

        <polygon points={dataPath} className="radar-area" />

        {data.map((s, i) => {
          const r = Math.max(0.05, Math.min(1, s.accuracy)) * R;
          const [px, py] = pointAt(i, r);
          const [lx, ly] = pointAt(i, R + 30);
          const anchor = Math.abs(lx - cx) < 8 ? "middle" : lx > cx ? "start" : "end";
          return (
            <g key={s.key}>
              <circle
                cx={px}
                cy={py}
                r={hover === i ? 7 : 5}
                className="chart-dot"
                fill={s.accuracy >= 0.6 ? SUCCESS : WEAK}
                onMouseEnter={() => setHover(i)}
                onMouseLeave={() => setHover(null)}
              />
              <text x={lx} y={ly + 4} textAnchor={anchor} className="chart-axis-label radar-label">
                {s.label}
              </text>
            </g>
          );
        })}
      </svg>

      {active !== null && data[active] ? (
        <div className="chart-tooltip chart-tooltip-center">
          <strong style={{ color: data[active].accuracy >= 0.6 ? SUCCESS : WEAK }}>
            {asPct(data[active].accuracy)}%
          </strong>
          <span>{data[active].label}</span>
          <span>
            {data[active].correct}/{data[active].total} correct
          </span>
        </div>
      ) : null}
    </div>
  );
}

export const CHART_COLORS = { ACCENT, SUCCESS, WEAK, NAVY };
