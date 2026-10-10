import { useEffect, useRef, useState } from "react";
import MessageBubble from "./MessageBubble.jsx";

const SUGGESTIONS = ["Summarize this subject's main topics", "Explain the key definitions with examples", "What are the differences between the concepts covered?"];

export default function ChatWindow({ messages, sending, onSend, disabled }) {
  const [text, setText] = useState("");
  const endRef = useRef(null);

  useEffect(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), [messages, sending]);

  const submit = (e) => {
    e?.preventDefault();
    const q = text.trim();
    if (!q || sending) return;
    onSend(q);
    setText("");
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 space-y-4 overflow-y-auto px-1 py-4">
        {messages.length === 0 && (
          <div className="mx-auto max-w-md py-10 text-center">
            <p className="font-serif text-2xl font-semibold">Ask your notes anything</p>
            <p className="mt-2 text-sm text-ink-soft">Answers come only from your uploaded files, with the slide or page they came from.</p>
            <div className="mt-5 flex flex-col gap-2">
              {SUGGESTIONS.map((s) => (
                <button key={s} className="card px-3 py-2 text-left text-sm hover:border-accent" onClick={() => onSend(s)} disabled={disabled}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <MessageBubble key={m.id || i} message={m} />
        ))}
        {sending && (
          <div className="flex items-center gap-2 px-2 text-sm text-ink-soft">
            <span className="h-2 w-2 animate-pulse rounded-full bg-accent" />
            Reading your notes…
          </div>
        )}
        <div ref={endRef} />
      </div>
      <form onSubmit={submit} className="border-t border-line bg-paper pt-3">
        <div className="flex items-end gap-2">
          <textarea
            className="input min-h-[44px] resize-none"
            rows={Math.min(5, text.split("\n").length)}
            placeholder={disabled ? "Upload a file and wait for it to be ready…" : "e.g. Explain normalization from Lecture 4"}
            value={text}
            maxLength={1000}
            disabled={disabled}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) submit(e);
            }}
          />
          <button className="btn-primary h-[44px]" disabled={!text.trim() || sending || disabled}>
            Ask
          </button>
        </div>
        <p className="mt-1 text-right font-mono text-[10px] text-ink-faint">{text.length}/1000 · Enter to send, Shift+Enter for new line</p>
      </form>
    </div>
  );
}
