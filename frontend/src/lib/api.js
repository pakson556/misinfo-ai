/*
 * Every call from the website to the backend goes through this file.
 *
 * In Docker and in dev mode the API is on the same address as the website
 * (/api/...): nginx or Vite forwards it to the backend. To point at a backend
 * elsewhere, build with VITE_API_URL=https://your-backend.example.com
 */
// Base URL: empty means same origin (/api is proxied by Vite in dev and nginx in Docker).
const BASE = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

// fetch() wrapper: turns network failures and error responses into readable messages.
async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(`${BASE}${path}`, options);
  } catch {
    throw new Error("The checking service can't be reached right now. Please try again in a minute.");
  }
  if (!res.ok) throw new Error(await errorMessage(res));
  return res;
}

// Pull a human-readable message out of an error response.
// FastAPI validation errors come as a list, so we join their messages.
async function errorMessage(res) {
  try {
    const data = await res.json();
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) return data.detail.map((d) => d.msg?.replace(/^Value error, /, "")).join(" ");
    if (data.error) return data.error;
  } catch {
    /* not json */
  }
  if (res.status === 429) return "Too many checks in a short time. Wait a minute and try again.";
  return `The server returned an error (${res.status}).`;
}

/**
 * Why not use the browser's built-in EventSource? It only supports GET requests,
 * and we need POST to send the text/screenshot. So we read the stream by hand:
 * SSE is plain text where each event looks like
 *     event: claim_result
 *     data: {"claim": ...}
 *     (blank line)
 *
 * Read a Server-Sent Events stream from a POST response and call onEvent(name, data)
 * for each event. Resolves when the stream ends.
 */
async function readStream(res, onEvent, signal) {
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const flush = (block) => {
    let name = "message";
    const data = [];
    for (const line of block.split(/\r?\n/)) {
      if (line.startsWith("event:")) name = line.slice(6).trim();
      else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
    }
    if (!data.length) return;
    try {
      onEvent(name, JSON.parse(data.join("\n")));
    } catch {
      /* ignore keep-alive pings */
    }
  };
  while (true) {
    if (signal?.aborted) {
      reader.cancel();
      return;
    }
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split(/\r?\n\r?\n/);
    buffer = parts.pop();
    parts.forEach(flush);
  }
  if (buffer.trim()) flush(buffer);
}

// The functions the pages use, one per backend endpoint (see backend/app/main.py).
export const api = {
  health: () => request("/api/health").then((r) => r.json()),

  async analyzeStream({ text, url, file, useWeb }, onEvent, signal) {
    let res;
    if (file) {
      const form = new FormData();
      form.append("file", file);
      res = await request(`/api/analyze/image/stream?use_web=${useWeb}`, { method: "POST", body: form, signal });
    } else {
      res = await request("/api/analyze/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(url ? { url, use_web: useWeb } : { text, use_web: useWeb }),
        signal,
      });
    }
    await readStream(res, onEvent, signal);
  },

  history: (limit = 50) => request(`/api/history?limit=${limit}`).then((r) => r.json()),
  analysis: (id) => request(`/api/history/${encodeURIComponent(id)}`).then((r) => r.json()),
  remove: (id) => request(`/api/history/${encodeURIComponent(id)}`, { method: "DELETE" }).then((r) => r.json()),
  stats: (days = 30) => request(`/api/stats?days=${days}`).then((r) => r.json()),
  monitor: () => request("/api/monitor").then((r) => r.json()),
};
