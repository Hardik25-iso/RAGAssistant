import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import api, { errorMessage } from "../api/client.js";
import DocumentList from "../components/DocumentList.jsx";
import FileUpload from "../components/FileUpload.jsx";

export function useSubject(subjectId) {
  const [subject, setSubject] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [subs, docs] = await Promise.all([api.get("/subjects"), api.get("/documents", { params: { subject_id: subjectId } })]);
      setSubject(subs.data.find((s) => s.id === subjectId) || null);
      setDocuments(docs.data);
      setError("");
    } catch (e) {
      setError(errorMessage(e, "Could not load subject"));
    }
  }, [subjectId]);

  useEffect(() => {
    load();
  }, [load]);

  // Poll while any file is still being processed
  useEffect(() => {
    if (!documents.some((d) => d.status === "processing")) return;
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [documents, load]);

  return { subject, documents, error, reload: load };
}

export default function Subject() {
  const { subjectId } = useParams();
  const { subject, documents, error, reload } = useSubject(subjectId);
  const readyCount = documents.filter((d) => d.status === "ready").length;

  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      <Link to="/dashboard" className="text-sm text-ink-soft hover:text-ink">← All subjects</Link>
      <div className="mt-2 flex flex-wrap items-end justify-between gap-3">
        <h1 className="font-serif text-3xl font-semibold tracking-tight">{subject?.name || "…"}</h1>
        <Link to={`/subjects/${subjectId}/chat`} className={`btn-primary ${readyCount ? "" : "pointer-events-none opacity-50"}`}>
          Ask questions
        </Link>
      </div>
      {error && <p className="mt-4 rounded-md bg-bad-soft px-3 py-2 text-sm text-bad">{error}</p>}

      <section className="mt-8">
        <FileUpload subjectId={subjectId} onUploaded={reload} />
      </section>
      <section className="mt-8">
        <h2 className="label">Files ({documents.length})</h2>
        <DocumentList documents={documents} onChange={reload} />
      </section>
    </main>
  );
}
