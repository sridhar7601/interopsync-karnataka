const BASE = '/api';

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
}

/* ---------- Types ---------- */

export interface DepartmentRecord {
  id: string;
  department: string;
  status: string;
  last_synced: string | null;
  data: Record<string, unknown>;
}

export interface Application {
  id: string;
  ubid: string;
  entity_name: string;
  status: string;
  created_at: string;
  updated_at: string;
  department_records?: DepartmentRecord[];
}

export interface SyncEvent {
  id: string;
  direction: 'sws_to_dept' | 'dept_to_sws';
  department: string;
  ubid: string;
  event_type: string;
  status: 'completed' | 'pending' | 'conflict' | 'failed';
  timestamp: string;
  source_schema?: Record<string, unknown>;
  translated_schema?: Record<string, unknown>;
  payload_hash?: string;
}

export interface Conflict {
  id: string;
  application_id: string;
  ubid: string;
  department: string;
  field_name: string;
  sws_value: string;
  dept_value: string;
  severity: 'critical' | 'warning' | 'info';
  status: 'unresolved' | 'resolved';
  resolved_value?: string;
  resolution_notes?: string;
  created_at: string;
  resolved_at?: string;
}

export interface ConflictStats {
  total: number;
  resolved: number;
  unresolved: number;
  by_severity: { critical: number; warning: number; info: number };
}

export interface SyncResult {
  synced: number;
  failed: number;
  conflicts: number;
  events: SyncEvent[];
}

/* ---------- Applications ---------- */

export function createApplication(data: Record<string, unknown>): Promise<Application> {
  return request<Application>('/applications/', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function listApplications(): Promise<Application[]> {
  return request<{ total: number; applications: Application[] }>('/applications/').then(
    (r) => r.applications ?? []
  );
}

export function getApplication(id: string): Promise<Application> {
  return request<Application>(`/applications/${id}`);
}

/* ---------- Sync ---------- */

export function syncSwsToDept(): Promise<SyncResult> {
  return request<SyncResult>('/sync/sws-to-dept', { method: 'POST' });
}

export function syncDeptToSws(): Promise<SyncResult> {
  return request<SyncResult>('/sync/dept-to-sws', { method: 'POST' });
}

export function listSyncEvents(): Promise<SyncEvent[]> {
  return request<{ total: number; events: SyncEvent[] }>('/sync/events').then(
    (r) => r.events ?? []
  );
}

/* ---------- Conflicts ---------- */

export function listConflicts(): Promise<Conflict[]> {
  return request<{ total: number; conflicts: Conflict[] }>('/conflicts/').then(
    (r) => r.conflicts ?? []
  );
}

export function resolveConflict(
  id: string,
  data: { resolved_value: string; resolution_notes?: string },
): Promise<Conflict> {
  return request<Conflict>(`/conflicts/${id}/resolve`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export function getConflictStats(): Promise<ConflictStats> {
  return request<ConflictStats>('/conflicts/stats');
}

/* ---------- Dashboard + AI ---------- */

export interface DashboardOverview {
  total_applications: number;
  total_department_records: number;
  total_syncs: number;
  completed: number;
  failed: number;
  pending: number;
  conflict_count: number;
  success_rate_pct: number;
  sws_to_dept: number;
  dept_to_sws: number;
  by_department: { [k: string]: number };
  unresolved_conflicts: number;
  critical_conflicts: number;
  briefing: string;
}

export function getDashboardOverview(): Promise<DashboardOverview> {
  return request<DashboardOverview>('/dashboard/overview');
}

export interface ConflictRecommendation {
  conflict_id: string;
  ai_recommendation: string;
  field_name: string;
  severity: string;
}

export function recommendConflict(id: string): Promise<ConflictRecommendation> {
  return request<ConflictRecommendation>(`/conflicts/${id}/recommend-llm`);
}

export function retryFailedSyncs(): Promise<{ retried: number; succeeded: number; still_failed: number }> {
  return request('/sync/retry-failed', { method: 'POST', body: JSON.stringify({}) });
}
