import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import SourceCitation from "./SourceCitation.jsx";

export default function MessageBubble({ message }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-accent px-4 py-2.5 text-[15px] text-white">
          {message.content}
        </div>
      </div>
    );
  }
  return (
    <div className="flex justify-start">
      <div
        className={`max-w-[90%] rounded-2xl rounded-bl-sm border px-4 py-3 ${
          message.blocked ? "border-warn/30 bg-warn-soft" : message.error ? "border-bad/30 bg-bad-soft" : "border-line bg-white"
        }`}
      >
        {message.blocked && <p className="mb-1 font-mono text-[11px] uppercase tracking-wide text-warn">Blocked by prompt guard</p>}
        <div className="prose-answer">
          {/* react-markdown does not render raw HTML, so model output cannot inject scripts */}
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
        </div>
        {message.citations?.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5 border-t border-line pt-2.5">
            <span className="mr-1 self-center text-[11px] uppercase tracking-wide text-ink-faint">Sources</span>
            {message.citations.map((c, i) => (
              <SourceCitation key={`${c.doc_id}-${c.page_or_slide}-${i}`} citation={c} />
            ))}
          </div>
        )}
        {message.latency_ms != null && (
          <p className="mt-1.5 text-right font-mono text-[10px] text-ink-faint">{(message.latency_ms / 1000).toFixed(1)}s</p>
        )}
      </div>
    </div>
  );
}
