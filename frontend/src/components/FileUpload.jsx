import { useRef, useState } from "react";
import api, { errorMessage } from "../api/client.js";

const MAX_MB = 20;

function precheck(file) {
  const ext = file.name.split(".").pop().toLowerCase();
  if (ext === "ppt") return "Old .ppt files can't be read. Open it in PowerPoint and save as .pptx, or export to PDF.";
  if (!["pdf", "pptx"].includes(ext)) return "Only PDF and PPTX files are allowed.";
  if (file.size > MAX_MB * 1024 * 1024) return `File is larger than ${MAX_MB} MB.`;
  return null;
}

export default function FileUpload({ subjectId, onUploaded }) {
  const inputRef = useRef(null);
  const [drag, setDrag] = useState(false);
  const [uploads, setUploads] = useState([]); // {name, progress, error}

  const update = (name, patch) => setUploads((u) => u.map((x) => (x.name === name ? { ...x, ...patch } : x)));

  const send = async (file) => {
    const problem = precheck(file);
    setUploads((u) => [...u.filter((x) => x.name !== file.name), { name: file.name, progress: 0, error: problem }]);
    if (problem) return;
    const form = new FormData();
    form.append("subject_id", subjectId);
    form.append("file", file);
    try {
      await api.post("/documents", form, {
        timeout: 120000,
        onUploadProgress: (e) => update(file.name, { progress: Math.round((e.loaded / (e.total || 1)) * 100) }),
      });
      setUploads((u) => u.filter((x) => x.name !== file.name));
      onUploaded();
    } catch (err) {
      update(file.name, { error: errorMessage(err, "Upload failed") });
    }
  };

  const handle = (files) => Array.from(files).forEach(send);

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          handle(e.dataTransfer.files);
        }}
        className={`cursor-pointer rounded-lg border-2 border-dashed px-6 py-8 text-center transition-colors ${
          drag ? "border-accent bg-accent-soft" : "border-line bg-white hover:border-accent/50"
        }`}
      >
        <p className="font-medium">Drop lecture slides or PDFs here</p>
        <p className="mt-1 text-sm text-ink-soft">or click to choose · .pdf and .pptx · up to {MAX_MB} MB each</p>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.pptx,application/pdf,application/vnd.openxmlformats-officedocument.presentationml.presentation"
          multiple
          hidden
          onChange={(e) => {
            handle(e.target.files);
            e.target.value = "";
          }}
        />
      </div>
      {uploads.length > 0 && (
        <ul className="mt-3 space-y-2">
          {uploads.map((u) => (
            <li key={u.name} className="card px-3 py-2 text-sm">
              <div className="flex items-center justify-between gap-3">
                <span className="truncate">{u.name}</span>
                {u.error ? (
                  <button className="btn-ghost px-2 py-0.5 text-xs" onClick={() => setUploads((x) => x.filter((y) => y.name !== u.name))}>
                    Dismiss
                  </button>
                ) : (
                  <span className="font-mono text-xs text-ink-soft">{u.progress}%</span>
                )}
              </div>
              {u.error ? (
                <p className="mt-1 text-xs text-bad">{u.error}</p>
              ) : (
                <div className="mt-1.5 h-1 overflow-hidden rounded bg-line">
                  <div className="h-full bg-accent transition-all" style={{ width: `${u.progress}%` }} />
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
