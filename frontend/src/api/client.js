import axios from "axios";

// Tokens live in sessionStorage: cleared when the tab closes, never sent as cookies (no CSRF surface).
const KEY = "studyrag.tokens";

export const tokenStore = {
  get() {
    try {
      return JSON.parse(sessionStorage.getItem(KEY)) || null;
    } catch {
      return null;
    }
  },
  set(tokens) {
    sessionStorage.setItem(KEY, JSON.stringify(tokens));
  },
  clear() {
    sessionStorage.removeItem(KEY);
  },
};

const api = axios.create({ baseURL: "/api", timeout: 60000 });

api.interceptors.request.use((config) => {
  const t = tokenStore.get();
  if (t?.access_token) config.headers.Authorization = `Bearer ${t.access_token}`;
  return config;
});

let onLogout = () => {};
export function setLogoutHandler(fn) {
  onLogout = fn;
}

let refreshing = null;
api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;
    const status = error.response?.status;
    const isAuthCall = original?.url?.startsWith("/auth/");
    if (status === 401 && !original._retry && !isAuthCall) {
      const t = tokenStore.get();
      if (t?.refresh_token) {
        original._retry = true;
        try {
          refreshing =
            refreshing ||
            axios.post("/api/auth/refresh", { refresh_token: t.refresh_token }).finally(() => {
              refreshing = null;
            });
          const { data } = await refreshing;
          tokenStore.set({ access_token: data.access_token, refresh_token: data.refresh_token });
          original.headers.Authorization = `Bearer ${data.access_token}`;
          return api(original);
        } catch {
          /* fall through to logout */
        }
      }
      tokenStore.clear();
      onLogout();
    }
    return Promise.reject(error);
  }
);

export function errorMessage(err, fallback = "Something went wrong") {
  const d = err?.response?.data;
  if (d?.errors?.length) return d.errors.map((e) => `${e.field}: ${e.message}`).join(", ");
  if (typeof d?.detail === "string") return d.detail;
  if (err?.code === "ECONNABORTED") return "The request timed out. Please try again.";
  if (!err?.response) return "Can't reach the server. Check your connection.";
  return fallback;
}

export function formatBytes(n) {
  if (!n) return "0 B";
  const u = ["B", "KB", "MB", "GB"];
  const i = Math.min(Math.floor(Math.log(n) / Math.log(1024)), u.length - 1);
  return `${(n / 1024 ** i).toFixed(i ? 1 : 0)} ${u[i]}`;
}

export default api;
