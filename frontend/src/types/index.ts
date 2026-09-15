/**
 * ArchScale — Frontend TypeScript Types
 * Strictly mirrors the backend Pydantic models (M1–M9).
 */

export type MemoryItemType = 'communication' | 'task' | 'decision' | 'approval' | 'action';

export interface CommunicationRecord {
  project_id: string;
  communication_id: string;
  source_type: 'text' | 'transcript' | 'txt_file' | 'pdf_file';
  timestamp: string;
  raw_content: string;
  metadata: Record<string, any>;
  storage_path?: string | null;
  status: 'pending' | 'ingested' | 'failed';
}

export interface UnderstandingResult {
  project_id: string;
  communication_id: string;
  concise_summary: string;
  detailed_summary: string;
  topics: string[];
  stakeholders: string[];
  communication_type: string;
  important_context: string[];
  analyzed_at?: string | null;
  llm_model?: string;
}

export interface ExtractedAction {
  action_id: string;
  title: string;
  description: string;
  action_type: string;
  evidence: string;
  confidence: number;
}

export interface ResponsibilityAssignment {
  action_id: string;
  responsible_party: string;
  party_type: string;
  confidence: number;
  evidence: string;
}

export interface DeadlineAssignment {
  action_id: string;
  deadline: string;
  deadline_type: string;
  normalized_deadline?: string | null;
  confidence: number;
  evidence: string;
}

export interface ExtractedDecision {
  decision_id: string;
  item_type: 'decision' | 'approval';
  description: string;
  subject?: string | null;
  status: 'decided' | 'approved' | 'rejected';
  evidence: string;
  confidence: number;
}

export interface StructuredTask {
  task_id: string;
  project_id: string;
  communication_id: string;
  action_id: string;
  title: string;
  description: string;
  responsible_party?: string | null;
  responsibility_type?: string | null;
  deadline?: string | null;
  deadline_type: string;
  normalized_deadline?: string | null;
  status: 'pending' | 'in_progress' | 'completed' | 'blocked' | 'cancelled';
  priority: 'low' | 'medium' | 'high' | 'urgent' | 'unspecified';
  evidence: string;
  decision_context: string[];
  created_at: string;
}

export interface ProjectMemoryOverview {
  project_id: string;
  communications: number;
  tasks: number;
  decisions: number;
  approvals: number;
  memory_items: number;
}

export interface MemorySearchResultItem {
  memory_id: string;
  project_id: string;
  item_type: MemoryItemType;
  source_id: string;
  communication_id: string;
  title: string;
  content: string;
  evidence?: string | null;
  metadata: Record<string, any>;
  score: number;
  retrieval_mode: string;
}

export interface MemorySearchResult {
  project_id: string;
  query: string;
  results: MemorySearchResultItem[];
  result_count: number;
  retrieval_mode: string;
}

export interface AgentSourceItem {
  memory_id: string;
  item_type: string;
  source_id: string;
  communication_id: string;
  title: string;
  evidence?: string | null;
  score: number;
}

export interface AgentResponse {
  project_id: string;
  query: string;
  intent: string;
  answer: string;
  grounded: boolean;
  result_count: number;
  sources: AgentSourceItem[];
  generated_at: string;
}

export interface ApiSuccessResponse<T> {
  success: true;
  data: T;
}

export interface ApiErrorResponse {
  success: false;
  error: string;
  detail?: string;
}
