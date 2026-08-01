import { redirect } from "next/navigation";

export default function DiagnosticsPage() {
  redirect("/settings/system/diagnostics");
}
