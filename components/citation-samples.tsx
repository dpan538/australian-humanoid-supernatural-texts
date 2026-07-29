"use client";

import { useState } from "react";
import type { CitationSample } from "@/lib/citations";

type CitationSamplesProps = {
  samples: CitationSample[];
  compact?: boolean;
};

export function CitationSamples({ samples, compact = false }: CitationSamplesProps) {
  const [copiedId, setCopiedId] = useState<string | null>(null);

  async function copyCitation(sample: CitationSample) {
    try {
      await navigator.clipboard.writeText(sample.text);
    } catch {
      const field = document.createElement("textarea");
      field.value = sample.text;
      field.setAttribute("readonly", "");
      field.style.position = "fixed";
      field.style.opacity = "0";
      document.body.appendChild(field);
      field.select();
      document.execCommand("copy");
      field.remove();
    }
    setCopiedId(sample.id);
    window.setTimeout(() => {
      setCopiedId((current) => (current === sample.id ? null : current));
    }, 6000);
  }

  return (
    <div className={compact ? "citation-samples citation-samples-compact" : "citation-samples"}>
      {samples.map((sample, index) => (
        <article className="citation-sample" key={sample.id}>
          <header>
            <span>{String(index + 1).padStart(2, "0")}</span>
            <strong>{sample.label}</strong>
            <button type="button" onClick={() => void copyCitation(sample)} aria-label={`Copy ${sample.label} citation`}>
              {copiedId === sample.id ? "COPIED" : "COPY"}
            </button>
          </header>
          <pre>{sample.text}</pre>
        </article>
      ))}
      <p className="citation-copy-status" role="status" aria-live="polite">
        {copiedId ? `${samples.find((sample) => sample.id === copiedId)?.label ?? "Citation"} copied to clipboard.` : ""}
      </p>
    </div>
  );
}
