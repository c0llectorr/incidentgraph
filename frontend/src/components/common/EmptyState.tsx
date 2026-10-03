interface EmptyStateProps {
  title: string;
  body: string;
  action?: React.ReactNode;
}

export default function EmptyState({ title, body, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-ig-border px-6 py-12 text-center">
      <h3 className="text-sm font-semibold text-ig-navy">{title}</h3>
      <p className="max-w-md text-sm text-ig-muted">{body}</p>
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}
