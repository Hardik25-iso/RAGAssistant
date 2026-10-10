import { useState } from "react";

export default function SourceCitation({ citation }) {
  const [open, setOpen] = useState(false);
  return (
    <span className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="chip border border-line bg-paper text-ink-soft hover:border-accent hover:text-accent"
        title={citation.filename}
      >
        <span className="max-w-[160px] truncate">{citation.filename}</span>
        <span className="text-ink-faint">·</span>
        <span className="font-medium text-accent">{citation.label}</span>
      </button>
      {open && (
        <span className="absolute left-0 top-full z-10 mt-1 block w-72 max-w-[80vw] rounded-md border border-line bg-white p-3 text-xs leading-relaxed text-ink-soft shadow-lg">
          <span className="mb-1 block font-mono text-[11px] text-ink-faint">
            {citation.filename} · {citation.label} · match {(citation.score * 100).toFixed(0)}%
          </span>
          {citation.snippet}
        </span>
      )}
    </span>
  );
}
