/**
 * ArchScale — Tasks API (M7 & M8)
 */

import { request } from './client';
import type { ApiSuccessResponse, StructuredTask } from '../types';

export interface TaskFilters {
  status?: string;
  responsible_party?: string;
  deadline?: string;
}

export async function getProjectTasks(projectId: string, filters: TaskFilters = {}): Promise<StructuredTask[]> {
  const params = new URLSearchParams();
  if (filters.status && filters.status !== 'all') {
    params.append('status', filters.status);
  }
  if (filters.responsible_party) {
    params.append('responsible_party', filters.responsible_party);
  }
  if (filters.deadline) {
    params.append('deadline', filters.deadline);
  }

  const queryString = params.toString() ? `?${params.toString()}` : '';
  const res = await request<ApiSuccessResponse<{ project_id: string; tasks: StructuredTask[]; task_count: number }>>(
    `/api/v1/memory/project/${encodeURIComponent(projectId)}/tasks${queryString}`
  );
  return res.data.tasks;
}

export async function structureTasks(communicationId: string): Promise<StructuredTask[]> {
  const res = await request<ApiSuccessResponse<{ project_id: string; communication_id: string; tasks: StructuredTask[]; task_count: number }>>(
    '/api/v1/tasks/structure',
    {
      method: 'POST',
      body: JSON.stringify({
        communication_id: communicationId,
      }),
    }
  );
  return res.data.tasks;
}
