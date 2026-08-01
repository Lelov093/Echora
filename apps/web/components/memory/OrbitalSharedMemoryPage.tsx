import SharedMemoryPageBody from "@/components/page-bodies/SharedMemoryPageBody";
import { OrbitalMemoryDomainNav } from "./OrbitalMemoryDomainNav";

export function OrbitalSharedMemoryPage() {
  return (
    <div className="orbital-domain-page orbital-domain-embedded-workspace orbital-domain-shared-memory">
      <OrbitalMemoryDomainNav />
      <header className="orbital-domain-page-header">
        <div>
          <span>Studio / Cross-scope review</span>
          <h1>Shared Memory Review</h1>
          <p>Private-to-shared, shared-to-private, and cross-Companion writes remain explicit review decisions.</p>
        </div>
      </header>
      <div className="orbital-domain-page-body"><SharedMemoryPageBody /></div>
    </div>
  );
}
