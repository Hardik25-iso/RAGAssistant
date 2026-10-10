export default function DocSelector({ documents, selected, onChange }) {
  const ready = documents.filter((d) => d.status === "ready");
  const toggle = (id) => onChange(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id]);

  return (
    <div>
      <p className="label">Search in</p>
      <label className="flex cursor-pointer items-center gap-2 rounded px-1 py-1 text-sm hover:bg-black/5">
        <input type="checkbox" className="accent-accent" checked={selected.length === 0} onChange={() => onChange([])} />
        All files in subject
      </label>
      {ready.map((d) => (
        <label key={d.id} className="flex cursor-pointer items-center gap-2 rounded px-1 py-1 text-sm hover:bg-black/5" title={d.filename}>
          <input type="checkbox" className="accent-accent" checked={selected.includes(d.id)} onChange={() => toggle(d.id)} />
          <span className="truncate">{d.filename}</span>
        </label>
      ))}
      {ready.length === 0 && <p className="px-1 text-xs text-ink-faint">No processed files yet.</p>}
    </div>
  );
}
