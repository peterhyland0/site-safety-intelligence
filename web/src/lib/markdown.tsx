/**
 * Tiny markdown renderer for the foreman assistant's phone-sized answers.
 *
 * Builds React elements directly (never innerHTML), so model output can't inject markup.
 * Supports: paragraphs, line breaks, #/##/### headings, - / * / 1. lists, GFM tables,
 * **bold**, *italic* / _italic_, `code` and [links](https://…).
 */
import type { ReactNode } from "react";

const INLINE = /(\*\*[^*]+?\*\*|__[^_]+?__|`[^`]+?`|\[[^\]]+?\]\([^)\s]+?\)|\*[^*\s][^*]*?\*|(?<![A-Za-z0-9])_[^_\s][^_]*?_(?![A-Za-z0-9]))/g;

function safeHref(href: string): string | null {
  if (/^https?:\/\//i.test(href)) return href;
  if (href.startsWith("/") && !href.startsWith("//")) return href;
  return null;
}

export function renderInline(text: string, keyPrefix = "i"): ReactNode[] {
  const out: ReactNode[] = [];
  let last = 0;
  let n = 0;
  for (const m of text.matchAll(INLINE)) {
    const tok = m[0];
    const start = m.index ?? 0;
    if (start > last) out.push(text.slice(last, start));
    const key = `${keyPrefix}-${n++}`;
    if (tok.startsWith("**") || tok.startsWith("__")) {
      out.push(<strong key={key}>{renderInline(tok.slice(2, -2), key)}</strong>);
    } else if (tok.startsWith("`")) {
      out.push(
        <code key={key} className="rounded bg-surface-2 px-1 py-0.5 font-mono text-[0.9em]">
          {tok.slice(1, -1)}
        </code>,
      );
    } else if (tok.startsWith("[")) {
      const lm = /^\[([^\]]+)\]\(([^)\s]+)\)$/.exec(tok);
      const href = lm ? safeHref(lm[2]) : null;
      if (lm && href) {
        const external = /^https?:/i.test(href);
        out.push(
          <a
            key={key}
            href={href}
            className="link"
            {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
          >
            {renderInline(lm[1], key)}
          </a>,
        );
      } else {
        out.push(lm ? lm[1] : tok);
      }
    } else {
      out.push(<em key={key}>{renderInline(tok.slice(1, -1), key)}</em>);
    }
    last = start + tok.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

function withBreaks(lines: string[], keyPrefix: string): ReactNode[] {
  const out: ReactNode[] = [];
  lines.forEach((l, i) => {
    if (i > 0) out.push(<br key={`${keyPrefix}-br${i}`} />);
    out.push(...renderInline(l, `${keyPrefix}-${i}`));
  });
  return out;
}

const UL = /^\s*[-*•]\s+(.*)$/;
const OL = /^\s*(\d+)[.)]\s+(.*)$/;
const H = /^(#{1,4})\s+(.*)$/;
const TABLE_SEP = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/;

function splitRow(line: string): string[] {
  let s = line.trim();
  if (s.startsWith("|")) s = s.slice(1);
  if (s.endsWith("|")) s = s.slice(0, -1);
  return s.split("|").map((c) => c.trim());
}

export function Markdown({ text, className }: { text: string; className?: string }) {
  const lines = text.replace(/\r\n/g, "\n").split("\n");
  const blocks: ReactNode[] = [];
  let i = 0;
  let b = 0;

  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      i++;
      continue;
    }
    const key = `b${b++}`;

    const h = H.exec(line);
    if (h) {
      blocks.push(
        <p key={key} className="font-semibold text-ink">
          {renderInline(h[2], key)}
        </p>,
      );
      i++;
      continue;
    }

    // GFM table: header row, separator row, body rows.
    if (line.includes("|") && i + 1 < lines.length && TABLE_SEP.test(lines[i + 1])) {
      const header = splitRow(line);
      const body: string[][] = [];
      i += 2;
      while (i < lines.length && lines[i].includes("|") && lines[i].trim()) {
        body.push(splitRow(lines[i]));
        i++;
      }
      blocks.push(
        <div key={key} className="-mx-1 overflow-x-auto">
          <table className="w-full border-collapse text-left text-sm">
            <thead>
              <tr>
                {header.map((c, ci) => (
                  <th key={ci} scope="col" className="border-b border-line px-1 py-1 font-semibold">
                    {renderInline(c, `${key}-h${ci}`)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {body.map((r, ri) => (
                <tr key={ri}>
                  {header.map((_, ci) => (
                    <td key={ci} className="border-b border-line px-1 py-1 align-top tabular-nums">
                      {renderInline(r[ci] ?? "", `${key}-${ri}-${ci}`)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      continue;
    }

    if (UL.test(line) || OL.test(line)) {
      const ordered = !UL.test(line);
      const items: string[] = [];
      while (i < lines.length) {
        const m = ordered ? OL.exec(lines[i]) : UL.exec(lines[i]);
        if (m) {
          items.push(ordered ? m[2] : m[1]);
          i++;
        } else if (lines[i].trim() && /^\s{2,}/.test(lines[i]) && items.length) {
          items[items.length - 1] += ` ${lines[i].trim()}`; // continuation line
          i++;
        } else break;
      }
      const ListTag = ordered ? "ol" : "ul";
      blocks.push(
        <ListTag key={key} className={`${ordered ? "list-decimal" : "list-disc"} space-y-1 pl-5`}>
          {items.map((it, ii) => (
            <li key={ii}>{renderInline(it, `${key}-${ii}`)}</li>
          ))}
        </ListTag>,
      );
      continue;
    }

    // Paragraph: consecutive non-blank lines that don't start another block.
    const para: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() &&
      !H.test(lines[i]) &&
      !UL.test(lines[i]) &&
      !OL.test(lines[i]) &&
      !(lines[i].includes("|") && i + 1 < lines.length && TABLE_SEP.test(lines[i + 1]))
    ) {
      para.push(lines[i]);
      i++;
    }
    if (para.length === 0) {
      para.push(lines[i]);
      i++;
    }
    blocks.push(<p key={key}>{withBreaks(para, key)}</p>);
  }

  return <div className={`space-y-2 ${className ?? ""}`}>{blocks}</div>;
}
