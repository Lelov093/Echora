import Link from "next/link";
import { SectionNav } from "@/components/navigation/SectionNav";
import { traceNavItems } from "@/lib/navigation/routes";

export default function TraceOverviewPageBody() {
  return (
    <>
      <SectionNav title="Trace" eyebrow="Evidence and replay" items={traceNavItems} />
      <main className="echora-page domain-page">
        <section className="dynamic-glass domain-page-hero">
          <div>
            <div className="domain-chip-row">
              <span className="pill-sm pill-accent">Trace</span>
              <span className="pill-sm">Realtime</span>
              <span className="pill-sm">Channel audit</span>
            </div>
            <h1>Trace Overview</h1>
            <p>Choose a trace surface for realtime evidence, replay review, or external channel audit logs.</p>
          </div>
        </section>
        <div className="domain-three-column">
          {traceNavItems.filter((item) => item.href !== "/trace").map((item) => (
            <Link key={item.href} href={item.href} className="dynamic-glass domain-panel trace-overview-card">
              <div className="domain-panel-header">
                <div className="domain-panel-icon">T</div>
                <div>
                  <h2>{item.label}</h2>
                  <p>{item.description}</p>
                </div>
              </div>
            </Link>
          ))}
        </div>
      </main>
    </>
  );
}
