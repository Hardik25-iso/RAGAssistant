import { useEffect, useState } from "react";
import api, { errorMessage } from "../api/client.js";
import SubjectCard from "../components/SubjectCard.jsx";
import { useAuth } from "../context/AuthContext.jsx";

export default function Dashboard() {
  const { user } = useAuth();
  const [subjects, setSubjects] = useState(null);
  const [name, setName] = useState("");
  const [error, setError] = useState("");

  const load = () =>
    api.get("/subjects").then((r) => setSubjects(r.data)).catch((e) => setError(errorMessage(e)));

  useEffect(() => {
    load();
  }, []);

  const run = async (fn) => {
    setError("");
    try {
      await fn();
      await load();
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  const create = (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    run(async () => {
      await api.post("/subjects", { name: name.trim() });
      setName("");
    });
  };

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm text-ink-soft">Hi {user.name.split(" ")[0]},</p>
          <h1 className="font-serif text-3xl font-semibold tracking-tight">Your subjects</h1>
        </div>
        <form onSubmit={create} className="flex w-full gap-2 sm:w-auto">
          <input className="input sm:w-64" placeholder="New subject, e.g. DBMS" value={name} maxLength={100}
            onChange={(e) => setName(e.target.value)} />
          <button className="btn-primary shrink-0">Add subject</button>
        </form>
      </div>
      {error && <p className="mt-4 rounded-md bg-bad-soft px-3 py-2 text-sm text-bad">{error}</p>}

      {subjects === null ? (
        <p className="mt-10 text-sm text-ink-soft">Loading…</p>
      ) : subjects.length === 0 ? (
        <div className="mt-10 rounded-lg border border-dashed border-line px-6 py-14 text-center">
          <p className="font-serif text-xl font-semibold">Start with a subject</p>
          <p className="mt-1 text-sm text-ink-soft">Create one like “DBMS” or “Operating Systems”, then upload its lecture slides.</p>
        </div>
      ) : (
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {subjects.map((s) => (
            <SubjectCard key={s.id} subject={s}
              onRename={(id, n) => run(() => api.patch(`/subjects/${id}`, { name: n }))}
              onDelete={(id) => run(() => api.delete(`/subjects/${id}`))} />
          ))}
        </div>
      )}
    </main>
  );
}
