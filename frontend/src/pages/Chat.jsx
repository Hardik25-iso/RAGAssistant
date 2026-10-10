import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import api, { errorMessage } from "../api/client.js";
import ChatWindow from "../components/ChatWindow.jsx";
import DocSelector from "../components/DocSelector.jsx";
import { useSubject } from "./Subject.jsx";

export default function Chat() {
  const { subjectId } = useParams();
  const [params, setParams] = useSearchParams();
  const sessionId = params.get("session");
  const { subject, documents } = useSubject(subjectId);

  const [sessions, setSessions] = useState([]);
  const [messages, setMessages] = useState([]);
  const [selected, setSelected] = useState([]);
  const [sending, setSending] = useState(false);
  const [showSidebar, setShowSidebar] = useState(false);

  const loadSessions = () =>
    api.get("/chat/sessions", { params: { subject_id: subjectId } }).then((r) => setSessions(r.data)).catch(() => {});

  useEffect(() => {
    loadSessions();
  }, [subjectId]);

  useEffect(() => {
    if (!sessionId) return setMessages([]);
    api.get(`/chat/sessions/${sessionId}/messages`).then((r) => setMessages(r.data)).catch(() => setMessages([]));
  }, [sessionId]);

  const send = async (question) => {
    setMessages((m) => [...m, { role: "user", content: question }]);
    setSending(true);
    try {
      const { data } = await api.post("/chat/ask", {
        subject_id: subjectId,
        question,
        session_id: sessionId || undefined,
        doc_ids: selected.length ? selected : undefined,
      });
      setMessages((m) => [...m, { role: "assistant", content: data.answer, citations: data.citations, blocked: data.blocked, latency_ms: data.latency_ms }]);
      if (!sessionId) {
        setParams({ session: data.session_id }, { replace: true });
        loadSessions();
      }
    } catch (err) {
      setMessages((m) => [...m, { role: "assistant", content: errorMessage(err, "Could not get an answer"), error: true }]);
    } finally {
      setSending(false);
    }
  };

  const removeSession = async (id) => {
    await api.delete(`/chat/sessions/${id}`).catch(() => {});
    if (id === sessionId) setParams({});
    loadSessions();
  };

  const hasReady = documents.some((d) => d.status === "ready");

  return (
    <main className="mx-auto flex h-[calc(100vh-3.5rem)] max-w-6xl gap-6 px-4 py-4">
      <aside className={`${showSidebar ? "block" : "hidden"} w-64 shrink-0 overflow-y-auto md:block`}>
        <Link to={`/subjects/${subjectId}`} className="text-sm text-ink-soft hover:text-ink">← {subject?.name || "Subject"}</Link>
        <button className="btn-primary mt-4 w-full" onClick={() => setParams({})}>New chat</button>
        <div className="mt-6">
          <DocSelector documents={documents} selected={selected} onChange={setSelected} />
        </div>
        <div className="mt-6">
          <p className="label">History</p>
          {sessions.length === 0 && <p className="px-1 text-xs text-ink-faint">No chats yet.</p>}
          <ul className="space-y-0.5">
            {sessions.map((s) => (
              <li key={s.id} className={`group flex items-center rounded ${s.id === sessionId ? "bg-accent-soft" : "hover:bg-black/5"}`}>
                <button className="min-w-0 flex-1 truncate px-2 py-1.5 text-left text-sm" onClick={() => setParams({ session: s.id })} title={s.title}>
                  {s.title}
                </button>
                <button className="px-2 text-xs text-ink-faint opacity-0 hover:text-bad group-hover:opacity-100" onClick={() => removeSession(s.id)} aria-label="Delete chat">
                  ✕
                </button>
              </li>
            ))}
          </ul>
        </div>
      </aside>
      <section className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center justify-between border-b border-line pb-2 md:hidden">
          <button className="btn-ghost -ml-2 text-sm" onClick={() => setShowSidebar((v) => !v)}>
            {showSidebar ? "Hide" : "Files & history"}
          </button>
        </div>
        <ChatWindow messages={messages} sending={sending} onSend={send} disabled={!hasReady} />
      </section>
    </main>
  );
}
