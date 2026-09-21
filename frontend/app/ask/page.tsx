"use client";

import { useState } from "react";

const TABS = ["Answer", "SQL", "Table", "Chart"] as const;
type Tab = (typeof TABS)[number];

export default function AskPage() {
  const [question, setQuestion] = useState("");
  const [tab, setTab] = useState<Tab>("Answer");

  return (
    <>
      <h1>Ask</h1>
      <input
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        placeholder="Ask a question about your data"
        style={{ width: "60%", padding: 8 }}
      />
      <div style={{ display: "flex", gap: 8, margin: "16px 0" }}>
        {TABS.map((t) => (
          <button key={t} onClick={() => setTab(t)} disabled={t === tab}>
            {t}
          </button>
        ))}
      </div>
      <p>{tab} view goes here.</p>
    </>
  );
}
