import { useEffect, useState, useCallback } from "react";
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis,
  Tooltip, Legend, CartesianGrid, ResponsiveContainer,
} from "recharts";
import { api, API } from "./api";

const COLORS = ["#2563eb", "#059669", "#d97706", "#dc2626", "#7c3aed", "#0891b2", "#64748b", "#db2777"];
const when = (d) => (d ? new Date(d + "Z").toLocaleString() : "—");

/* ---------- login / register ---------- */
function Auth({ onAuth }) {
  const [mode, setMode] = useState("login");
  const [f, setF] = useState({ username: "", password: "" });
  const [err, setErr] = useState("");
  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    try {
      const r = await api(`/auth/${mode}`, { method: "POST", body: f });
      localStorage.setItem("lp_token", r.token);
      onAuth();
    } catch (x) { setErr(x.message); }
  };
  return (
    <div className="auth card">
      <h1>LinkPulse</h1>
      <p className="muted">Short links. Smart insights. Safer sharing.</p>
      <form onSubmit={submit}>
        <input placeholder="Username" value={f.username} onChange={(e) => setF({ ...f, username: e.target.value })} required />
        <input type="password" placeholder="Password (6+ characters)" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} required />
        {err && <div className="error">{err}</div>}
        <button className="primary">{mode === "login" ? "Log in" : "Create account"}</button>
      </form>
      <p className="muted">
        {mode === "login" ? "New here?" : "Already registered?"}{" "}
        <a href="#" onClick={(e) => { e.preventDefault(); setMode(mode === "login" ? "register" : "login"); setErr(""); }}>
          {mode === "login" ? "Create an account" : "Log in"}
        </a>
      </p>
      {mode === "register" && <p className="muted small">The first account created becomes the admin.</p>}
    </div>
  );
}

