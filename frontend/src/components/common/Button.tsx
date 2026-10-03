import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  children: ReactNode;
}

const styles: Record<Variant, string> = {
  primary: "bg-ig-blue text-white hover:bg-ig-navy focus-visible:outline-ig-blue",
  secondary:
    "bg-ig-surface text-ig-navy border border-ig-border hover:border-ig-blue focus-visible:outline-ig-blue",
  ghost: "bg-transparent text-ig-muted hover:text-ig-navy focus-visible:outline-ig-blue",
  danger: "bg-ig-surface text-ig-danger border border-ig-danger/40 hover:bg-ig-danger/5 focus-visible:outline-ig-danger",
};

export default function Button({ variant = "primary", children, className = "", ...rest }: ButtonProps) {
  return (
    <button
      className={`inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors duration-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-50 ${styles[variant]} ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
}
