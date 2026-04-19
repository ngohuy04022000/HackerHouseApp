// Lay BASE URL tu bien moi truong Vite hoac fallback localhost
const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export const api = {
  async get(path) {
    const res = await fetch(`${BASE}${path}`);
    if (!res.ok) {
      const body = await res.text();
      throw new Error(`HTTP ${res.status}: ${body}`);
    }
    return res.json();
  },

  async post(path, body) {
    const res = await fetch(`${BASE}${path}`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify(body),
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`HTTP ${res.status}: ${text}`);
    }
    return res.json();
  },

  async upload(path, formData) {
    const res = await fetch(`${BASE}${path}`, {
      method: "POST",
      body:   formData,   // browser tu dat Content-Type multipart/form-data
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`HTTP ${res.status}: ${text}`);
    }
    return res.json();
  },
};
