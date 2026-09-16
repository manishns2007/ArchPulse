/**
 * ArchScale — Frontend Sequential Pipeline Runner
 * Calls the existing frozen M1–M8 backend APIs in sequence with live status updates.
 */

import { request } from './client';
import type {
  CommunicationRecord,
  ExtractedAction,
  ExtractedDecision,
  StructuredTask,
  UnderstandingResult,
} from '../types';

export type PipelineStageKey =
  | 'ingest'
  | 'understand'
  | 'actions'
  | 'responsibility'
  | 'deadlines'
  | 'decisions'
  | 'tasks'
  | 'memory';

export interface PipelineStageState {
  key: PipelineStageKey;
  label: string;
  module: string;
  status: 'idle' | 'running' | 'completed' | 'failed';
  error?: string;
  data?: any;
}

export const INITIAL_PIPELINE_STAGES: PipelineStageState[] = [
  { key: 'ingest', label: 'Ingestion', module: 'M1', status: 'idle' },
  { key: 'understand', label: 'Understanding', module: 'M2', status: 'idle' },
  { key: 'actions', label: 'Action Extraction', module: 'M3', status: 'idle' },
  { key: 'responsibility', label: 'Responsibility Detection', module: 'M4', status: 'idle' },
  { key: 'deadlines', label: 'Deadline Detection', module: 'M5', status: 'idle' },
  { key: 'decisions', label: 'Decisions & Approvals', module: 'M6', status: 'idle' },
  { key: 'tasks', label: 'Structured Tasks', module: 'M7', status: 'idle' },
  { key: 'memory', label: 'Memory Indexing', module: 'M8', status: 'idle' },
];