/* ---------- charts ---------- */
function Charts({ data }) {
  return (
    <>
      <h4>Clicks, last 30 days</h4>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={data.series}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" fontSize={11} />
          <YAxis allowDecimals={false} fontSize={11} />
          <Tooltip />
          <Line type="monotone" dataKey="clicks" stroke="#2563eb" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
      <div className="grid3">
        {[["Referrers", "referrers"], ["Browsers", "browsers"], ["Devices", "devices"]].map(([t, k]) => (
          <div key={k}>
            <h4>{t}</h4>
            {data[k].length ? (
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie data={data[k]} dataKey="value" nameKey="name" outerRadius={60}>
                    {data[k].map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Tooltip />
                  <Legend fontSize={11} />
                </PieChart>
              </ResponsiveContainer>
            ) : <p className="muted">No clicks yet</p>}
          </div>
        ))}
      </div>
    </>
  );
}

function Stats({ code, onClose }) {
  const [d, setD] = useState(null);
  useEffect(() => { api(`/links/${code}/analytics`).then(setD); }, [code]);
  return (
    <div className="modal" onClick={onClose}>
      <div className="card modal-body" onClick={(e) => e.stopPropagation()}>
        <button className="close" onClick={onClose} aria-label="Close">✕</button>
        <h3>Analytics for /{code}</h3>
        {d ? <><p>Total clicks: <b>{d.total}</b></p><Charts data={d} /></> : <p>Loading…</p>}
      </div>
    </div>
  );
}

function QR({ code, onClose }) {
  const src = `${API}/api/links/${code}/qr`;
  return (
    <div className="modal" onClick={onClose}>
      <div className="card modal-body narrow" onClick={(e) => e.stopPropagation()}>
        <button className="close" onClick={onClose} aria-label="Close">✕</button>
        <h3>QR code for /{code}</h3>
        <img src={src} alt={`QR code for ${code}`} width="240" height="240" />
        <p><a className="btn" href={src + "?download=1"} download={`${code}.png`}>Download PNG</a></p>
      </div>
    </div>
  );
}

/* ---------- create + bulk ---------- */
function CreateForm({ onDone }) {
  const empty = { url: "", alias: "", campaign: "", tags: "", password: "", expires_at: "", max_clicks: "" };
  const [f, setF] = useState(empty);
  const [msg, setMsg] = useState(null);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const submit = async (e) => {
    e.preventDefault();
    setMsg(null);
    const body = {
      url: f.url, alias: f.alias || null, campaign: f.campaign || null, tags: f.tags || null,
      password: f.password || null,
      expires_at: f.expires_at ? new Date(f.expires_at).toISOString() : null,
      max_clicks: f.max_clicks ? Number(f.max_clicks) : null,
    };
    try {
      const r = await api("/links", { method: "POST", body });
      setMsg({ ok: true, t: r.short_url });
      setF(empty);
      onDone();
    } catch (x) { setMsg({ ok: false, t: x.message }); }
  };
  return (
    <form className="card" onSubmit={submit}>
      <h3>Create a short link</h3>
      <input placeholder="Paste a long URL (https://…)" value={f.url} onChange={set("url")} required />
      <div className="grid3">
        <input placeholder="Custom alias (optional)" value={f.alias} onChange={set("alias")} />
        <input placeholder="Campaign (optional)" value={f.campaign} onChange={set("campaign")} />
        <input placeholder="Tags, comma separated" value={f.tags} onChange={set("tags")} />
        <input type="password" placeholder="Password (optional)" value={f.password} onChange={set("password")} />
        <label className="field">Expires<input type="datetime-local" value={f.expires_at} onChange={set("expires_at")} /></label>
        <label className="field">Click limit<input type="number" min="1" placeholder="Unlimited" value={f.max_clicks} onChange={set("max_clicks")} /></label>
      </div>
      <button className="primary">Create link</button>
      {msg && <div className={msg.ok ? "ok" : "error"}>{msg.ok ? <>Created: <a href={msg.t} target="_blank" rel="noreferrer">{msg.t}</a></> : msg.t}</div>}
    </form>
  );
}

function Bulk({ onDone }) {
  const [res, setRes] = useState(null);
  const upload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    try { setRes(await api("/links/bulk", { method: "POST", body: fd })); onDone(); }
    catch (x) { setRes({ error: x.message }); }
    e.target.value = "";
  };
  return (
    <div className="card">
      <h3>Bulk upload (CSV)</h3>
      <p className="muted small">Header row: url, alias, campaign, tags. Up to 200 rows.</p>
      <input type="file" accept=".csv" onChange={upload} />
      {res?.error && <div className="error">{res.error}</div>}
      {res?.created && (
        <div className="ok">
          Created {res.created.length}, failed {res.errors.length}
          {res.errors.map((er) => <div key={er.row} className="small">Row {er.row}: {er.error}</div>)}
        </div>
      )}
    </div>
  );
}

