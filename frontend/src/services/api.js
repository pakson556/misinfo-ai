// frontend/src/services/api.js
const DEFAULT_BASE = "http://127.0.0.1:8000";

export function getApiBase() {
  return import.meta.env.VITE_API_BASE_URL || DEFAULT_BASE;
}

async function httpJson(path, { method = "GET", body } = {}) {
  const base = getApiBase();
  const url = `${base}${path}`;

  console.log(`🌐 API Request: ${method} ${url}`);

  try {
    const res = await fetch(url, {
      method,
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: body ? JSON.stringify(body) : undefined,
    });

    console.log(`📡 Response status: ${res.status}`);

    if (!res.ok) {
      const text = await res.text();
      console.error(`❌ API Error ${res.status}:`, text);

      try {
        const errorJson = JSON.parse(text);
        throw new Error(errorJson.detail || errorJson.message || `HTTP ${res.status}`);
      } catch {
        throw new Error(`HTTP ${res.status}\n${text.substring(0, 200)}`);
      }
    }

    const data = await res.json();
    console.log(`✅ API Success:`, data);
    return data;
  } catch (error) {
    console.error(`❌ Fetch error:`, error);
    throw error;
  }
}

async function httpForm(path, formData, { method = "POST" } = {}) {
  const base = getApiBase();
  const url = `${base}${path}`;

  console.log(`🌐 API Form Request: ${method} ${url}`);

  try {
    const res = await fetch(url, { method, body: formData });

    console.log(`📡 Response status: ${res.status}`);

    if (!res.ok) {
      const text = await res.text();
      console.error(`❌ API Error ${res.status}:`, text);

      try {
        const errorJson = JSON.parse(text);
        throw new Error(errorJson.detail || errorJson.message || `HTTP ${res.status}`);
      } catch {
        throw new Error(`HTTP ${res.status}\n${text.substring(0, 200)}`);
      }
    }

    const data = await res.json();
    console.log(`✅ API Success:`, data);
    return data;
  } catch (error) {
    console.error(`❌ Fetch error:`, error);
    throw error;
  }
}

export const api = {
  // Core
  getRoot: () => httpJson("/"),
  getHealth: () => httpJson("/health"),
  getModelsInfo: () => httpJson("/models/info"),

  // Predictions
  predictAutoText: (text) => {
    console.log("🔤 Calling predictAutoText with:", (text || "").substring(0, 50) + "...");
    return httpJson("/predict/auto", { method: "POST", body: { text } });
  },

  predictAutoImage: (file) => {
    console.log("🖼️ Calling predictAutoImage with:", file?.name);
    const fd = new FormData();
    fd.append("file", file);
    return httpForm("/predict/auto/image", fd);
  },

  // Trends / Monitoring
  getTrends: (limit = 20, window = 2000) =>
    httpJson(`/trends?limit=${encodeURIComponent(limit)}&window=${encodeURIComponent(window)}`),

  // ✅ Dashboard metrics
  getMetrics: ({ window = 2000, recent = 10, bucket_seconds = 60 } = {}) =>
    httpJson(
      `/dashboard/metrics?window=${encodeURIComponent(window)}&recent=${encodeURIComponent(
        recent
      )}&bucket_seconds=${encodeURIComponent(bucket_seconds)}`
    ),
};
