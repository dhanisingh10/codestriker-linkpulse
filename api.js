export const API = import.meta.env.VITE_API_URL || "";

export async function api(path, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  const token = localStorage.getItem("lp_token");
  if (token) headers.Authorization = "Bearer " + token;
  let body = opts.body;
  if (body && !(body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(body);
  }
  const r = await fetch(API + "/api" + path, { ...opts, headers, body });
  if (!r.ok) {
    let msg = "Something went wrong";
    try {
      const j = await r.json();
      msg = Array.isArray(j.detail) ? j.detail.map((d) => d.msg).join(", ") : j.detail || msg;
    } catch {}
    const err = new Error(msg);
    err.status = r.status;
    throw err;
  }
  return r.json();
}
