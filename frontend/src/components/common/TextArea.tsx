import type { TextareaHTMLAttributes } from "react";
import { useId } from "react";

interface TextAreaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string;
  hint?: string;
}

export default function TextArea({ label, hint, className = "", ...rest }: TextAreaProps) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-[13px] font-medium text-ig-navy">
        {label}
      </label>
      <textarea
        id={id}
        className={`min-h-24 rounded-md border border-ig-border bg-ig-surface px-3 py-2 font-mono text-[13px] text-ig-navy placeholder:text-ig-muted/60 focus:border-ig-blue focus:outline-none focus:ring-2 focus:ring-ig-blue/30 ${className}`}
        {...rest}
      />
      {hint ? (
        <p className="text-xs text-ig-muted" role="note">
          {hint}
        </p>
      ) : null}
    </div>
  );
}
