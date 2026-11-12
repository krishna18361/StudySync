import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, setToken } from "../api";
import {
  AnswerAnalysisChart,
  ScoreTrendChart,
  SkillRadarChart,
  TopicBars,
} from "../components/Charts";
import DoubtChat from "../components/DoubtChat";
import SummarySections from "../components/SummarySections";
import UploadDropzone from "../components/UploadDropzone";
import EmptyState from "../components/EmptyState";
import PreferencesMenu from "../components/PreferencesMenu";
import {
  DocListSkeleton,
  PerformanceSkeleton,
  QuizSkeleton,
  SummarySkeleton,
} from "../components/Skeleton";
import { useToast } from "../components/Toast";

const BACKEND_DOWN =
  "Could not reach the backend. Make sure FastAPI is running (uvicorn app.main:app --reload) and Ollama is started (ollama serve).";

// Seconds allowed per quiz question before the quiz auto-submits.
const SECONDS_PER_QUESTION = 75;

function fmtClock(totalSeconds) {
  const safe = Math.max(0, Math.floor(totalSeconds || 0));
  const m = Math.floor(safe / 60);
  const s = safe % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function fmtWhen(value) {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const TABS = [
  { id: "summary", label: "📑 Summary" },
  { id: "doubts", label: "💬 Ask AI" },
  { id: "quiz", label: "📝 Quiz" },
  { id: "performance", label: "📊 Performance" },
];

export default function Workspace() {
  const navigate = useNavigate();
  const toast = useToast();
  const [me, setMe] = useState(null);
  const [docs, setDocs] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [tab, setTab] = useState("summary");
  const [summary, setSummary] = useState(null);
  const [quiz, setQuiz] = useState(null);
  const [answers, setAnswers] = useState([]);
  const [result, setResult] = useState(null);
  const [perf, setPerf] = useState(null);
  const [coachAdvice, setCoachAdvice] = useState("");
  const [busy, setBusy] = useState("");
  const [docsLoading, setDocsLoading] = useState(true);
  const [perfLoading, setPerfLoading] = useState(false);
  const [showAssessment, setShowAssessment] = useState(false);
  const [quizStartedAt, setQuizStartedAt] = useState(null);
  const [quizElapsed, setQuizElapsed] = useState(null);
  const [nowTs, setNowTs] = useState(() => Date.now());
  const pollToken = useRef(0);
  const autoSubmitRef = useRef(false);
  const [assessmentForm, setAssessmentForm] = useState({
    learner_level: "beginner",
    learning_style: "analogy_and_examples",
    study_goals: "exam_prep",
    preferred_depth: "simplified",
  });

  const active = useMemo(() => docs.find((d) => d.id === activeId) || null, [docs, activeId]);

  // Derived performance insights for the Overview + Strengths & Weaknesses sections.
  const perfInsights = useMemo(() => {
    const topics = (perf?.topics || []).filter((t) => t.total > 0);
    const ranked = [...topics].sort((a, b) => b.accuracy - a.accuracy);
    const history = perf?.history || [];
    const first = history.length ? history[0].score : 0;
    const latest = history.length ? history[history.length - 1].score : 0;
    return {
      topicsAssessed: topics.length,
      best: ranked[0] || null,
      weakest: ranked.length > 1 ? ranked[ranked.length - 1] : null,
      improvement: history.length > 1 ? (latest - first) * 100 : 0,
    };
  }, [perf]);

  function notifyError(err, title) {
    const msg = err?.message || String(err);
    toast.error(title, msg.toLowerCase().includes("failed to fetch") ? BACKEND_DOWN : msg);
  }

  // --- Quiz timer ---------------------------------------------------------
  const quizActive = Boolean(quiz && quiz.status === "ready" && quiz.questions?.length && !result);
  const quizDuration = quiz?.questions?.length ? quiz.questions.length * SECONDS_PER_QUESTION : 0;
  const timeLeft =
    quizActive && quizStartedAt
      ? Math.max(0, quizDuration - Math.floor((nowTs - quizStartedAt) / 1000))
      : 0;
  const timerPct = quizDuration ? (timeLeft / quizDuration) * 100 : 0;
  const timerState = timerPct > 50 ? "ok" : timerPct > 20 ? "warn" : "danger";

  useEffect(() => {
    if (!quizActive) return undefined;
    const id = setInterval(() => setNowTs(Date.now()), 1000);
    return () => clearInterval(id);
  }, [quizActive]);

  useEffect(() => {
    if (!quizActive || !quizStartedAt || timeLeft > 0 || autoSubmitRef.current) return;
    autoSubmitRef.current = true;
    toast.info("Time's up", "Your answers were submitted automatically.");
    onSubmitQuiz();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timeLeft, quizActive, quizStartedAt]);


  async function refreshDocs(preferredId) {
    setDocsLoading(true);
    try {
      const list = await api.documents();
      setDocs(list);
      const nextId = preferredId || (list.some((d) => d.id === activeId) ? activeId : list[0]?.id || null);
      setActiveId(nextId);
      return list;
    } catch (err) {
      notifyError(err, "Could not load documents");
      return [];
    } finally {
      setDocsLoading(false);
    }
  }

  useEffect(() => {
    api
      .me()
      .then((user) => {
        setMe(user);
        setAssessmentForm((prev) => ({
          ...prev,
          learner_level: user.learner_level || "beginner",
          learning_style: user.learning_preferences?.learning_style || "analogy_and_examples",
          study_goals: user.learning_preferences?.study_goals || "exam_prep",
        }));
      })
      .catch(() => {
        setToken(null);
        navigate("/login");
      });
    refreshDocs();
  }, [navigate]);

  useEffect(() => {
    pollToken.current += 1; // cancel any in-flight quiz generation polling
    setSummary(null);
    setQuiz(null);
    setAnswers([]);
    setResult(null);
    setPerf(null);
    setCoachAdvice("");
    setQuizStartedAt(null);
    setQuizElapsed(null);
    autoSubmitRef.current = false;
    if (!activeId) return;

    let timer;
    let attempts = 0;
    const maxAttempts = 20;

    function fetchSummary() {
      api.summary(activeId)
        .then((data) => {
          setSummary(data);
          const stillGenerating =
            data.status === "generating" ||
            (data.status !== "failed" &&
              data.key_concepts?.length === 0 &&
              (!data.exam_notes || data.exam_notes.includes("being generated")));
          if (stillGenerating && attempts < maxAttempts) {
            attempts++;
            timer = setTimeout(fetchSummary, 3000);
          }
        })
        .catch(() => {
          if (attempts < maxAttempts) {
            attempts++;
            timer = setTimeout(fetchSummary, 3000);
          }
        });
    }

    fetchSummary();
    setPerfLoading(true);
    api
      .performance(activeId)
      .then(setPerf)
      .catch(() => setPerf(null))
      .finally(() => setPerfLoading(false));

    return () => {
      if (timer) clearTimeout(timer);
    };
  }, [activeId]);

  async function onRegenerateSummary() {
    if (!activeId) return;
    setBusy("Summarization Agent is extracting concepts and generating revision notes via Llama 3...");
    try {
      const updated = await api.regenerateSummary(activeId);
      setSummary(updated);
      toast.success("Summary regenerated", "Fresh concepts and revision notes are ready.");
    } catch (err) {
      notifyError(err, "Summary generation failed");
    } finally {
      setBusy("");
    }
  }


  async function handleUploaded(doc) {
    await refreshDocs(doc.id);
  }

  async function onDeleteDocument(docId, event) {
    event.stopPropagation();
    if (!window.confirm("Are you sure you want to delete this document and its vector index?")) return;
    try {
      await api.deleteDocument(docId);
      await refreshDocs();
      toast.info("Document deleted", "The file and its studies were removed.");
    } catch (err) {
      notifyError(err, "Could not delete document");
    }
  }

  async function onQuiz(focusWeak = false) {
    if (!activeId) return;
    const token = (pollToken.current += 1);
    setResult(null);
    setAnswers([]);
    setQuiz(null);
    setQuizStartedAt(null);
    setQuizElapsed(null);
    autoSubmitRef.current = false;
    setBusy(
      focusWeak
        ? "Generating a targeted quiz on your weak topics..."
        : "Generating your adaptive quiz from your notes..."
    );
    try {
      // The backend returns immediately and generates questions in the background,
      // so we poll for the result instead of holding one long request open.
      let stage = await api.createQuiz(activeId, focusWeak);
      if (pollToken.current !== token) return;
      setQuiz(stage);
      setBusy("");

      let attempts = 0;
      const maxAttempts = 150; // ~10 minutes at a 4s interval
      while ((stage.status === "generating" || !stage.status) && attempts < maxAttempts) {
        await new Promise((resolve) => setTimeout(resolve, 4000));
        if (pollToken.current !== token) return;
        stage = await api.getQuiz(stage.id);
        if (pollToken.current !== token) return;
        setQuiz(stage);
        attempts += 1;
      }

      if (stage.status === "generating") {
        toast.error("Quiz is taking too long", "Please try generating it again.");
      } else if (stage.status === "ready") {
        setAnswers(stage.questions.map(() => ""));
        setQuizStartedAt(Date.now());
        setNowTs(Date.now());
        autoSubmitRef.current = false;
        const mins = Math.round((stage.questions.length * SECONDS_PER_QUESTION) / 60);
        toast.success(
          "Quiz ready",
          `${stage.questions.length} questions · you have about ${mins} min.`
        );
      } else if (stage.status === "failed") {
        toast.error("Quiz generation failed", stage.error || "The AI could not build this quiz. Make sure Ollama is running.");
      }
    } catch (err) {
      notifyError(err, "Quiz generation failed");
    } finally {
      if (pollToken.current === token) setBusy("");
    }
  }

  async function onSubmitQuiz(event) {
    if (event) event.preventDefault();
    if (!quiz || result) return;
    const elapsed = quizStartedAt
      ? Math.min(quizDuration, Math.floor((Date.now() - quizStartedAt) / 1000))
      : null;
    setBusy("Grading answers and updating adaptive difficulty...");
    try {
      const res = await api.submitQuiz(quiz.id, answers);
      setResult(res);
      setQuizElapsed(elapsed);
      setQuizStartedAt(null);
      const updatedPerf = await api.performance(activeId);
      setPerf(updatedPerf);
      toast.success(
        "Quiz graded",
        `You scored ${Math.round((res.score || 0) * 100)}%. Check Performance & Coach for insights.`
      );
    } catch (err) {
      notifyError(err, "Could not grade this quiz");
    } finally {
      setBusy("");
    }
  }

  async function onFetchCoach() {
    if (!activeId) return;
    setBusy("Consulting Adaptive AI Study Coach...");
    try {
      const data = await api.adaptiveCoach(activeId);
      setCoachAdvice(data.adaptive_advice || "Keep practicing your notes!");
      toast.info("Coach report ready", "Your personalized recovery plan is below.");
    } catch (err) {
      notifyError(err, "Could not reach the AI Coach");
    } finally {
      setBusy("");
    }
  }

  async function onSaveAssessment(e) {
    e.preventDefault();
    setBusy("Personalizing your learning profile...");
    try {
      const res = await api.assessLearner(assessmentForm);
      setMe((prev) => ({
        ...prev,
        learner_level: res.learner_level,
        learning_preferences: res.learning_preferences,
      }));
      setShowAssessment(false);
      toast.success("Profile updated", "Your explanations and quizzes will now adapt to this level.");
    } catch (err) {
      notifyError(err, "Could not save your profile");
    } finally {
      setBusy("");
    }
  }

  function logout() {
    setToken(null);
    navigate("/login");
  }

  return (
    <div className="app-shell">
      {/* Sidebar */}
      <aside>
        <div className="brand">
          <strong>StudySync AI</strong>
          <span>Intelligent Multi-Agent Assistant</span>
        </div>

        <UploadDropzone onUploaded={handleUploaded} />

        <div className="doc-section-header">
          <span>Your Documents ({docs.length})</span>
        </div>

        <div className="doc-list">
          {docsLoading ? (
            <DocListSkeleton />
          ) : (
            <>
              {docs.map((doc) => (
                <div
                  key={doc.id}
                  className={doc.id === activeId ? "doc active" : "doc"}
                  onClick={() => setActiveId(doc.id)}
                >
                  <div className="doc-info">
                    <span className="doc-title">{doc.filename}</span>
                    <em className={`status-pill ${doc.status}`}>{doc.status}</em>
                  </div>
                  <button
                    className="btn-delete"
                    title="Delete document"
                    onClick={(e) => onDeleteDocument(doc.id, e)}
                  >
                    ✕
                  </button>
                </div>
              ))}
              {!docs.length ? (
                <div className="empty-note">
                  <span className="empty-note-icon">🗂️</span>
                  <span>No materials yet — upload a PDF, PPTX, or your own notes to begin.</span>
                </div>
              ) : null}
            </>
          )}
        </div>

        <div className="aside-foot">
          <div className="user-profile" onClick={() => setShowAssessment(true)}>
            <div className="user-avatar">{me?.email?.[0]?.toUpperCase() || "S"}</div>
            <div className="user-meta">
              <span className="user-email">{me?.email}</span>
              <span className="user-level-badge">
                🎓 {me?.learner_level?.toUpperCase() || "BEGINNER"}
              </span>
            </div>
          </div>
          <button className="linkish signout-btn" onClick={logout}>
            Sign out
          </button>
        </div>
      </aside>

      {/* Main Workspace */}
      <main>
        <header>
          <div>
            <p className="eyebrow">{active ? active.filename : "No document selected"}</p>
            <h1>{active ? active.filename : "Select or Upload a Document to Begin"}</h1>
          </div>

          <div className="header-badges">
            <PreferencesMenu />
            <button
              className="level-pill"
              onClick={() => setShowAssessment(true)}
              title="Click to change your learner level assessment"
            >
              Learner: <strong>{me?.learner_level || "Beginner"}</strong> ✎
            </button>
            {perf ? (
              <div className="pill">
                Difficulty: <strong>{perf.difficulty}</strong> · Avg:{" "}
                <strong>{(perf.average_score * 100).toFixed(0)}%</strong>
              </div>
            ) : null}
          </div>
        </header>

        {/* Tab Navigation */}
        <nav className="tabs">
          {TABS.map((t) => (
            <button
              key={t.id}
              className={tab === t.id ? "on" : ""}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>

        {busy ? <div className="banner busy">{busy}</div> : null}

        {/* TAB 1: SUMMARY */}
        {tab === "summary" && (
          <section className="tab-pane">
            {!active ? (
              <EmptyState
                icon="📚"
                title="No document selected"
                message="Upload your notes from the sidebar (PDF, PPTX, DOCX, TXT or MD) to unlock AI summaries, doubt solving, and adaptive quizzes — all grounded in your own material."
              />
            ) : summary && summary.status === "failed" ? (
              <div className="loading-card">
                <div style={{ fontSize: "2rem", marginBottom: "0.5rem" }}>⚠️</div>
                <p><strong>Summary generation failed.</strong></p>
                <small className="muted">
                  {summary.error || "The Summarization Agent could not process this document. Make sure Ollama is running (ollama serve) and try again."}
                </small>
                <div style={{ marginTop: "1rem" }}>
                  <button className="primary-btn" onClick={onRegenerateSummary}>
                    🔄 Try Again
                  </button>
                </div>
              </div>
            ) : !summary || summary.status === "generating" || (summary.key_concepts?.length === 0 && (!summary.exam_notes || summary.exam_notes.includes("being generated"))) ? (
              <div className="loading-block">
                <div className="loading-status">
                  <span className="spinner small" />
                  <div>
                    <strong>The Summarization Agent is analyzing your notes…</strong>
                    <small className="muted">
                      Extracting key concepts, definitions, important points and chapter notes. This
                      usually takes 10–20 seconds.
                    </small>
                  </div>
                  <button className="primary-btn" onClick={onRegenerateSummary}>
                    ⚡ Regenerate Now
                  </button>
                </div>
                <SummarySkeleton />
              </div>
            ) : (
              <SummarySections
                summary={summary}
                active={active}
                onRegenerate={onRegenerateSummary}
              />
            )}
          </section>
        )}

        {/* TAB 2: ASK AI (DOUBT SOLVER) */}
        {tab === "doubts" && (
          <section className="tab-pane">
            <DoubtChat key={activeId || "none"} activeId={activeId} summary={summary} />
          </section>
        )}

        {/* TAB 3: QUIZ */}
        {tab === "quiz" && (
          <section className="tab-pane">
            <div className="quiz-header-actions">
              <button className="primary-btn" onClick={() => onQuiz(false)}>
                🎯 Generate New Quiz
              </button>
              {perf?.weak_topics?.length > 0 && (
                <button className="accent-btn" onClick={() => onQuiz(true)}>
                  ⚡ Focus on Weak Topics ({perf.weak_topics.map((t) => t.topic).join(", ")})
                </button>
              )}
            </div>

            {!quiz && !result ? (
              <EmptyState
                icon="📝"
                title="Ready to test yourself?"
                message="Generate an adaptive quiz from your notes. Difficulty adjusts to your level and, once you have results, targets your weakest topics."
                action={
                  <button className="primary-btn" onClick={() => onQuiz(false)}>
                    Generate Adaptive Quiz
                  </button>
                }
              />
            ) : null}

            {quiz && (quiz.status === "generating" || !quiz.status) ? (
              <div className="loading-block">
                <div className="loading-status">
                  <span className="spinner small" />
                  <div>
                    <strong>The Quiz Agent is crafting your questions…</strong>
                    <small className="muted">
                      Local AI can take a minute or two. Keep this tab open — your quiz will appear
                      automatically.
                    </small>
                  </div>
                </div>
                <QuizSkeleton />
              </div>
            ) : null}

            {quiz && quiz.status === "failed" ? (
              <div className="quiz-failed-card">
                <p className="muted">{quiz.error || "Quiz generation failed. Please try again."}</p>
                <button className="primary-btn" onClick={() => onQuiz(false)}>Try Again</button>
              </div>
            ) : null}

            {quiz && quiz.status === "ready" && quiz.questions?.length ? (
              <form className="quiz-card" onSubmit={onSubmitQuiz}>
                <div className="quiz-meta-bar">
                  <span>Difficulty: <strong>{quiz.difficulty.toUpperCase()}</strong></span>
                  <span>Total Questions: <strong>{quiz.questions.length}</strong></span>
                  <span className={`quiz-timer ${timerState}`} title="Time remaining">
                    <span aria-hidden="true">⏱</span>
                    <span>{fmtClock(timeLeft)}</span>
                  </span>
                </div>
                <div className="quiz-timer-track" aria-hidden="true">
                  <div
                    className={`quiz-timer-fill ${timerState}`}
                    style={{ width: `${Math.max(timerPct, 0)}%` }}
                  />
                </div>

                {quiz.questions.map((q, idx) => (
                  <fieldset key={q.id || idx} className="question-block">
                    <legend>
                      <span className="q-num">Question {idx + 1}</span>
                      <span className="q-text">{q.prompt}</span>
                      <span className="q-topic">[{q.topic}]</span>
                    </legend>

                    {q.options?.length ? (
                      <div className="options-group">
                        {q.options.map((opt, oi) => {
                          const picked = answers[idx] === opt;
                          return (
                            <label
                              key={opt}
                              className={`choice-card ${picked ? "selected" : ""}`}
                            >
                              <input
                                type="radio"
                                name={`q-${idx}`}
                                checked={picked}
                                onChange={() =>
                                  setAnswers((prev) =>
                                    prev.map((val, i) => (i === idx ? opt : val))
                                  )
                                }
                              />
                              <span className="choice-letter">
                                {String.fromCharCode(65 + oi)}
                              </span>
                              <span className="choice-text">{opt}</span>
                            </label>
                          );
                        })}
                      </div>
                    ) : (
                      <input
                        type="text"
                        className="short-answer-input"
                        placeholder="Type your concise answer here..."
                        value={answers[idx] || ""}
                        onChange={(e) =>
                          setAnswers((prev) =>
                            prev.map((val, i) => (i === idx ? e.target.value : val))
                          )
                        }
                      />
                    )}
                  </fieldset>
                ))}

                <button type="submit" className="submit-quiz-btn">
                  Submit Quiz & Evaluate
                </button>
              </form>
            ) : null}

            {/* Quiz Result & Detailed Explanations */}
            {result ? (
              <div className="quiz-result-card">
                <div className="result-banner">
                  <div className="result-score-circle">
                    <strong>{(result.score * 100).toFixed(0)}%</strong>
                    <span>Score</span>
                  </div>
                  <div className="result-meta">
                    <h3>Quiz Completed!</h3>
                    <p>
                      Adaptive Level: <strong>{result.difficulty.toUpperCase()}</strong>
                    </p>
                    {quizElapsed != null ? (
                      <p>
                        Time taken: <strong>{fmtClock(quizElapsed)}</strong>
                      </p>
                    ) : null}
                    {result.weak_topics?.length > 0 ? (
                      <p className="weak-alert">
                        ⚠️ Identified Weak Topics: <strong>{result.weak_topics.join(", ")}</strong>
                      </p>
                    ) : (
                      <p className="strong-alert">🎉 Excellent mastery! No weak topics detected.</p>
                    )}
                  </div>
                </div>

                <h3>Detailed Question Review</h3>
                <div className="results-review-list">
                  {result.results.map((res, i) => (
                    <div
                      key={i}
                      className={`review-item ${res.correct ? "correct" : "incorrect"}`}
                    >
                      <div className="review-header">
                        <span className="review-status">
                          {res.correct ? "✅ Correct" : "❌ Incorrect"}
                        </span>
                        <span className="review-topic">Topic: {res.topic}</span>
                      </div>
                      <div className="review-answers">
                        <p>
                          <strong>Your Answer:</strong> {res.given || "(None)"}
                        </p>
                        {!res.correct && (
                          <p>
                            <strong>Expected Answer:</strong> {res.expected}
                          </p>
                        )}
                      </div>
                      {res.explanation && (
                        <div className="review-explanation">
                          <strong>💡 Explanation:</strong> {res.explanation}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </section>
        )}

        {/* TAB 4: PERFORMANCE & COACH */}
        {tab === "performance" && (
          <section className="tab-pane">
            {perfLoading ? (
              <PerformanceSkeleton />
            ) : !perf || (perf.quizzes_taken === 0 && !(perf.history?.length)) ? (
              <EmptyState
                icon="📊"
                title="No performance data yet"
                message="Generate an adaptive quiz and submit your answers — your scores, topic mastery and a personalised coaching plan will appear here as interactive charts."
                action={
                  <button className="primary-btn" onClick={() => setTab("quiz")}>
                    📝 Go to Adaptive Quiz
                  </button>
                }
              />
            ) : (
              <div className="performance-layout">
                {/* SECTION 1: Performance Overview */}
                <div className="card perf-overview">
                  <h2>🎯 Performance Overview</h2>
                  <small className="muted">A snapshot of your learning across this document.</small>
                  <div className="stats-grid">
                    <div className="stat-card">
                      <span className="stat-value">{(perf.average_score * 100).toFixed(0)}%</span>
                      <span className="stat-label">Overall Accuracy</span>
                    </div>
                    <div className="stat-card">
                      <span className="stat-value">{perf.quizzes_taken}</span>
                      <span className="stat-label">Quizzes Attempted</span>
                    </div>
                    <div className="stat-card">
                      <span className="stat-value">{perfInsights.topicsAssessed}</span>
                      <span className="stat-label">Topics Assessed</span>
                    </div>
                    <div className="stat-card">
                      <span
                        className={`stat-value ${perfInsights.improvement >= 0 ? "up" : "down"}`}
                      >
                        {perfInsights.improvement >= 0 ? "▲" : "▼"}{" "}
                        {Math.abs(perfInsights.improvement).toFixed(0)}%
                      </span>
                      <span className="stat-label">Improvement</span>
                    </div>
                    <div className="stat-card">
                      <span className="stat-value">{perf.difficulty.toUpperCase()}</span>
                      <span className="stat-label">Current Difficulty</span>
                    </div>
                  </div>
                </div>

                {/* SECTION 2: Strengths & Weaknesses */}
                <div className="card">
                  <h2>⚖️ Strengths &amp; Weaknesses</h2>
                  <small className="muted">Your best-performing and weakest topics so far.</small>
                  <div className="sw-grid">
                    <div className="sw-card sw-strong">
                      <span className="sw-tag">💪 Strongest Topic</span>
                      {perfInsights.best ? (
                        <>
                          <h3>{perfInsights.best.topic}</h3>
                          <span className="sw-score">
                            {Math.round(perfInsights.best.accuracy * 100)}% accuracy ·{" "}
                            {perfInsights.best.correct}/{perfInsights.best.total} correct
                          </span>
                          <div className="progress-bar-bg">
                            <div
                              className="progress-bar-fill good"
                              style={{ width: `${Math.round(perfInsights.best.accuracy * 100)}%` }}
                            />
                          </div>
                        </>
                      ) : (
                        <p className="muted">Keep quizzing to reveal your strengths.</p>
                      )}
                    </div>
                    <div className="sw-card sw-weak">
                      <span className="sw-tag">🎯 Needs Work</span>
                      {perfInsights.weakest ? (
                        <>
                          <h3>{perfInsights.weakest.topic}</h3>
                          <span className="sw-score">
                            {Math.round(perfInsights.weakest.accuracy * 100)}% accuracy ·{" "}
                            {perfInsights.weakest.correct}/{perfInsights.weakest.total} correct
                          </span>
                          <div className="progress-bar-bg">
                            <div
                              className="progress-bar-fill weak"
                              style={{ width: `${Math.round(perfInsights.weakest.accuracy * 100)}%` }}
                            />
                          </div>
                          <button
                            className="accent-btn"
                            onClick={() => {
                              setTab("quiz");
                              onQuiz(true);
                            }}
                          >
                            Take Targeted Quiz
                          </button>
                        </>
                      ) : (
                        <p className="muted">
                          Take a couple more quizzes (covering at least two topics) to compare.
                        </p>
                      )}
                    </div>
                  </div>
                </div>

                {/* CHARTS */}
                <div className="perf-chart-grid">
                  <div className="card span-2">
                    <h2>📊 Topic-wise Performance</h2>
                    <small className="muted">
                      Accuracy across topics — your strongest subjects appear first.
                    </small>
                    <TopicBars topics={perf.topics || []} />
                  </div>

                  <div className="card span-2">
                    <h2>📈 Learning Progress Over Time</h2>
                    <small className="muted">
                      Interactive — hover any point for the exact score, difficulty and date.
                    </small>
                    <ScoreTrendChart history={perf.history || []} />
                  </div>

                  <div className="card">
                    <h2>🧩 Answer Analysis</h2>
                    <small className="muted">Correct, incorrect and skipped answers per topic.</small>
                    <AnswerAnalysisChart topics={perf.topics || []} />
                  </div>

                  <div className="card">
                    <h2>🕸️ Skill Mastery</h2>
                    <small className="muted">
                      Conceptual understanding, recall, application and problem solving.
                    </small>
                    <SkillRadarChart skills={perf.skills || []} />
                  </div>
                </div>

                {/* Past Attempt History */}
                {perf.history?.length ? (
                  <div className="card">
                    <h2>🗂️ Past Attempts</h2>
                    <small className="muted">Every quiz you've finished for this document — newest first.</small>
                    <div className="attempt-list">
                      {[...perf.history].reverse().map((h, i, arr) => {
                        const pct = Math.round((h.score || 0) * 100);
                        const strong = (h.score || 0) >= 0.6;
                        const color = strong ? "#17294a" : "#a8432c";
                        return (
                          <div key={h.id ?? i} className="attempt-row">
                            <span className="attempt-index">#{arr.length - i}</span>
                            <div className="attempt-main">
                              <div className="attempt-topline">
                                <span className="attempt-difficulty">{h.difficulty}</span>
                                <span className="attempt-date">{fmtWhen(h.created_at)}</span>
                              </div>
                              <div className="attempt-track">
                                <div
                                  className="attempt-fill"
                                  style={{ width: `${Math.max(pct, 2)}%`, background: color }}
                                />
                              </div>
                            </div>
                            <span className="attempt-score" style={{ color }}>
                              {pct}%
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ) : null}

                {/* SECTION 3: AI Performance Coach */}
                <div className="card coach-card">
                  <div className="coach-header">
                    <h2>🤖 AI Performance Coach</h2>
                    <button className="primary-btn" onClick={onFetchCoach}>
                      Consult AI Coach
                    </button>
                  </div>
                  {coachAdvice ? (
                    <div className="coach-advice-box">
                      <pre className="notes">{coachAdvice}</pre>
                    </div>
                  ) : (
                    <p className="muted">
                      Get a 3-step plan telling you exactly what to revise and which topics to practise
                      next — based on your accuracy, weak areas and current level.
                    </p>
                  )}
                </div>
              </div>
            )}
          </section>
        )}
      </main>

      {/* LEARNER ASSESSMENT MODAL */}
      {showAssessment && (
        <div className="modal-backdrop" onClick={() => setShowAssessment(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>🎓 Learner Knowledge Assessment</h2>
              <button className="modal-close" onClick={() => setShowAssessment(false)}>
                ✕
              </button>
            </div>
            <p className="muted">
              StudySync adapts explanations, analogies, and quiz difficulty based on your understanding level.
            </p>

            <form onSubmit={onSaveAssessment}>
              <label>
                <span>Current Knowledge Level:</span>
                <select
                  value={assessmentForm.learner_level}
                  onChange={(e) =>
                    setAssessmentForm({ ...assessmentForm, learner_level: e.target.value })
                  }
                >
                  <option value="beginner">Beginner (Simple terms, intuitive analogies)</option>
                  <option value="intermediate">Intermediate (Mechanisms, practical examples)</option>
                  <option value="advanced">Advanced (Deep dive, edge cases, formulas)</option>
                  <option value="exam">Exam Ready (Strict definitions & test problems)</option>
                </select>
              </label>

              <label>
                <span>Preferred Learning Style:</span>
                <select
                  value={assessmentForm.learning_style}
                  onChange={(e) =>
                    setAssessmentForm({ ...assessmentForm, learning_style: e.target.value })
                  }
                >
                  <option value="analogy_and_examples">Intuitive Analogies & Examples</option>
                  <option value="practical">Practical / Code / Tables</option>
                  <option value="theory">Theoretical Deep Dives</option>
                  <option value="exam_prep">Quick Bullet Points for Exams</option>
                </select>
              </label>

              <label>
                <span>Primary Goal:</span>
                <select
                  value={assessmentForm.study_goals}
                  onChange={(e) =>
                    setAssessmentForm({ ...assessmentForm, study_goals: e.target.value })
                  }
                >
                  <option value="exam_prep">Acing an Upcoming Exam</option>
                  <option value="conceptual">Mastering Concepts for Long-Term</option>
                  <option value="quick_revision">Fast Revision before Class</option>
                </select>
              </label>

              <div className="modal-actions">
                <button
                  type="button"
                  className="linkish"
                  onClick={() => setShowAssessment(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="primary-btn">
                  Save & Apply Profile
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
