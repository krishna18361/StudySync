const API = import.meta.env.VITE_API_URL || `http://${window.location.hostname}:8000`;

function token() {
  return localStorage.getItem("studysync_token");
}

export function setToken(value) {
  if (value) localStorage.setItem("studysync_token", value);
  else localStorage.removeItem("studysync_token");
}

export function isLoggedIn() {
  return Boolean(token());
}

async function request(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  const auth = token();
  if (auth) headers.Authorization = `Bearer ${auth}`;
  const res = await fetch(`${API}${path}`, { ...options, headers });
  const text = await res.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text };
    }
  }
  if (!res.ok) {
    const detail = data?.detail;
    const message = typeof detail === "string" ? detail : JSON.stringify(detail || res.statusText);
    throw new Error(message);
  }
  return data;
}

export const api = {
  register: (email, password) => request("/auth/register", { method: "POST", body: JSON.stringify({ email, password }) }),
  login: (email, password) => request("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  me: () => request("/auth/me"),
  assessLearner: (data) => request("/auth/assessment", { method: "POST", body: JSON.stringify(data) }),
  documents: () => request("/documents"),
  upload: (file, onProgress) =>
    new Promise((resolve, reject) => {
      const body = new FormData();
      body.append("file", file);
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${API}/documents/upload`);
      const auth = token();
      if (auth) xhr.setRequestHeader("Authorization", `Bearer ${auth}`);
      xhr.upload.onprogress = (event) => {
        if (onProgress && event.lengthComputable) {
          onProgress(Math.min(100, Math.round((event.loaded / event.total) * 100)));
        }
      };
      xhr.onload = () => {
        let data = null;
        if (xhr.responseText) {
          try {
            data = JSON.parse(xhr.responseText);
          } catch {
            data = { detail: xhr.responseText };
          }
        }
        if (xhr.status >= 200 && xhr.status < 300) {
          if (onProgress) onProgress(100);
          resolve(data);
        } else {
          const detail = data?.detail;
          reject(
            new Error(
              typeof detail === "string" ? detail : JSON.stringify(detail || xhr.statusText)
            )
          );
        }
      };
      xhr.onerror = () => reject(new Error("Failed to fetch"));
      xhr.send(body);
    }),
  deleteDocument: (id) => request(`/documents/${id}`, { method: "DELETE" }),
  summary: (id) => request(`/documents/${id}/summary`),
  regenerateSummary: (id) => request(`/documents/${id}/summarize`, { method: "POST" }),
  ask: (document_id, question, history = []) =>
    request("/ask", {
      method: "POST",
      body: JSON.stringify({ document_id, question, history }),
    }),
  createQuiz: (document_id, focus_weak_areas = false) =>
    request("/quiz", { method: "POST", body: JSON.stringify({ document_id, focus_weak_areas }) }),
  getQuiz: (id) => request(`/quiz/${id}`),
  submitQuiz: (id, answers) => request(`/quiz/${id}/submit`, { method: "POST", body: JSON.stringify({ answers }) }),
  performance: (document_id) => request(document_id ? `/performance?document_id=${document_id}` : "/performance"),
  adaptiveCoach: (document_id) => request(`/performance/coach?document_id=${document_id}`),
};
