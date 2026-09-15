/**
 * ArchScale — Ingestion & Understanding APIs (M1 & M2)
 */

import { request } from './client';
import type { ApiSuccessResponse, CommunicationRecord, UnderstandingResult } from '../types';

export async function ingestText(projectId: string, content: string, sourceType: 'text' | 'transcript' = 'text'): Promise<CommunicationRecord> {
  const res = await request<ApiSuccessResponse<CommunicationRecord>>('/api/v1/ingest/text', {
    method: 'POST',
    body: JSON.stringify({
      project_id: projectId,
      content,
      source_type: sourceType,
    }),
  });
  return res.data;
}

export async function ingestFile(projectId: string, file: File, sourceType?: string): Promise<CommunicationRecord> {
  const formData = new FormData();
  formData.append('project_id', projectId);
  formData.append('file', file);
  if (sourceType) {
    formData.append('source_type', sourceType);
  }

  const res = await request<ApiSuccessResponse<CommunicationRecord>>('/api/v1/ingest/file', {
    method: 'POST',
    body: formData,
  });
  return res.data;
}

export async function getProjectCommunications(projectId: string): Promise<CommunicationRecord[]> {
  const res = await request<ApiSuccessResponse<CommunicationRecord[]>>(`/api/v1/ingest/project/${encodeURIComponent(projectId)}`);
  return res.data;
}

export async function getCommunicationById(communicationId: string): Promise<CommunicationRecord> {
  const res = await request<ApiSuccessResponse<CommunicationRecord>>(`/api/v1/ingest/${encodeURIComponent(communicationId)}`);
  return res.data;
}

export async function analyzeUnderstanding(communicationId: string): Promise<UnderstandingResult> {
  const res = await request<ApiSuccessResponse<UnderstandingResult>>('/api/v1/understand/analyze', {
    method: 'POST',
    body: JSON.stringify({
      communication_id: communicationId,
    }),
  });
  return res.data;
}
