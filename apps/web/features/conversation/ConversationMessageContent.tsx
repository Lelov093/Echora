"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

function CodeBlock({ language, code }: { language: string; code: string }) {
  const [copyStatus, setCopyStatus] = useState<"idle" | "copied" | "failed">("idle");

  async function copyCode() {
    try {
      await navigator.clipboard.writeText(code);
      setCopyStatus("copied");
    } catch {
      setCopyStatus("failed");
    }
    window.setTimeout(() => setCopyStatus("idle"), 1600);
  }

  return (
    <div className="conversation-code-block">
      <header><span>{language || "代码"}</span><button type="button" onClick={copyCode} aria-label="复制代码">{copyStatus === "copied" ? <Check size={14} /> : <Copy size={14} />}{copyStatus === "copied" ? "已复制" : copyStatus === "failed" ? "复制失败" : "复制"}</button></header>
      <pre tabIndex={0}><code>{code}</code></pre>
    </div>
  );
}

const markdownComponents: Components = {
  a: ({ href, children, ...props }) => <a href={href} target="_blank" rel="noreferrer noopener" {...props}>{children}</a>,
  pre: ({ children }) => <>{children}</>,
  code: ({ className, children, ...props }) => {
    const content = String(children).replace(/\n$/, "");
    const language = /language-([^\s]+)/.exec(className ?? "")?.[1] ?? "";
    if (language || content.includes("\n")) return <CodeBlock language={language} code={content} />;
    return <code className={className} {...props}>{children}</code>;
  },
};

export function ConversationMessageContent({ content, markdown }: { content: string; markdown: boolean }) {
  if (!markdown) return <p className="conversation-plain-text">{content}</p>;
  return <div className="conversation-markdown"><ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{content}</ReactMarkdown></div>;
}
