import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, setToken } from "../api";

const FEATURES = [
  {
    icon: "📑",
    title: "Structured summaries",
    text: "Key concepts, definitions and rapid revision notes pulled from any document.",
  },
  {
    icon: "💬",
    title: "Doubt solving that cites",
    text: "Answers grounded in your own notes — with analogies, examples and sources.",
  },
  {
    icon: "📝",
    title: "Adaptive quizzes",
    text: "Difficulty adjusts to you and targets the topics you're weakest in.",
  },
];

export default function Auth({ mode }) {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const isLogin = mode === "login";

  async function onSubmit(event) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = isLogin ? await api.login(email, password) : await api.register(email, password);
      setToken(res.access_token);
      navigate("/");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-shell">
      <aside className="auth-aside">
        <div>
          <p className="eyebrow">StudySync AI</p>
          <h2>A study coach that actually knows your notes.</h2>
        </div>
        <ul className="auth-features">
          {FEATURES.map((f) => (
            <li key={f.title}>
              <span className="feat-icon" aria-hidden="true">
                {f.icon}
              </span>
              <span>
                <strong>{f.title}</strong>
                {f.text}
              </span>
            </li>
          ))}
        </ul>
      </aside>

      <div className="auth-main">
        <div className="auth-panel">
          <p className="eyebrow">StudySync AI</p>
          <h1>{isLogin ? "Welcome back" : "Create your study desk"}</h1>
          <p className="lede">
            Upload your notes, get exam-focused summaries, ask doubts from your material, and let
            quizzes adapt to your weak areas.
          </p>
          <form onSubmit={onSubmit}>
            <label>
              Email
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </label>
            <label>
              Password
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={6}
                required
              />
            </label>
            {error ? <p className="error">{error}</p> : null}
            <button type="submit" disabled={loading}>
              {loading ? "Please wait..." : isLogin ? "Sign in" : "Create account"}
            </button>
          </form>
          <p className="switch">
            {isLogin ? (
              <>
                New here? <Link to="/register">Register</Link>
              </>
            ) : (
              <>
                Already have an account? <Link to="/login">Sign in</Link>
              </>
            )}
          </p>
        </div>
      </div>
    </div>
  );
}
