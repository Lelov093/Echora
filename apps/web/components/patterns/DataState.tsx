import { AlertCircle, CircleOff, LoaderCircle, LockKeyhole } from "lucide-react";

type DataStateKind = "loading" | "empty" | "unavailable" | "permission" | "error" | "partial";

type DataStateProps = {
  kind: DataStateKind;
  title: string;
  description?: string;
  action?: React.ReactNode;
};

const iconByKind = {
  loading: LoaderCircle,
  empty: CircleOff,
  unavailable: CircleOff,
  permission: LockKeyhole,
  error: AlertCircle,
  partial: AlertCircle,
} satisfies Record<DataStateKind, typeof AlertCircle>;

export function DataState({ kind, title, description, action }: DataStateProps) {
  const Icon = iconByKind[kind];
  const urgent = kind === "error" || kind === "permission";

  return (
    <section
      className="orbital-data-state"
      role={urgent ? "alert" : "status"}
      aria-live={urgent ? "assertive" : "polite"}
      aria-atomic="true"
      aria-busy={kind === "loading"}
    >
      <div>
        <div className="orbital-data-state-icon" aria-hidden="true">
          <Icon size={20} className={kind === "loading" ? "animate-spin" : undefined} />
        </div>
        <h2>{title}</h2>
        {description ? <p>{description}</p> : null}
        {action ? <div>{action}</div> : null}
      </div>
    </section>
  );
}
