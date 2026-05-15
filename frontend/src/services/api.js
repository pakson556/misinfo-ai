const API_BASE = "http://127.0.0.1:8000";

async function handleResponse(res) {
  let data = null;

  try {
    data = await res.json();
  } catch {
    data = null;
  }

  if (!res.ok) {
    const detail =
      data?.detail ||
      data?.message ||
      `Request failed with status ${res.status}`;
    throw new Error(detail);
  }

  return data;
}

export const api = {
  async predictAutoText(text, enableInternet = true) {
    const res = await fetch(`${API_BASE}/predict/auto`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        text,
        enable_internet: enableInternet,
      }),
    });

    return handleResponse(res);
  },

  async predictAutoImage(file, enableInternet = true) {
    const formData = new FormData();
    formData.append("file", file);

    const res = await fetch(
      `${API_BASE}/predict/auto/image?enable_internet=${encodeURIComponent(enableInternet)}`,
      {
        method: "POST",
        body: formData,
      }
    );

    return handleResponse(res);
  },

  async getHealth() {
    const res = await fetch(`${API_BASE}/health`);
    return handleResponse(res);
  },

  async getTrends(limit = 20, window = 2000) {
    const res = await fetch(
      `${API_BASE}/trends?limit=${encodeURIComponent(limit)}&window=${encodeURIComponent(window)}`
    );
    return handleResponse(res);
  },

  async getDashboardMetrics(window = 2000, recent = 10, bucketSeconds = 60) {
    const res = await fetch(
      `${API_BASE}/dashboard/metrics?window=${encodeURIComponent(window)}&recent=${encodeURIComponent(recent)}&bucket_seconds=${encodeURIComponent(bucketSeconds)}`
    );
    return handleResponse(res);
  },
};