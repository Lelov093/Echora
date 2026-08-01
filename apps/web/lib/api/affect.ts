import { api } from "./client";

export interface AffectExpression { label: string; tone: string; focus: string }
export interface AffectState {
  id: string; revision: number; current_event_id: string | null; expression: AffectExpression;
  expression_enabled: boolean; expression_intensity: "off" | "subtle" | "balanced";
  last_transition_at: string | null; updated_at: string | null;
}
export interface AffectEvent {
  id: string; status: "active" | "corrected" | "invalidated"; operation: string;
  summary: string; evidence_quote: string; state_revision: number; created_at: string | null;
}
interface AffectEventPage { items: AffectEvent[]; pagination: { total: number } }

export const affectApi = {
  state: (companionId: string) => api.get<AffectState | null>(`/companions/${companionId}/affect`),
  events: (companionId: string) => api.get<AffectEventPage>(`/companions/${companionId}/affect/events?page_size=20`),
  preferences: (companionId: string, expectedRevision: number, enabled: boolean, intensity: AffectState["expression_intensity"]) =>
    api.patch<AffectState>(`/companions/${companionId}/affect/preferences`, { expected_revision: expectedRevision, expression_enabled: enabled, expression_intensity: intensity }),
  correct: (companionId: string, eventId: string, revision: number) =>
    api.post(`/companions/${companionId}/affect/events/${eventId}/correct`, { expected_revision: revision, reason: "用户指出本次互动理解不准确" }),
};
