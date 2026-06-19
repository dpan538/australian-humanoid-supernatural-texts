"use client";

import Link from "next/link";

export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <main className="terminal-shell">
      <div className="noise-layer" aria-hidden="true" />
      <section className="status-page" aria-label="500 error">
        <div className="status-panel status-panel-narrow">
          <span className="tiny-label">500 / INTERNAL FIELD ERROR</span>
          <h1>THE TERMINAL FAILED TO RESOLVE THIS VIEW</h1>
          <p>Retry the render, or return to a stable route.</p>
          <div className="status-actions">
            <button type="button" onClick={reset}>
              RETRY
            </button>
            <Link href="/map">MAP</Link>
            <Link href="/dashboard">DASHBOARD</Link>
          </div>
        </div>
      </section>
    </main>
  );
}
