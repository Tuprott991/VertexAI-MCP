import { useMemo } from "react";
import DOMPurify from "dompurify";
import { marked } from "marked";

marked.setOptions({
  breaks: true,
  gfm: true,
});

export default function Markdown({ text }: { text: string }) {
  const html = useMemo(() => {
    const raw = marked.parse(text);
    const safe = DOMPurify.sanitize(typeof raw === "string" ? raw : raw.toString());
    return safe;
  }, [text]);

  return (
    <div
      className="prose prose-slate max-w-none dark:prose-invert prose-pre:bg-slate-900 prose-pre:text-slate-100"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
