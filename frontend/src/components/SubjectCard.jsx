import { useState } from "react";
import { Link } from "react-router-dom";

export default function SubjectCard({ subject, onRename, onDelete }) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(subject.name);
  const [confirm, setConfirm] = useState(false);

  const save = async (e) => {
    e.preventDefault();
    if (name.trim() && name !== subject.name) await onRename(subject.id, name.trim());
    setEditing(false);
  };

  return (
    <div className="card group flex flex-col p-4">
      {editing ? (
        <form onSubmit={save} className="flex gap-2">
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} maxLength={100} autoFocus />
          <button className="btn-primary">Save</button>
        </form>
      ) : (
        <Link to={`/subjects/${subject.id}`} className="block">
          <h3 className="font-serif text-xl font-semibold tracking-tight group-hover:text-accent">{subject.name}</h3>
          <p className="mt-1 text-sm text-ink-soft">
            {subject.document_count} {subject.document_count === 1 ? "file" : "files"}
          </p>
        </Link>
      )}
      <div className="mt-4 flex items-center gap-1 border-t border-line pt-3">
        <Link to={`/subjects/${subject.id}/chat`} className="btn-ghost -ml-2 text-accent">
          Ask questions →
        </Link>
        <span className="flex-1" />
        {confirm ? (
          <>
            <span className="text-xs text-bad">Delete subject and its files?</span>
            <button className="btn-danger" onClick={() => onDelete(subject.id)}>
              Yes
            </button>
            <button className="btn-ghost" onClick={() => setConfirm(false)}>
              No
            </button>
          </>
        ) : (
          <>
            <button className="btn-ghost text-xs" onClick={() => setEditing((v) => !v)}>
              Rename
            </button>
            <button className="btn-danger text-xs" onClick={() => setConfirm(true)}>
              Delete
            </button>
          </>
        )}
      </div>
    </div>
  );
}
