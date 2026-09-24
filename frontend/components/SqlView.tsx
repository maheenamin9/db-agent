"use client";

import { useState } from "react";

// A small, self-contained highlighter rather than a new dependency. Splitting on
// string literals FIRST (and never re-tokenizing inside them) matters: a naive
// keyword regex applied to the whole string would wrongly highlight a keyword that
// appears inside a value, e.g. WHERE name = 'SELECT'.
const KEYWORDS = new Set([
  "select", "from", "where", "group", "by", "order", "having", "join", "left",
  "right", "inner", "outer", "full", "on", "as", "and", "or", "not", "null",
  "is", "in", "like", "between", "limit", "offset", "with", "distinct", "case",
  "when", "then", "else", "end", "union", "all", "asc", "desc", "count", "sum",
  "avg", "min", "max", "cast", "extract", "interval", "over", "partition",
  "exists", "any", "some",
]);

function highlightPlain(text: string, keyPrefix: string) {
  return text.split(/(\b\w+\b)/g).map((part, i) => {
    const key = `${keyPrefix}-${i}`;
    if (KEYWORDS.has(part.toLowerCase())) {
      return (
        <span key={key} className="font-semibold text-purple-700">
          {part}
        </span>
      );
    }
    if (/^\d+(\.\d+)?$/.test(part)) {
      return (
        <span key={key} className="text-blue-700">
          {part}
        </span>
      );
    }
    return part;
  });
}

export default function SqlView({ sql }: { sql: string }) {
  const [copied, setCopied] = useState(false);
  // Capturing group keeps the delimiters in the split result, alternating
  // plain-text / string-literal segments. '' inside a string is an escaped quote.
  const segments = sql.split(/('(?:[^']|'')*')/g);

  const copy = () => {
    navigator.clipboard?.writeText(sql).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };

  return (
    <div className="relative">
      <button
        onClick={copy}
        className="absolute right-2 top-2 rounded border border-gray-300 bg-white px-2 py-1 text-xs text-gray-600 hover:bg-gray-50"
      >
        {copied ? "Copied!" : "Copy"}
      </button>
      <pre className="overflow-x-auto whitespace-pre-wrap rounded border border-gray-200 bg-gray-50 p-4 pr-16 text-sm">
        <code>
          {segments.map((segment, i) =>
            segment.startsWith("'") && segment.endsWith("'") && segment.length >= 2 ? (
              <span key={i} className="text-green-700">
                {segment}
              </span>
            ) : (
              <span key={i}>{highlightPlain(segment, String(i))}</span>
            )
          )}
        </code>
      </pre>
    </div>
  );
}
