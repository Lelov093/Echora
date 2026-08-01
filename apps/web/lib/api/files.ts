import { api, queryString, type QueryParams } from "./client";
import type { FileDocument, PaginatedItems } from "@/lib/types";

export interface FileSource {
  id: string;
  source_type: string;
  name: string;
  uri?: string | null;
  status: string;
}

export interface FileChunk {
  id: string;
  file_document_id: string;
  chunk_index: number;
  content: string;
  status: string;
}

export interface FileContextUsage {
  id: string;
  trace_run_id?: string | null;
  file_document_id?: string | null;
  file_chunk_ids?: string[];
  usage_purpose: string;
  evidence_score?: number | null;
}

export function listFileSources(params?: QueryParams) {
  return api.get<PaginatedItems<FileSource>>(`/file-sources${queryString(params)}`);
}
export function createFileSource(data: Partial<FileSource>) {
  return api.post<FileSource>("/file-sources", data);
}
export function listFileDocuments(params?: QueryParams) {
  return api.get<PaginatedItems<FileDocument>>(`/file-documents${queryString(params)}`);
}
export function createFileDocument(data: Partial<FileDocument>) {
  return api.post<FileDocument>("/file-documents", data);
}
export function getFileDocument(id: string) {
  return api.get<FileDocument>(`/file-documents/${id}`);
}
export function processFileDocument(id: string, data: Record<string, unknown>) {
  return api.post<FileDocument>(`/file-documents/${id}/process`, data);
}
export function listFileChunks(documentId: string) {
  return api.get<PaginatedItems<FileChunk>>(`/file-documents/${documentId}/chunks`);
}
export function searchFileChunks(params?: QueryParams) {
  return api.get<PaginatedItems<FileChunk>>(`/file-chunks/search${queryString(params)}`);
}
export function listFileContextUsages(params?: QueryParams) {
  return api.get<PaginatedItems<FileContextUsage>>(`/file-context-usages${queryString(params)}`);
}
export function getFileContextUsage(id: string) {
  return api.get<FileContextUsage>(`/file-context-usages/${id}`);
}
