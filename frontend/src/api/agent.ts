/**
 * ArchScale — Agentic Query API (M9)
 */

import { request } from './client';
import type { AgentResponse, ApiSuccessResponse } from '../types';

export async function queryAgent(projectId: string, query: string, useLlm: boolean = false): Promise<AgentResponse> {
  const res = await request<ApiSuccessResponse<AgentResponse>>('/api/v1/agent/query', {
    method: 'POST',
    body: JSON.stringify({
      project_id: projectId,
      query,
      use_llm: useLlm,
    }),
  });
  return res.data;
}
