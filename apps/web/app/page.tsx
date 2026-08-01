import { CompanionHome } from "@/features/home/CompanionHome";
import "../styles/companion-home.css";

type HomeSearchParams = Record<string, string | string[] | undefined>;

function first(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value;
}

function page(value: string | string[] | undefined) {
  const parsed = Number.parseInt(first(value) ?? "1", 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
}

export default async function HomePage({ searchParams }: { searchParams: Promise<HomeSearchParams> }) {
  const params = await searchParams;
  const mode = first(params.mode) === "multi" ? "multi" : "single";
  return <CompanionHome
    mode={mode}
    selectedCompanionId={first(params.companion_id)}
    activePage={page(params.active_page)}
    archivedPage={page(params.archived_page)}
    roomPage={page(params.room_page)}
    singleQuery={first(params.single_q) ?? ""}
    roomQuery={first(params.room_q) ?? ""}
  />;
}
