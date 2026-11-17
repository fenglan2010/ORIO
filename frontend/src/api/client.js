const TOKEN_KEY = "oiro_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || "";
}
export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

async function request(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const resp = await fetch(path, { ...options, headers });
  if (resp.status === 401) {
    setToken("");
    if (!path.includes("/api/auth/login")) {
      window.location.hash = "#/login";
    }
  }
  const text = await resp.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { detail: text };
  }
  if (!resp.ok) {
    const detail = data?.detail;
    const msg = typeof detail === "string" ? detail : data?.message || resp.statusText;
    throw new Error(msg || "请求失败");
  }
  return data;
}

export const api = {
  login: (username, password) =>
    request("/api/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }),
  me: () => request("/api/auth/me"),
  health: () => request("/api/health"),
  summary: () => request("/api/dashboard/summary"),
  timeseries: () => request("/api/dashboard/timeseries"),
  competitors: () => request("/api/dashboard/competitors"),
  rooms: () => request("/api/dashboard/rooms"),
  updateRoomConstraints: (id, payload) =>
    request(`/api/dashboard/rooms/${id}/constraints`, { method: "PUT", body: JSON.stringify(payload) }),
  alerts: () => request("/api/alerts"),
  diagnose: (id) => request(`/api/alerts/${id}/diagnose`, { method: "POST" }),
  diagnoseDate: (date) => request(`/api/diagnosis?date=${encodeURIComponent(date)}`),
  ackAlert: (id) => request(`/api/alerts/${id}/ack`, { method: "POST" }),
  strategies: () => request("/api/strategies"),
  campaigns: () => request("/api/campaigns"),
  generate: (payload = {}) =>
    request("/api/strategies/generate", { method: "POST", body: JSON.stringify(payload) }),
  reviewStrategy: (id, decision, comment = "") =>
    request(`/api/strategies/${id}/review`, { method: "POST", body: JSON.stringify({ decision, comment }) }),
  rollbackStrategy: (id, reason = "") =>
    request(`/api/strategies/${id}/rollback`, { method: "POST", body: JSON.stringify({ reason }) }),
  reviews: () => request("/api/reviews"),
  draftReply: (id) => request(`/api/reviews/${id}/draft`, { method: "POST" }),
  reviewReply: (id, decision, comment = "") =>
    request(`/api/reviews/${id}/review`, { method: "POST", body: JSON.stringify({ decision, comment }) }),
  rollbackReply: (id, comment = "") =>
    request(`/api/reviews/${id}/rollback`, { method: "POST", body: JSON.stringify({ decision: "rollback", comment }) }),
  chatHistory: () => request("/api/chat/history"),
  chat: (message) => request("/api/chat", { method: "POST", body: JSON.stringify({ message }) }),
  memories: (params = "") => request("/api/memories" + (params ? "?" + params : "")),
  industryPatterns: (params = "") => request("/api/memories/patterns" + (params ? "?" + params : "")),
  audit: () => request("/api/audit"),
  modelCalls: () => request("/api/audit/model-calls"),
  workflow: (id) => request(`/api/audit/workflows/${id}`),
  settings: () => request("/api/settings"),
  updateSettings: (payload) => request("/api/settings", { method: "PUT", body: JSON.stringify(payload) }),
  writes: (params = "") => request("/api/writes" + (params ? "?" + params : "")),
  jobs: (params = "") => request("/api/jobs" + (params ? "?" + params : "")),
  writeJob: (id) => request(`/api/writes/${id}`),
  retryWrite: (id) => request(`/api/writes/${id}/retry`, { method: "POST" }),
  reconcileWrite: (id) => request(`/api/writes/${id}/reconcile`, { method: "POST" }),
  reconcileWrites: () => request("/api/writes/reconcile", { method: "POST" }),
  channels: () => request("/api/channels"),
  channel: (platform) => request(`/api/channels/${platform}`),
  connectChannel: (platform, payload) => request(`/api/channels/${platform}`, { method: "PUT", body: JSON.stringify(payload) }),
  verifyChannel: (platform) => request(`/api/channels/${platform}/verify`, { method: "POST" }),
  disconnectChannel: (platform) => request(`/api/channels/${platform}/disconnect`, { method: "POST" }),
  validateChannelContract: (platform, payload) => request(`/api/channels/${platform}/contract/validate`, { method: "POST", body: JSON.stringify(payload) }),
  installChannelContract: (platform, payload) => request(`/api/channels/${platform}/contract`, { method: "PUT", body: JSON.stringify(payload) }),
  uninstallChannelContract: (platform) => request(`/api/channels/${platform}/contract`, { method: "DELETE" }),
  executeStrategy: (id) => request(`/api/strategies/${id}/execute`, { method: "POST" }),
  executeReply: (id) => request(`/api/reviews/${id}/execute`, { method: "POST" }),
  users: () => request("/api/users"),
  userMatrix: () => request("/api/users/matrix"),
  createUser: (payload) => request("/api/users", { method: "POST", body: JSON.stringify(payload) }),
  updateUser: (id, payload) => request(`/api/users/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  disableUser: (id) => request(`/api/users/${id}/disable`, { method: "POST" }),
  enableUser: (id) => request(`/api/users/${id}/enable`, { method: "POST" }),
};

