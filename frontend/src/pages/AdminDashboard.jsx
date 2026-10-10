import { useEffect, useState } from "react";
import api, { errorMessage, formatBytes } from "../api/client.js";

const ACTIONS = ["", "login_success", "login_failed", "register", "upload", "delete_document", "download", "chat_query", "prompt_blocked"];
const PAGE = 25;

function Stat({ label, value, tone }) {
  return (
    <div className="card p-4">
      <p className="text-xs uppercase tracking-wide text-ink-soft">{label}</p>
      <p className={`mt-1 font-serif text-3xl font-semibold ${tone || ""}`}>{value}</p>
    </div>
  );
}

export default function AdminDashboard() {
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [logs, setLogs] = useState({ total: 0, items: [] });
  const [action, setAction] = useState("");
  const [page, setPage] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api.get("/admin/stats"), api.get("/admin/users")])
      .then(([s, u]) => {
        setStats(s.data);
        setUsers(u.data);
      })
      .catch((e) => setError(errorMessage(e)));
  }, []);

  useEffect(() => {
    api
      .get("/admin/audit-logs", { params: { action: action || undefined, limit: PAGE, offset: page * PAGE } })
      .then((r) => setLogs(r.data))
      .catch((e) => setError(errorMessage(e)));
  }, [action, page]);

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="font-serif text-3xl font-semibold tracking-tight">Admin</h1>
      <p className="mt-1 text-sm text-ink-soft">Usage and security activity. Admins cannot open student documents or chats.</p>
      {error && <p className="mt-4 rounded-md bg-bad-soft px-3 py-2 text-sm text-bad">{error}</p>}

      {stats && (
        <div className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat label="Students" value={stats.users} />
          <Stat label="Documents" value={stats.documents} />
          <Stat label="Storage used" value={formatBytes(stats.storage_bytes)} />
          <Stat label="Questions (24h)" value={stats.questions_24h} />
          <Stat label="Chunks indexed" value={stats.chunks} />
          <Stat label="Failed files" value={stats.documents_by_status?.failed || 0} />
          <Stat label="Failed logins (24h)" value={stats.failed_logins_24h} tone={stats.failed_logins_24h ? "text-warn" : ""} />
          <Stat label="Blocked prompts (24h)" value={stats.blocked_prompts_24h} tone={stats.blocked_prompts_24h ? "text-warn" : ""} />
        </div>
      )}

      <section className="mt-10">
        <h2 className="label">Users</h2>
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-paper text-left text-xs uppercase tracking-wide text-ink-soft">
              <tr><th className="px-4 py-2">Name</th><th className="px-4 py-2">Email</th><th className="px-4 py-2">Role</th><th className="px-4 py-2 text-right">Files</th><th className="px-4 py-2 text-right">Storage</th></tr>
            </thead>
            <tbody className="divide-y divide-line">
              {users.map((u) => (
                <tr key={u.id}>
                  <td className="px-4 py-2">{u.name}</td>
                  <td className="px-4 py-2 text-ink-soft">{u.email}</td>
                  <td className="px-4 py-2">{u.role}</td>
                  <td className="px-4 py-2 text-right font-mono">{u.documents}</td>
                  <td className="px-4 py-2 text-right font-mono">{formatBytes(u.storage_bytes)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="mt-10">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="label mb-0">Audit log ({logs.total})</h2>
          <select className="input w-48 py-1.5" value={action} onChange={(e) => { setAction(e.target.value); setPage(0); }}>
            {ACTIONS.map((a) => <option key={a} value={a}>{a || "All actions"}</option>)}
          </select>
        </div>
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-paper text-left text-xs uppercase tracking-wide text-ink-soft">
              <tr><th className="px-4 py-2">Time</th><th className="px-4 py-2">User</th><th className="px-4 py-2">Action</th><th className="px-4 py-2">Resource</th><th className="px-4 py-2">IP</th></tr>
            </thead>
            <tbody className="divide-y divide-line">
              {logs.items.map((l) => (
                <tr key={l.id}>
                  <td className="whitespace-nowrap px-4 py-2 font-mono text-xs">{new Date(l.timestamp).toLocaleString()}</td>
                  <td className="px-4 py-2 text-ink-soft">{l.user_email || "—"}</td>
                  <td className="px-4 py-2">
                    <span className={`chip ${["login_failed", "prompt_blocked"].includes(l.action) ? "bg-warn-soft text-warn" : "bg-paper text-ink-soft"}`}>{l.action}</span>
                  </td>
                  <td className="max-w-[220px] truncate px-4 py-2 font-mono text-xs text-ink-faint">{l.resource || "—"}</td>
                  <td className="px-4 py-2 font-mono text-xs">{l.ip || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-3 flex justify-end gap-2">
          <button className="btn-ghost" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>← Newer</button>
          <button className="btn-ghost" disabled={(page + 1) * PAGE >= logs.total} onClick={() => setPage((p) => p + 1)}>Older →</button>
        </div>
      </section>
    </main>
  );
}
