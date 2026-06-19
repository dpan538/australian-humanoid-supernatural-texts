import Link from "next/link";

export default function AboutPage() {
  return (
    <main className="terminal-shell">
      <div className="noise-layer" aria-hidden="true" />
      <div className="terminal-stage">
        <section className="view-area view-area-about" aria-label="About this archive terminal">
          <div className="about-view">
            <div className="about-copy">
              <span className="tiny-label">ABOUT / PUBLIC DATA TERMINAL</span>
              <h1>AUSTRALIAN HUMANOID SUPERNATURAL TEXTS</h1>
              <p>
                This project presents a research database and public display system for tracing how humanoid or humanoid-adjacent supernatural figures appear in Australian public texts.
              </p>
              <p>
                Records are organised by figure, source, period, query pathway, publication context, and available location evidence so later analysis can separate discourse patterns from collection noise.
              </p>
              <p>
                The corpus is limited to public, published, openly discoverable material. Source voice, publicness, mediation, and ethics flags are retained as research variables rather than flattened into a single folklore category.
              </p>
            </div>
            <div className="about-actions">
              <Link href="/map">MAP</Link>
              <Link href="/dashboard">DASHBOARD</Link>
              <Link href="/density">DENSITY</Link>
              <Link href="/source">SOURCE</Link>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
