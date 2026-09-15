/**
 * ArchScale — Project Memory API (M8)
 */

import { request } from './client';
import type { ApiSuccessResponse, MemorySearchResult, ProjectMemoryOverview } from '../types';

export interface MemorySearchParams {
  project_id: string;
  query?: string;
  item_type?: string;
  responsible_party?: string;
  status?: string;
  deadline?: string;
  limit?: number;
}

export async function getProjectOverview(projectId: string): Promise<ProjectMemoryOverview> {
  const res = await request<ApiSuccessResponse<ProjectMemoryOverview>>(`/api/v1/memory/project/${encodeURIComponent(projectId)}`);
  return res.data;
}

export async function searchProjectMemory(params: MemorySearchParams): Promise<MemorySearchResult> {
  const res = await request<ApiSuccessResponse<MemorySearchResult>>('/api/v1/memory/search', {
    method: 'POST',
    body: JSON.stringify({
      project_id: params.project_id,
      query: params.query || '',
      item_type: params.item_type && params.item_type !== 'all' ? params.item_type : null,
      responsible_party: params.responsible_party || null,
      status: params.status && params.status !== 'all' ? params.status : null,
      deadline: params.deadline || null,
      limit: params.limit || 50,
    }),
  });
  return res.data;
}

export async function indexMemoryItem(payload: {
  project_id: string;
  item_type: string;
  source_id: string;
  communication_id: string;
  title: string;
  content: string;
  evidence?: string | null;
  metadata?: Record<string, any>;
}): Promise<any> {
  const res = await request<ApiSuccessResponse<any>>('/api/v1/memory/index', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  return res.data;
}
