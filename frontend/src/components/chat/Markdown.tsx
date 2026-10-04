import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import MermaidBlock from "./MermaidBlock";

interface MarkdownProps {
  content: string;
}

/** Render LLM answers as formatted Markdown (PRD §12.8 chat readability):
 * bold/italics/lists/tables via GFM, syntax-highlighted code blocks via
 * highlight.js, and ```mermaid blocks rendered as copyable diagram boxes.
 * Palette + typography come from the prose theme and globals.css. */
export default function Markdown({ content }: MarkdownProps) {
  return (
    <div className="prose prose-sm max-w-none text-ig-navy">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={{
          code(props) {
            const { className, children } = props;
            const language = /language-([\w-]+)/.exec(className ?? "")?.[1];
            if (language === "mermaid") {
              return <MermaidBlock code={String(children ?? "").replace(/\n$/, "")} />;
            }
            return <code className={className}>{children}</code>;
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
