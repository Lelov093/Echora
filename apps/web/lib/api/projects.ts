import { api, queryString, type QueryParams } from "./client";
import type { PaginatedItems, ProjectTask } from "@/lib/types";

export interface ProjectMilestone {
  id: string;
  title: string;
  status: string;
  priority?: number;
  target_at?: string | null;
}

export interface ProjectTaskEvent {
  id: string;
  project_task_id: string;
  event_type: string;
  previous_status?: string | null;
  new_status?: string | null;
  description?: string | null;
}

export interface ProjectTaskEvidenceLink {
  id: string;
  project_task_id: string;
  evidence_type: string;
  evidence_id?: string | null;
  relevance_score?: number | null;
}

export function listProjectMilestones(params?: QueryParams) {
  return api.get<PaginatedItems<ProjectMilestone>>(`/project-milestones${queryString(params)}`);
}
export function createProjectMilestone(data: Partial<ProjectMilestone>) {
  return api.post<ProjectMilestone>("/project-milestones", data);
}
export function getProjectMilestone(id: string) {
  return api.get<ProjectMilestone>(`/project-milestones/${id}`);
}
export function updateProjectMilestone(id: string, data: Partial<ProjectMilestone>) {
  return api.patch<ProjectMilestone>(`/project-milestones/${id}`, data);
}
export function listProjectTasks(params?: QueryParams) {
  return api.get<PaginatedItems<ProjectTask>>(`/project-tasks${queryString(params)}`);
}
export function createProjectTask(data: Partial<ProjectTask>) {
  return api.post<ProjectTask>("/project-tasks", data);
}
export function getProjectTask(id: string) {
  return api.get<ProjectTask>(`/project-tasks/${id}`);
}
export function updateProjectTask(id: string, data: Partial<ProjectTask>) {
  return api.patch<ProjectTask>(`/project-tasks/${id}`, data);
}
export function completeProjectTask(id: string, data?: Record<string, unknown>) {
  return api.post<ProjectTask>(`/project-tasks/${id}/complete`, data);
}
export function listProjectTaskEvents(id: string) {
  return api.get<PaginatedItems<ProjectTaskEvent>>(`/project-tasks/${id}/events`);
}
export function createProjectTaskEvidenceLink(id: string, data: Partial<ProjectTaskEvidenceLink>) {
  return api.post<ProjectTaskEvidenceLink>(`/project-tasks/${id}/evidence-links`, data);
}
