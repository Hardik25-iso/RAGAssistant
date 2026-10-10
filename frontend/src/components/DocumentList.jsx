import { useState } from "react";
import api, { errorMessage, formatBytes } from "../api/client.js";

const STATUS = {
  processing: "bg-warn-soft text-warn",
  ready: "bg-accent-soft text-accent",
  failed: "bg-bad-soft text-bad",
};

export default function DocumentList({ documents, onChange }) {
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState("");

  const act = async (id, fn) => {
    setBusy(id);
    setError("");
    try {
      await fn();
      onChange();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  };

  const download = (doc) =>
    act(doc.id, async () => {
      const res = await api.get(`/documents/${doc.id}/download`, { responseType: "blob" });
      if (res.data.type === "application/json") {
        const { url } = JSON.parse(await res.data.text()); // S3 presigned link (expires in 5 min)
        window.location.assign(url);
      } else {
        const href = URL.createObjectURL(res.data);
        const a = Object.assign(document.createElement("a"), { href, download: doc.filename });
        a.click();
        URL.revokeObjectURL(href);
      }
    });

  if (!documents.length)
    return <p className="rounded-lg border border-line bg-white px-4 py-6 text-center text-sm text-ink-soft">No files yet.</p>;

  return (
    <div>
      {error && <p className="mb-2 text-sm text-bad">{error}</p>}
      <ul className="card divide-y divide-line">
        {documents.map((d) => (
          <li key={d.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
            <span className="chip bg-paper uppercase text-ink-soft">{d.file_type}</span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{d.filename}</p>
              <p className="text-xs text-ink-faint">
                {formatBytes(d.size_bytes)}
                {d.pages ? ` · ${d.pages} ${d.file_type === "pptx" ? "slides" : "pages"}` : ""}
              </p>
              {d.status === "failed" && d.error && <p className="mt-0.5 text-xs text-bad">{d.error}</p>}
            </div>
            <span className={`chip ${STATUS[d.status]}`}>
              {d.status === "processing" && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />}
              {d.status}
            </span>
            <div className="flex gap-1">
              {d.status === "failed" && (
                <button className="btn-ghost px-2 py-1 text-xs" disabled={busy === d.id}
                  onClick={() => act(d.id, () => api.post(`/documents/${d.id}/reprocess`))}>
                  Retry
                </button>
              )}
              <button className="btn-ghost px-2 py-1 text-xs" disabled={busy === d.id} onClick={() => download(d)}>
                Download
              </button>
              <button className="btn-danger px-2 py-1 text-xs" disabled={busy === d.id}
                onClick={() => act(d.id, () => api.delete(`/documents/${d.id}`))}>
                Delete
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
