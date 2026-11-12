import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import EmptyState from "./EmptyState";
import { useToast } from "./Toast";

function parseAnswer(answer) {
  if (!answer) return [];
  const sections = [];
  const regex = /###\s+(.*)\n([\s\S]*?)(?=###\s+|$)/g;
  let match;
  while ((match = regex.exec(answer)) !== null) {
    sections.push({ title: match[1].trim(), content: match[2].trim() });
  }
  if (sections.length === 0) {
    sections.push({ title: "Answer", content: answer.trim() });
  }
  return sections;
}

function newId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

/** Reveals text character-by-character to mimic streaming output. */
function Typewriter({ text, delay = 0 }) {
  const [shown, setShown] = useState("");
  const [done, setDone] = useState(false);

  useEffect(() => {
    let interval;
    let i = 0;
    const total = text.length;
    const step = Math.max(1, Math.ceil(total / 130));
    const start = setTimeout(() => {
      interval = setInterval(() => {
        i += step;
        if (i >= total) {
          setShown(text);
          setDone(true);
          clearInterval(interval);
        } else {
          setShown(text.slice(0, i));
        }
      }, 16);
    }, delay);
    return () => {
      clearTimeout(start);
      if (interval) clearInterval(interval);
    };
  }, [text, delay]);

  return (
    <span>
      {shown}
      {!done ? <span className="tw-caret" aria-hidden="true" /> : null}
    </span>
  );
}

function ThinkingDots({ label }) {
  return (
    <div className="thinking">
      <span className="thinking-avatar" aria-hidden="true">
        ✨
      </span>
      <div className="thinking-body">
        <span className="thinking-label">{label || "StudySync is thinking"}</span>
        <span className="thinking-dots" aria-hidden="true">
          <i />
          <i />
          <i />
        </span>
      </div>
    </div>
  );
}

function loadMessages(storageKey) {
  if (!storageKey) return [];
  try {
    const raw = localStorage.getItem(storageKey);
    const parsed = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(parsed)) return [];
    return parsed.map((turn) => ({ ...turn, fresh: false }));
  } catch {
    return [];
  }
}

