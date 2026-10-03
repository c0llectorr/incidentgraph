import type { InputHTMLAttributes } from "react";
import { useId } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  hint?: string;
}

export default function Input({ label, hint, className = "", ...rest }: InputProps) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-[13px] font-medium text-ig-navy">
        {label}
      </label>
      <input
        id={id}
        className={`rounded-md border border-ig-border bg-ig-surface px-3 py-2 text-sm text-ig-navy placeholder:text-ig-muted/60 focus:border-ig-blue focus:outline-none focus:ring-2 focus:ring-ig-blue/30 ${className}`}
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
