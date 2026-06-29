import Link from "next/link";

export default function NotFound() {
  return (
    <main className="terminal-shell">
      <div className="noise-layer" aria-hidden="true" />
      <section className="status-page" aria-label="404 not found">
        <div className="status-panel status-panel-narrow">
          <span className="tiny-label">404 / ROUTE LOST</span>
          <h1>NO PUBLIC RECORD AT THIS ADDRESS</h1>
          <p>The requested route is outside the current archive interface.</p>
          <div className="status-actions">
            <Link href="/map">RETURN MAP</Link>
            <Link href="/dashboard">DASHBOARD</Link>
          </div>
        </div>
      </section>
    </main>
  );
}