export default function DoubtChat({ activeId, summary }) {
  const toast = useToast();
  const storageKey = activeId ? `studysync_chat_${activeId}` : null;
  const [messages, setMessages] = useState(() => loadMessages(storageKey));
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const [pendingId, setPendingId] = useState(null);
  const bottomRef = useRef(null);

  // Persist history (without the transient "fresh" flag).
  useEffect(() => {
    if (!storageKey) return;
    try {
      const persisted = messages.map(({ fresh, ...rest }) => rest);
      localStorage.setItem(storageKey, JSON.stringify(persisted));
    } catch {
      /* storage full or unavailable — ignore */
    }
  }, [messages, storageKey]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, pending]);

  const suggestions = useMemo(() => {
    const concepts = (summary?.key_concepts || []).slice(0, 3);
    const derived = concepts.map((concept) => `Explain "${concept}" with a simple example`);
    const fallback = [
      "What are the main concepts covered in this document?",
      "Give me an analogy to understand this better",
      "Summarize the most important points for exam revision",
    ];
    return [...derived, ...fallback].slice(0, 5);
  }, [summary]);

  function buildHistory(excludeId) {
    return messages
      .filter((turn) => turn.id !== excludeId)
      .flatMap((turn) => [
        { role: "user", content: turn.q },
        { role: "assistant", content: turn.a || "" },
      ])
      .filter((item) => item.content);
  }

  async function ask(queryText, targetId = null) {
    const text = queryText.trim();
    if (!activeId || !text || pending) return;
    setPending(true);
    setPendingId(targetId);
    try {
      const res = await api.ask(activeId, text, buildHistory(targetId));
      if (targetId) {
        setMessages((prev) =>
          prev.map((turn) =>
            turn.id === targetId
              ? {
                  ...turn,
                  a: res.answer,
                  sources: res.sources || [],
                  fresh: true,
                  rev: (turn.rev || 0) + 1,
                }
              : turn
          )
        );
      } else {
        setMessages((prev) => [
          ...prev,
          {
            id: newId(),
            q: text,
            a: res.answer,
            sources: res.sources || [],
            fresh: true,
            feedback: null,
            rev: 0,
          },
        ]);
      }
    } catch (err) {
      toast.error(
        "Could not answer that",
        (err?.message || "").toLowerCase().includes("failed to fetch")
          ? "Could not reach the backend. Make sure the FastAPI server is running."
          : err?.message || "The AI tutor ran into a problem."
      );
    } finally {
      setPending(false);
      setPendingId(null);
    }
  }

  function onSubmit(event) {
    event.preventDefault();
    if (!input.trim()) return;
    const text = input;
    setInput("");
    ask(text, null);
  }

  function onSuggestion(text) {
    ask(text, null);
  }

  async function copyAnswer(turn) {
    try {
      await navigator.clipboard.writeText(turn.a || "");
      toast.success("Copied", "The answer was copied to your clipboard.");
    } catch {
      toast.error("Copy failed", "Your browser blocked clipboard access.");
    }
  }

  function setFeedback(turnId, value) {
    setMessages((prev) =>
      prev.map((turn) => (turn.id === turnId ? { ...turn, feedback: value } : turn))
    );
    toast.info(
      value === "up" ? "Thanks for the feedback!" : "Noted — we'll improve this answer.",
      value === "up" ? "Glad this was helpful." : "Your feedback helps tune future responses."
    );
  }

  function clearChat() {
    if (!messages.length) return;
    if (!window.confirm("Clear this conversation history?")) return;
    setMessages([]);
    if (storageKey) localStorage.removeItem(storageKey);
    toast.info("Chat cleared", "You can start a fresh conversation.");
  }

  return (
    <div className="doubt-chat">
      <div className="chat-topbar">
        <div className="chat-topbar-info">
          <span className="chat-topbar-icon" aria-hidden="true">
            🤖
          </span>
          <div>
            <strong>Ask AI — Doubt Solver</strong>
            <span className="muted">Grounded in your uploaded notes</span>
          </div>
        </div>
        {messages.length > 0 ? (
          <button className="ghost-btn" onClick={clearChat}>
            🗑 Clear chat
          </button>
        ) : null}
      </div>

      {suggestions.length > 0 ? (
        <div className="suggestions-bar">
          <span className="suggestions-label">Suggested prompts</span>
          {suggestions.map((text, i) => (
            <button
              key={i}
              className="suggestion-chip"
              disabled={pending}
              onClick={() => onSuggestion(text)}
            >
              {text}
            </button>
          ))}
        </div>
      ) : null}

      <div className="chat-container">
        {messages.length === 0 && !pending ? (
          <EmptyState
            compact
            icon="💬"
            title="Ask anything from your notes"
            message="The Doubt Agent answers strictly from your uploaded material — with simple explanations, analogies, concrete examples, and the source passages it used."
          />
        ) : null}

        {messages.map((turn) => (
          <article key={turn.id} className="chat-bubble">
            <div className="chat-question">
              <span className="chat-avatar user" aria-hidden="true">
                Q
              </span>
              <span>{turn.q}</span>
            </div>

            <div className="chat-answer">
              {pending && pendingId === turn.id ? (
                <ThinkingDots label="Re-generating answer" />
              ) : (
                <>
                  {parseAnswer(turn.a).map((section, idx) => (
                    <div key={`${turn.rev || 0}-${idx}`} className="doubt-card card">
                      <h3>{section.title}</h3>
                      <p>
                        {turn.fresh ? (
                          <Typewriter text={section.content} delay={idx * 150} />
                        ) : (
                          section.content
                        )}
                      </p>
                    </div>
                  ))}

                  <div className="chat-actions">
                    <button className="icon-btn" title="Copy answer" onClick={() => copyAnswer(turn)}>
                      📋 Copy
                    </button>
                    <button
                      className="icon-btn"
                      title="Regenerate answer"
                      disabled={pending}
                      onClick={() => ask(turn.q, turn.id)}
                    >
                      🔄 Regenerate
                    </button>
                    <span className="feedback-group">
                      <button
                        className={`icon-btn ${turn.feedback === "up" ? "active" : ""}`}
                        title="Helpful"
                        onClick={() => setFeedback(turn.id, "up")}
                      >
                        👍
                      </button>
                      <button
                        className={`icon-btn ${turn.feedback === "down" ? "active" : ""}`}
                        title="Not helpful"
                        onClick={() => setFeedback(turn.id, "down")}
                      >
                        👎
                      </button>
                    </span>
                  </div>

                  {turn.sources?.length > 0 ? (
                    <details className="source-citations">
                      <summary>
                        📚 Source references from your notes ({turn.sources.length}{" "}
                        {turn.sources.length === 1 ? "passage" : "passages"})
                      </summary>
                      <div className="source-snippets">
                        {turn.sources.map((src, idx) => (
                          <div key={idx} className="snippet-box">
                            <span className="snippet-index">Passage {idx + 1}</span>
                            <p>{src}</p>
                          </div>
                        ))}
                      </div>
                    </details>
                  ) : null}
                </>
              )}
            </div>
          </article>
        ))}

        {pending && pendingId === null ? <ThinkingDots /> : null}
        <div ref={bottomRef} />
      </div>

      <form className="ask-form" onSubmit={onSubmit}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          maxLength={2000}
          placeholder="Ask any doubt from your notes (e.g., 'Explain Normalization with an example')..."
          disabled={!activeId || pending}
        />
        <button type="submit" disabled={!activeId || !input.trim() || pending}>
          {pending ? "Thinking…" : "Ask AI"}
        </button>
      </form>
      {!activeId ? (
        <p className="muted chat-hint">Select or upload a document to start asking questions.</p>
      ) : null}
    </div>
  );
}
