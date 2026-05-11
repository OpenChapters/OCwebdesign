import { useMemo } from 'react';
import katex from 'katex';
import 'katex/dist/katex.min.css';

interface Props {
  source: string;
  className?: string;
}

// Best-effort LaTeX → HTML renderer for short snippets like worked-example
// statements and solutions. Renders inline math ($..$, \(..\)) and display
// math ($$..$$, \[..\]) via KaTeX; everything else is shown verbatim with
// whitespace preserved. Custom OpenChapters macros and complex environments
// fall back to the raw source rather than crashing the whole snippet.
const MATH_RE = /\$\$([\s\S]+?)\$\$|\\\[([\s\S]+?)\\\]|\$((?:\\.|[^$\\])+?)\$|\\\(([\s\S]+?)\\\)/g;

interface Segment {
  kind: 'text' | 'math';
  content: string;
  display?: boolean;
}

function tokenize(source: string): Segment[] {
  const out: Segment[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  MATH_RE.lastIndex = 0;
  while ((m = MATH_RE.exec(source)) !== null) {
    if (m.index > last) {
      out.push({ kind: 'text', content: source.slice(last, m.index) });
    }
    const display = m[1] !== undefined || m[2] !== undefined;
    const body = m[1] ?? m[2] ?? m[3] ?? m[4] ?? '';
    out.push({ kind: 'math', content: body, display });
    last = MATH_RE.lastIndex;
  }
  if (last < source.length) {
    out.push({ kind: 'text', content: source.slice(last) });
  }
  return out;
}

function renderMath(body: string, display: boolean): { html: string; ok: boolean } {
  try {
    return {
      html: katex.renderToString(body, {
        displayMode: display,
        throwOnError: false,
        strict: 'ignore',
      }),
      ok: true,
    };
  } catch {
    return { html: '', ok: false };
  }
}

export default function MathText({ source, className }: Props) {
  const segments = useMemo(() => tokenize(source), [source]);

  return (
    <div className={`whitespace-pre-wrap leading-relaxed ${className ?? ''}`}>
      {segments.map((seg, i) => {
        if (seg.kind === 'text') {
          return <span key={i}>{seg.content}</span>;
        }
        const { html, ok } = renderMath(seg.content, !!seg.display);
        if (!ok) {
          return (
            <code key={i} className="bg-amber-50 border border-amber-200 px-1 rounded">
              {seg.display ? '$$' : '$'}{seg.content}{seg.display ? '$$' : '$'}
            </code>
          );
        }
        return (
          <span
            key={i}
            dangerouslySetInnerHTML={{ __html: html }}
          />
        );
      })}
    </div>
  );
}
