import { useState } from "react";
import { SendHorizontal } from "lucide-react";

interface ChatComposerProps {
  disabled: boolean;
  onSubmit: (question: string) => void;
}

export default function ChatComposer({ disabled, onSubmit }: ChatComposerProps) {
  const [question, setQuestion] = useState("");

  const submit = () => {
    const trimmed = question.trim();
    if (!trimmed || disabled) return;
    onSubmit(trimmed);
    setQuestion("");
  };

  return (
    <form
      className="flex items-end gap-2 border-t border-ig-border pt-3"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <label htmlFor="chat-question" className="sr-only">
        Ask a question about this repository
      </label>
      <textarea
        id="chat-question"
        value={question}
        rows={1}
        disabled={disabled}
        onChange={(event) => setQuestion(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            submit();
          }
        }}
        placeholder="Ask about the code — e.g. where is authentication implemented?"
        className="max-h-32 min-h-10 flex-1 resize-y rounded-md border border-ig-border bg-ig-surface px-3 py-2 text-sm text-ig-navy placeholder:text-ig-muted/60 focus:border-ig-blue focus:outline-none focus:ring-2 focus:ring-ig-blue/30"
      />
      <button
        type="submit"
        disabled={disabled || question.trim().length === 0}
        aria-label="Send question"
        className="rounded-md bg-ig-blue p-2.5 text-white transition-colors duration-200 hover:bg-ig-navy disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ig-blue"
      >
        <SendHorizontal size={16} aria-hidden />
      </button>
    </form>
  );
}
