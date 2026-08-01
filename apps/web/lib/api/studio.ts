import { api, queryString, type QueryParams } from "./client";
import type { PaginatedItems } from "@/lib/types";

export type StudioList<T = Record<string, unknown>> = PaginatedItems<T>;

export const listStudio = <T = Record<string, unknown>>(path: string, params: QueryParams = { page_size: 5 }) =>
  api.get<StudioList<T>>(`${path}${queryString(params)}`);

export const getStudioHealth = () => api.get<Record<string, unknown>>("/health");
export const getStudioDatabaseHealth = () => api.get<Record<string, unknown>>("/health/db");
export const getStudioEnvironment = () => api.get<Record<string, unknown>>("/system/env");
export const getActivationGate = () => api.get<Record<string, unknown>>("/evaluation/core-algorithm/activation-gate");