export async function runSequentialPipeline(
  projectId: string,
  content: string,
  sourceType: 'text' | 'transcript' = 'text',
  onStageUpdate: (stageKey: PipelineStageKey, status: 'running' | 'completed' | 'failed', data?: any, error?: string) => void
): Promise<{
  communication: CommunicationRecord;
  understanding: UnderstandingResult;
  actions: ExtractedAction[];
  tasks: StructuredTask[];
  decisions: ExtractedDecision[];
}> {
  // Step 1: Ingestion (M1)
  onStageUpdate('ingest', 'running');
  let commRecord: CommunicationRecord;
  try {
    const ingestRes = await request<{ success: boolean; data: CommunicationRecord }>('/api/v1/ingest/text', {
      method: 'POST',
      body: JSON.stringify({
        project_id: projectId,
        content,
        source_type: sourceType,
      }),
    });
    commRecord = ingestRes.data;
    onStageUpdate('ingest', 'completed', commRecord);
  } catch (err: any) {
    onStageUpdate('ingest', 'failed', null, err.message);
    throw err;
  }

  const commId = commRecord.communication_id;

  // Step 2: Understanding (M2)
  onStageUpdate('understand', 'running');
  let understanding: UnderstandingResult;
  try {
    const undRes = await request<{ success: boolean; data: UnderstandingResult }>('/api/v1/understanding/analyze', {
      method: 'POST',
      body: JSON.stringify({ communication_id: commId }),
    });
    understanding = undRes.data;
    onStageUpdate('understand', 'completed', understanding);
  } catch (err: any) {
    onStageUpdate('understand', 'failed', null, err.message);
    throw err;
  }

  // Step 3: Actions (M3)
  onStageUpdate('actions', 'running');
  let actions: ExtractedAction[] = [];
  try {
    const actRes = await request<{ success: boolean; data: { actions: ExtractedAction[] } }>('/api/v1/actions/extract', {
      method: 'POST',
      body: JSON.stringify({ communication_id: commId }),
    });
    actions = actRes.data.actions || [];
    onStageUpdate('actions', 'completed', actions);
  } catch (err: any) {
    onStageUpdate('actions', 'failed', null, err.message);
    throw err;
  }

  // Step 4: Responsibility (M4)
  onStageUpdate('responsibility', 'running');
  let responsibilities: any[] = [];
  try {
    const respRes = await request<any>('/api/v1/responsibilities/extract', {
      method: 'POST',
      body: JSON.stringify({ communication_id: commId, actions }),
    });
    responsibilities = respRes.data?.assignments || [];
    onStageUpdate('responsibility', 'completed', respRes.data);
  } catch (err: any) {
    onStageUpdate('responsibility', 'failed', null, err.message);
    throw err;
  }

  // Step 5: Deadlines (M5)
  onStageUpdate('deadlines', 'running');
  let deadlines: any[] = [];
  try {
    const dlRes = await request<any>('/api/v1/deadlines/extract', {
      method: 'POST',
      body: JSON.stringify({ communication_id: commId, actions, responsibilities }),
    });
    deadlines = dlRes.data?.assignments || [];
    onStageUpdate('deadlines', 'completed', dlRes.data);
  } catch (err: any) {
    onStageUpdate('deadlines', 'failed', null, err.message);
    throw err;
  }

  // Step 6: Decisions (M6)
  onStageUpdate('decisions', 'running');
  let decisions: ExtractedDecision[] = [];
  try {
    const decRes = await request<{ success: boolean; data: { decisions: ExtractedDecision[] } }>('/api/v1/decisions/extract', {
      method: 'POST',
      body: JSON.stringify({ communication_id: commId }),
    });
    decisions = decRes.data.decisions || [];
    onStageUpdate('decisions', 'completed', decisions);
  } catch (err: any) {
    onStageUpdate('decisions', 'failed', null, err.message);
    throw err;
  }

  // Step 7: Structured Tasks (M7)
  onStageUpdate('tasks', 'running');
  let tasks: StructuredTask[] = [];
  try {
    const taskRes = await request<{ success: boolean; data: { tasks: StructuredTask[] } }>('/api/v1/tasks/structure', {
      method: 'POST',
      body: JSON.stringify({
        communication_id: commId,
        actions,
        responsibilities,
        deadlines,
        decisions,
      }),
    });
    tasks = taskRes.data.tasks || [];
    onStageUpdate('tasks', 'completed', tasks);
  } catch (err: any) {
    onStageUpdate('tasks', 'failed', null, err.message);
    throw err;
  }

  // Step 8: Memory Indexing (M8)
  onStageUpdate('memory', 'running');
  try {
    // Index communication
    await request('/api/v1/memory/index', {
      method: 'POST',
      body: JSON.stringify({
        project_id: projectId,
        item_type: 'communication',
        source_id: commId,
        communication_id: commId,
        title: understanding.concise_summary || commRecord.raw_content.slice(0, 80),
        content: understanding.detailed_summary || commRecord.raw_content,
        evidence: commRecord.raw_content.slice(0, 300),
        metadata: {
          source_type: commRecord.source_type,
          topics: understanding.topics,
          stakeholders: understanding.stakeholders,
        },
      }),
    });

    // Index decisions
    for (const dec of decisions) {
      await request('/api/v1/memory/index', {
        method: 'POST',
        body: JSON.stringify({
          project_id: projectId,
          item_type: dec.item_type === 'approval' ? 'approval' : 'decision',
          source_id: dec.decision_id,
          communication_id: commId,
          title: dec.subject ? `${dec.subject}: ${dec.description}` : dec.description,
          content: dec.description,
          evidence: dec.evidence,
          metadata: {
            subject: dec.subject,
            status: dec.status,
            confidence: dec.confidence,
          },
        }),
      });
    }

    // Index tasks
    for (const t of tasks) {
      await request('/api/v1/memory/index', {
        method: 'POST',
        body: JSON.stringify({
          project_id: projectId,
          item_type: 'task',
          source_id: t.task_id,
          communication_id: commId,
          title: t.title,
          content: t.description,
          evidence: t.evidence,
          metadata: {
            task_id: t.task_id,
            responsible_party: t.responsible_party,
            responsibility_type: t.responsibility_type,
            deadline: t.deadline,
            normalized_deadline: t.normalized_deadline,
            status: t.status,
            priority: t.priority,
          },
        }),
      });
    }

    onStageUpdate('memory', 'completed');
  } catch (err: any) {
    onStageUpdate('memory', 'failed', null, err.message);
    throw err;
  }

  return {
    communication: commRecord,
    understanding,
    actions,
    tasks,
    decisions,
  };
}
