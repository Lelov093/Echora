export function SectionHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return <div style={{ marginBottom: "1rem" }}>
    <h2 style={{ color: "#F8FAFC", fontSize: "1.1rem", fontWeight: 600, margin: 0 }}>{title}</h2>
    {subtitle && <p style={{ color: "#CBD5E1", fontSize: "0.8rem", margin: "0.2rem 0 0" }}>{subtitle}</p>}
  </div>;
}
