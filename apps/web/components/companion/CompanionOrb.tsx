import { LockKeyhole } from "lucide-react";

const signatures = ["violet", "blue", "mint", "rose"] as const;

export function CompanionOrb({ name, index = 0, size = "medium" }: { name: string; index?: number; size?: "small" | "medium" | "large" }) {
  const signature = signatures[index % signatures.length];
  return (
    <div className={`companion-orb is-${signature} is-${size}`} aria-label={`${name} 的私有伙伴空间`}>
      <span className="companion-orb-core" />
      <span className="companion-orb-ring is-one" />
      <span className="companion-orb-ring is-two" />
      <span className="companion-orb-lock"><LockKeyhole size={13} aria-hidden="true" /></span>
    </div>
  );
}
