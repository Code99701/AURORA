"use client";

import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ExternalLink, FileText } from "lucide-react";
import type { RAGSource } from "@/lib/types";
import { formatSourceLocation } from "@/lib/document-workspace";
import styles from "./chat-markdown.module.css";

interface CitationChipProps {
  position: number;
  source?: RAGSource;
  onOpenSource?: (source: RAGSource) => void;
}

function CitationChip({ position, source, onOpenSource }: CitationChipProps) {
  const [hovered, setHovered] = useState(false);

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (source && onOpenSource) {
      onOpenSource(source);
    }
  };

  const confidence = source?.similarity !== undefined
    ? `${Math.max(0, Math.min(100, source.similarity * 100)).toFixed(0)}% match`
    : null;

  return (
    <span
      className={styles.chipContainer}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onFocus={() => setHovered(true)}
      onBlur={() => setHovered(false)}
    >
      <button
        type="button"
        className={styles.citationChip}
        onClick={handleClick}
        aria-label={`Citation ${position}: ${source?.filename || "Source"}`}
        tabIndex={0}
      >
        {position}
      </button>

      {hovered && (
        <span className={styles.tooltip} role="tooltip">
          <span className={styles.tooltipTop}>
            <FileText size={13} className={styles.tooltipIcon} />
            <strong className={styles.tooltipFilename}>
              {source?.filename || `Source #${position}`}
            </strong>
          </span>
          <span className={styles.tooltipDetails}>
            <span className={styles.tooltipLocation}>
              {source ? formatSourceLocation(source) : "Referenced section"}
            </span>
            {confidence && (
              <span className={styles.tooltipConfidence}>{confidence}</span>
            )}
          </span>
          <span className={styles.tooltipAction}>Click to view document passage →</span>
        </span>
      )}
    </span>
  );
}

/**
 * Pre-processes markdown text to convert citations like [1], [2], or [1, 2]
 * into citation markdown links like [1](#citation-1) [2](#citation-2).
 * Skips image links ![alt](url) and markdown links [text](url).
 */
function preprocessCitations(text: string): string {
  return text.replace(/(?<!\!)\[(\d+(?:\s*,\s*\d+)*)\](?!\()/g, (_match, group) => {
    const list = group
      .split(",")
      .map((item: string) => item.trim())
      .filter(Boolean);
    return list.map((num: string) => `[${num}](#citation-${num})`).join(" ");
  });
}

export interface ChatMarkdownProps {
  content: string;
  sources?: RAGSource[];
  onOpenSource?: (source: RAGSource) => void;
}

export function ChatMarkdown({
  content,
  sources = [],
  onOpenSource,
}: ChatMarkdownProps) {
  const processed = preprocessCitations(content);

  return (
    <div className={styles.markdownBody}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children, ...props }) => {
            const citationMatch = href?.match(/^#citation-(\d+)$/);
            if (citationMatch) {
              const position = parseInt(citationMatch[1], 10);
              const source = sources.find((s) => s.position === position);
              return (
                <CitationChip
                  position={position}
                  source={source}
                  onOpenSource={onOpenSource}
                />
              );
            }
            return (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className={styles.externalLink}
                {...props}
              >
                <span>{children}</span>
                <ExternalLink size={12} className={styles.linkIcon} />
              </a>
            );
          },
          p: ({ children }) => <p className={styles.paragraph}>{children}</p>,
          ul: ({ children }) => <ul className={styles.unorderedList}>{children}</ul>,
          ol: ({ children }) => <ol className={styles.orderedList}>{children}</ol>,
          li: ({ children }) => <li className={styles.listItem}>{children}</li>,
          strong: ({ children }) => <strong className={styles.strong}>{children}</strong>,
          em: ({ children }) => <em className={styles.em}>{children}</em>,
          h1: ({ children }) => <h3 className={styles.heading1}>{children}</h3>,
          h2: ({ children }) => <h4 className={styles.heading2}>{children}</h4>,
          h3: ({ children }) => <h5 className={styles.heading3}>{children}</h5>,
          h4: ({ children }) => <h6 className={styles.heading4}>{children}</h6>,
          blockquote: ({ children }) => (
            <blockquote className={styles.blockquote}>{children}</blockquote>
          ),
          table: ({ children }) => (
            <div className={styles.tableWrapper}>
              <table className={styles.table}>{children}</table>
            </div>
          ),
          th: ({ children }) => <th className={styles.tableHeaderCell}>{children}</th>,
          td: ({ children }) => <td className={styles.tableCell}>{children}</td>,
          hr: () => <hr className={styles.hr} />,
          code: ({ className, children, ...props }) => {
            const match = /language-(\w+)/.exec(className || "");
            const textContent = String(children).replace(/\n$/, "");
            const isMultiline = textContent.includes("\n");

            if (!match && !isMultiline) {
              return (
                <code className={styles.inlineCode} {...props}>
                  {children}
                </code>
              );
            }

            return (
              <div className={styles.codeBlockWrapper}>
                {match && <span className={styles.codeLanguage}>{match[1]}</span>}
                <pre className={styles.pre}>
                  <code className={styles.codeBlock} {...props}>
                    {textContent}
                  </code>
                </pre>
              </div>
            );
          },
        }}
      >
        {processed}
      </ReactMarkdown>
    </div>
  );
}
