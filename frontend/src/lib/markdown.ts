// Minimal, safe Markdown -> blocks parser for reports (headings, paragraphs, lists, **bold**, _italic_).
// It never produces HTML strings, so report content cannot inject markup.
export type Inline = { text: string; bold?: boolean; italic?: boolean };
export type Block =
  | { kind: "h1" | "h2" | "h3"; text: string }
  | { kind: "p"; parts: Inline[] }
  | { kind: "ul"; items: Inline[][] };

export function parseInline(s: string): Inline[] {
  const out: Inline[] = [];
  const re = /(\*\*[^*]+\*\*|_[^_]+_)/g;
  let last = 0;
  for (const m of s.matchAll(re)) {
    const i = m.index ?? 0;
    if (i > last) out.push({ text: s.slice(last, i) });
    const tok = m[0];
    out.push(tok.startsWith("**") ? { text: tok.slice(2, -2), bold: true } : { text: tok.slice(1, -1), italic: true });
    last = i + tok.length;
  }
  if (last < s.length) out.push({ text: s.slice(last) });
  return out;
}

export function parseMarkdown(md: string): Block[] {
  const blocks: Block[] = [];
  let list: Inline[][] | null = null;
  let para: string[] = [];
  const flushPara = () => { if (para.length) { blocks.push({ kind: "p", parts: parseInline(para.join(" ")) }); para = []; } };
  const flushList = () => { if (list) { blocks.push({ kind: "ul", items: list }); list = null; } };
  for (const raw of md.split("\n")) {
    const line = raw.trimEnd();
    const h = /^(#{1,3}) (.*)$/.exec(line);
    if (h) { flushPara(); flushList(); blocks.push({ kind: `h${h[1].length}` as "h1" | "h2" | "h3", text: h[2] }); continue; }
    if (/^- /.test(line)) { flushPara(); (list ??= []).push(parseInline(line.slice(2))); continue; }
    if (!line.trim()) { flushPara(); flushList(); continue; }
    flushList(); para.push(line.trim());
  }
  flushPara(); flushList();
  return blocks;
}
