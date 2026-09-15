/**
 * ArchScale — Decisions & Approvals API (M6 & M8)
 */

import { request } from './client';
import type { ApiSuccessResponse } from '../types';

export interface DecisionItem {
  decision_id: string;
  item_type: 'decision' | 'approval';
  description: string;
  subject?: string | null;
  status: string;
  evidence: string;
  communication_id: string;
}

export async function getProjectDecisions(projectId: string): Promise<DecisionItem[]> {
  const res = await request<ApiSuccessResponse<{ project_id: string; decisions: DecisionItem[]; decision_count: number }>>(
    `/api/v1/memory/project/${encodeURIComponent(projectId)}/decisions`
  );
  return res.data.decisions || [];
}

export async function getDecisionsByCommunication(communicationId: string, projectId: string = 'villa-live-proj'): Promise<DecisionItem[]> {
  try {
    const allDecisions = await getProjectDecisions(projectId);
    return allDecisions.filter(d => d.communication_id === communicationId);
  } catch {
    return [];
  }
}

export async function extractDecisions(communicationId: string): Promise<any> {
  const res = await request<ApiSuccessResponse<any>>('/api/v1/decisions/extract', {
    method: 'POST',
    body: JSON.stringify({
      communication_id: communicationId,
    }),
  });
  return res.data;
}
