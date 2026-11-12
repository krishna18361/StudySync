import { useMemo, useState } from "react";
import Accordion from "./Accordion";

/* ------------------------------------------------------------------ */
/* Lightweight markdown helpers (headings, bold, bullet / ordered lists) */
/* ------------------------------------------------------------------ */

function renderInline(text) {
  const parts = [];
  const regex = /\*\*(.+?)\*\*/g;
  let last = 0;
  let key = 0;
  let match;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > last) parts.push(text.slice(last, match.index));
    parts.push(<strong key={key++}>{match[1]}</strong>);
    last = match.index + match[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts.length ? parts : text;
}

function parseBlocks(markdown) {
  const lines = (markdown || "").split(/\r?\n/);
  const out = [];
  let para = [];
  let list = null;
  let key = 0;

  const flushPara = () => {
    if (para.length) {
      out.push(
        <p key={key++} className="md-p">
          {renderInline(para.join(" "))}
        </p>
      );
      para = [];
    }
  };
  const flushList = () => {
    if (list) {
      const Tag = list.ordered ? "ol" : "ul";
      out.push(
        <Tag key={key++} className="md-list">
          {list.items.map((item, i) => (
            <li key={i}>{renderInline(item)}</li>
          ))}
        </Tag>
      );
      list = null;
    }
  };

  for (const raw of lines) {
    const line = raw.replace(/\s+$/, "");
    const heading = line.match(/^(#{1,6})\s+(.*)$/);
    if (heading) {
      flushPara();
      flushList();
      out.push(
        <h5 key={key++} className="md-h">
          {renderInline(heading[2].trim())}
        </h5>
      );
      continue;
    }
    const bullet = line.match(/^\s*[-*•]\s+(.*)$/);
    if (bullet) {
      flushPara();
      if (!list || list.ordered) {
        flushList();
        list = { ordered: false, items: [] };
      }
      list.items.push(bullet[1]);
      continue;
    }
    const ordered = line.match(/^\s*\d+[.)]\s+(.*)$/);
    if (ordered) {
      flushPara();
      if (!list || !list.ordered) {
        flushList();
        list = { ordered: true, items: [] };
      }
      list.items.push(ordered[1]);
      continue;
    }
    if (!line.trim()) {
      flushPara();
      flushList();
      continue;
    }
    para.push(line.trim());
  }
  flushPara();
  flushList();
  return out;
}

export function MiniMarkdown({ text }) {
  const blocks = useMemo(() => parseBlocks(text), [text]);
  if (!blocks.length) return null;
  return <div className="md">{blocks}</div>;
}

/* ------------------------------------------------------------------ */
/* Derive the Summary sub-sections from the existing summary payload   */
/* ------------------------------------------------------------------ */

function toText(value) {
  if (value == null) return "";
  return String(value).trim();
}

function buildOverview(summary) {
  const concepts = (summary.key_concepts || []).map(toText).filter(Boolean);
  const definitions = summary.definitions || [];
  const points = (summary.important_points || []).map(toText).filter(Boolean);
  const examples = summary.examples || [];

  const lead = concepts.slice(0, 4).join(", ");
  const sentence = `This study material covers ${concepts.length || "several"} key concepts${
    lead ? `, including ${lead}` : ""
  }. It distils ${definitions.length} definitions and ${points.length} high-yield points${
    examples.length ? `, backed by ${examples.length} worked examples` : ""
  } — organised below for fast, focused revision.`;

  const firstPara = (summary.exam_notes || "")
    .split(/\n\s*\n/)
    .map((part) => part.trim())
    .find((part) => part && !part.startsWith("#") && !part.startsWith("-"));

  return { sentence, firstPara };
}

function buildKeywords(summary) {
  const set = new Set();
  (summary.definitions || []).forEach((item) => {
    const term = toText(item?.term);
    if (term) set.add(term);
  });
  (summary.key_concepts || []).forEach((concept) => {
    const text = toText(concept);
    if (text) set.add(text);
  });
  return [...set].slice(0, 32);
}

function parseChapters(examNotes) {
  const lines = (examNotes || "").split(/\r?\n/);
  const chapters = [];
  let current = null;

  for (const line of lines) {
    const heading = line.match(/^(#{2,4})\s+(.*)$/);
    if (heading) {
      current = { title: heading[2].trim(), body: [] };
      chapters.push(current);
    } else if (current) {
      current.body.push(line);
    } else if (line.trim()) {
      current = { title: "Overview", body: [] };
      chapters.push(current);
      current.body.push(line);
    }
  }

  return chapters
    .map((chapter) => ({ title: chapter.title, body: chapter.body.join("\n").trim() }))
    .filter((chapter) => chapter.body);
}

/* ------------------------------------------------------------------ */
/* Compact, expandable dictionary row                                  */
/* ------------------------------------------------------------------ */

function DictionaryRow({ term, definition, defaultOpen }) {
  const [open, setOpen] = useState(Boolean(defaultOpen));
  return (
    <div className={`dict-row ${open ? "open" : ""}`}>
      <button type="button" className="dict-head" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <span className="dict-term">{term || "Term"}</span>
        <span className="dict-chevron" aria-hidden="true">
          ▾
        </span>
      </button>
      <div className="dict-body">
        <div className="dict-clip">
          <p className="dict-def">{definition || "No definition provided."}</p>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Main component                                                      */
/* ------------------------------------------------------------------ */

export default function SummarySections({ summary, active, onRegenerate }) {
  const concepts = (summary.key_concepts || []).map(toText).filter(Boolean);
  const definitions = (summary.definitions || []).filter((item) => item && (item.term || item.definition));
  const points = (summary.important_points || []).map(toText).filter(Boolean);
  const examples = (summary.examples || []).filter((item) => item && (item.concept || item.example));
  const chapters = useMemo(() => parseChapters(summary.exam_notes), [summary.exam_notes]);
  const keywords = useMemo(() => buildKeywords(summary), [summary]);
  const overview = useMemo(() => buildOverview(summary), [summary]);

  const stats = [
    { label: "Key Concepts", value: concepts.length },
    { label: "Definitions", value: definitions.length },
    { label: "Important Points", value: points.length },
    { label: "Examples", value: examples.length },
    { label: "Chapters", value: chapters.length },
  ];

  return (
    <div className="summary-sections">
      <div className="summary-toolbar">
        <div className="summary-file">
          <span className="summary-file-icon" aria-hidden="true">📄</span>
          <div>
            <strong>{active?.filename || "Document"}</strong>
            <span className="muted">AI-structured study material · expand any section to dive in</span>
          </div>
        </div>
        <button className="ghost-btn" onClick={onRegenerate} title="Re-run AI summarization on this document">
          🔄 Regenerate
        </button>
      </div>

      {/* 1. Document Overview */}
      <Accordion icon="🧭" title="Document Overview" subtitle="What this material is about" defaultOpen>
        <p className="overview-lead">{overview.sentence}</p>
        {overview.firstPara ? <p className="overview-para">{overview.firstPara}</p> : null}
        <div className="overview-stats">
          {stats.map((stat) => (
            <div key={stat.label} className="overview-stat">
              <span className="overview-stat-value">{stat.value}</span>
              <span className="overview-stat-label">{stat.label}</span>
            </div>
          ))}
        </div>
      </Accordion>

      {/* 2. Key Concepts */}
      {concepts.length > 0 ? (
        <Accordion icon="🔑" title="Key Concepts" count={concepts.length} subtitle="Core ideas to master" defaultOpen>
          <div className="concept-tags">
            {concepts.map((concept, i) => (
              <span key={i} className="concept-tag">
                {concept}
              </span>
            ))}
          </div>
        </Accordion>
      ) : null}

      {/* 3. Important Points */}
      {points.length > 0 ? (
        <Accordion icon="📌" title="Important Points" count={points.length} subtitle="Rules, formulas & takeaways">
          <ul className="bullet-points">
            {points.map((point, i) => (
              <li key={i}>{point}</li>
            ))}
          </ul>
        </Accordion>
      ) : null}

      {/* 4. Definitions Dictionary */}
      {definitions.length > 0 ? (
        <Accordion
          icon="📖"
          title="Definitions Dictionary"
          count={definitions.length}
          subtitle="Tap a term to reveal its definition"
        >
          <div className="dict-list">
            {definitions.map((item, i) => (
              <DictionaryRow
                key={i}
                term={item.term}
                definition={item.definition}
                defaultOpen={i === 0}
              />
            ))}
          </div>
        </Accordion>
      ) : null}

      {/* 5. Chapter-wise Summary */}
      {chapters.length > 0 ? (
        <Accordion
          icon="🗂️"
          title="Chapter-wise Summary"
          count={chapters.length}
          subtitle="Section by section revision notes"
        >
          <div className="chapter-list">
            {chapters.map((chapter, i) => (
              <Accordion
                key={i}
                icon="§"
                title={chapter.title || `Chapter ${i + 1}`}
                accent="oak"
              >
                <MiniMarkdown text={chapter.body} />
              </Accordion>
            ))}
          </div>
        </Accordion>
      ) : null}

      {/* 6. Keywords */}
      {keywords.length > 0 ? (
        <Accordion icon="🏷️" title="Keywords" count={keywords.length} subtitle="Glossary & search terms">
          <div className="keyword-cloud">
            {keywords.map((word, i) => (
              <span key={i} className="keyword-chip">
                {word}
              </span>
            ))}
          </div>
        </Accordion>
      ) : null}

      {/* Concrete examples (kept, now collapsible) */}
      {examples.length > 0 ? (
        <Accordion icon="💡" title="Concrete Examples & Scenarios" count={examples.length}>
          <div className="examples-grid">
            {examples.map((example, i) => (
              <div key={i} className="example-card">
                <strong>{example.concept}</strong>
                <p>{example.example}</p>
              </div>
            ))}
          </div>
        </Accordion>
      ) : null}
    </div>
  );
}
