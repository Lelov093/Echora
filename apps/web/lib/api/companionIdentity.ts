import { apiPatch, apiGet } from "./client";
import type {
  CompanionBoundaryProfile,
  CompanionIdentityProfile,
  CompanionPersonaProfile,
  CompanionRelationshipContract,
} from "@/lib/types";

export function getCompanionIdentity(companionId: string) {
  return apiGet<CompanionIdentityProfile>(`/companions/${companionId}/identity`);
}

export function patchCompanionIdentity(companionId: string, data: Record<string, unknown>) {
  return apiPatch<CompanionIdentityProfile>(`/companions/${companionId}/identity`, data);
}

export function getCompanionPersona(companionId: string) {
  return apiGet<CompanionPersonaProfile>(`/companions/${companionId}/persona`);
}

export function patchCompanionPersona(companionId: string, data: Record<string, unknown>) {
  return apiPatch<CompanionPersonaProfile>(`/companions/${companionId}/persona`, data);
}

export function getCompanionContract(companionId: string) {
  return apiGet<CompanionRelationshipContract>(`/companions/${companionId}/contract`);
}

export function patchCompanionContract(companionId: string, data: Record<string, unknown>) {
  return apiPatch<CompanionRelationshipContract>(`/companions/${companionId}/contract`, data);
}

export function getCompanionBoundary(companionId: string) {
  return apiGet<CompanionBoundaryProfile>(`/companions/${companionId}/boundary`);
}

export function patchCompanionBoundary(companionId: string, data: Record<string, unknown>) {
  return apiPatch<CompanionBoundaryProfile>(`/companions/${companionId}/boundary`, data);
}
