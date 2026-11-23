export type CitationSpan = { start: number; end: number; label: string };

const YEAR = String.raw`(?:19|20)\d{2}[a-z]?`;
const NARRATIVE = new RegExp(
  String.raw`\b[A-Z][\p{L}'’-]+(?:\s+et\s+al\.?|\s+(?:and|&)\s+[A-Z][\p{L}'’-]+)?\s*\(${YEAR}\)`,
  'gu',
);
const GROUP = /[[(]([^[\]()]*)[\])]/g;
const AUTHOR_YEAR = new RegExp(String.raw`\p{Lu}[^;]*\b${YEAR}\b`, 'u');
const NUMERIC = /^\s*\d+(?:\s*[-–,]\s*\d+)*\s*$/;

/** Detecta referencias habituales para que el usuario elija la cita objetivo. */
export function detectCitations(text: string): CitationSpan[] {
  const found: CitationSpan[] = [];
  const add = (start: number, end: number) => {
    if (found.some((c) => start < c.end && end > c.start)) return;
    found.push({ start, end, label: text.slice(start, end) });
  };
  for (const match of text.matchAll(NARRATIVE)) add(match.index, match.index + match[0].length);
  for (const match of text.matchAll(GROUP)) {
    const inner = match[1];
    const open = match.index + 1;
    const numeric = match[0].startsWith('[') && NUMERIC.test(inner);
    const separator = numeric ? /[,;]/ : /;/;
    const parts: { start: number; end: number }[] = [];
    let offset = 0;
    for (const raw of inner.split(separator)) {
      const lead = raw.length - raw.trimStart().length;
      const value = raw.trim();
      if (value && (numeric ? /^\d+(?:\s*[-–]\s*\d+)?$/.test(value) : AUTHOR_YEAR.test(value)))
        parts.push({ start: open + offset + lead, end: open + offset + lead + value.length });
      offset += raw.length + 1;
    }
    if (parts.length === 1 && inner.split(separator).length === 1)
      add(match.index, match.index + match[0].length);
    else parts.forEach((part) => add(part.start, part.end));
  }
  return found.sort((a, b) => a.start - b.start);
}

export function markCitation(text: string, span: { start: number; end: number }) {
  return `${text.slice(0, span.start)}TARGETCIT${text.slice(span.end)}`;
}