/* ---------- table ---------- */
function LinksTable({ links, admin, onChange, onStats, onQR }) {
  const act = async (fn) => { try { await fn(); onChange(); } catch (x) { alert(x.message); } };
  if (!links.length) return <p className="muted">No links yet. Create your first link above.</p>;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr><th>Short link</th><th>Destination</th><th>Campaign</th><th>Clicks</th><th>Status</th>{admin && <th>Owner</th>}<th></th></tr>
        </thead>
        <tbody>
          {links.map((l) => (
            <tr key={l.code}>
              <td>
                <a href={l.short_url} target="_blank" rel="noreferrer">/{l.code}</a>{l.protected && " 🔒"}
                <button className="link" onClick={() => navigator.clipboard.writeText(l.short_url)}>copy</button>
              </td>
              <td className="trunc" title={l.target}>{l.target}</td>
              <td>{l.campaign || "—"}</td>
              <td>{l.click_count}{l.max_clicks ? ` / ${l.max_clicks}` : ""}</td>
              <td><span className={"badge " + l.status}>{l.status.replace("_", " ")}</span>{l.expires_at && <div className="small muted">until {when(l.expires_at)}</div>}</td>
              {admin && <td>{l.owner}</td>}
              <td className="actions">
                <button onClick={() => onStats(l.code)}>Stats</button>
                <button onClick={() => onQR(l.code)}>QR</button>
                {admin
                  ? <button onClick={() => act(() => api(`/admin/links/${l.code}/takedown`, { method: "POST" }))}>{l.takedown ? "Restore" : "Take down"}</button>
                  : <button onClick={() => act(() => api(`/links/${l.code}/toggle`, { method: "POST" }))}>{l.is_active ? "Disable" : "Enable"}</button>}
                {!admin && <button className="danger" onClick={() => confirm(`Delete /${l.code}?`) && act(() => api(`/links/${l.code}`, { method: "DELETE" }))}>Delete</button>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ---------- overview ---------- */
function Overview({ data }) {
  if (!data) return null;
  return (
    <div className="card">
      <div className="cards">
        <div><b>{data.links}</b><span>Links</span></div>
        <div><b>{data.active}</b><span>Active</span></div>
        <div><b>{data.clicks}</b><span>Total clicks</span></div>
      </div>
      <Charts data={{ ...data, referrers: [], browsers: [], devices: [] }} />
      <h4>Campaign performance</h4>
      {data.campaigns.length ? (
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={data.campaigns}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="campaign" fontSize={11} />
            <YAxis allowDecimals={false} fontSize={11} />
            <Tooltip /><Legend />
            <Bar dataKey="clicks" fill="#2563eb" />
            <Bar dataKey="links" fill="#059669" />
          </BarChart>
        </ResponsiveContainer>
      ) : <p className="muted">Add a campaign name to a link to compare campaigns.</p>}
    </div>
  );
}

/* ---------- app ---------- */
export default function App() {
  const [user, setUser] = useState(null);
  const [checked, setChecked] = useState(false);
  const [tab, setTab] = useState("links");
  const [links, setLinks] = useState([]);
  const [all, setAll] = useState([]);
  const [ov, setOv] = useState(null);
  const [q, setQ] = useState("");
  const [stats, setStats] = useState(null);
  const [qr, setQr] = useState(null);

  const load = useCallback(async () => {
    try {
      const me = await api("/me");
      setUser(me);
      setLinks(await api("/links?q=" + encodeURIComponent(q)));
      setOv(await api("/analytics/overview"));
      if (me.is_admin) setAll(await api("/admin/links"));
    } catch (x) {
      if (x.status === 401) { localStorage.removeItem("lp_token"); setUser(null); }
    }
    setChecked(true);
  }, [q]);

  useEffect(() => { load(); }, [load]);
  const logout = () => { localStorage.removeItem("lp_token"); setUser(null); };

  if (!checked) return <p className="muted center">Loading…</p>;
  if (!user) return <Auth onAuth={load} />;

  return (
    <div className="app">
      <header>
        <h1>LinkPulse</h1>
        <nav>
          <button className={tab === "links" ? "on" : ""} onClick={() => setTab("links")}>My links</button>
          <button className={tab === "analytics" ? "on" : ""} onClick={() => setTab("analytics")}>Analytics</button>
          {user.is_admin && <button className={tab === "admin" ? "on" : ""} onClick={() => setTab("admin")}>Admin</button>}
        </nav>
        <span className="muted">{user.username}</span>
        <button onClick={logout}>Log out</button>
      </header>

      {tab === "links" && (
        <>
          <CreateForm onDone={load} />
          <Bulk onDone={load} />
          <div className="card">
            <div className="row">
              <h3>My links</h3>
              <input className="search" placeholder="Search links…" value={q} onChange={(e) => setQ(e.target.value)} />
            </div>
            <LinksTable links={links} onChange={load} onStats={setStats} onQR={setQr} />
          </div>
        </>
      )}
      {tab === "analytics" && <Overview data={ov} />}
      {tab === "admin" && (
        <div className="card">
          <h3>All links (admin takedown)</h3>
          <LinksTable links={all} admin onChange={load} onStats={setStats} onQR={setQr} />
        </div>
      )}
      {stats && <Stats code={stats} onClose={() => setStats(null)} />}
      {qr && <QR code={qr} onClose={() => setQr(null)} />}
    </div>
  );
}
