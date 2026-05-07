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
  // backend canonical fields
  business_name?: string;
  application_status?: string;
  service_type?: string;
  sws_reference_no?: string;
  submitted_at?: string;
  last_synced_at?: string | null;
  // legacy aliases (kept for backwards compat in older UI code)
  entity_name?: string;
  status?: string;
  created_at?: string;
  updated_at?: string;
  department_records?: DepartmentRecord[];
}

export interface SyncEvent {
  id: string;
  direction: 'sws_to_dept' | 'dept_to_sws';
  // backend canonical
  department_name?: string;
  initiated_at?: string;
  completed_at?: string | null;
  has_conflict?: boolean;
  attempt_count?: number;
  error_message?: string | null;
  // legacy aliases (some pages may still read these)
  department?: string;
  timestamp?: string;
  ubid: string;
  event_type: string;
  status: 'completed' | 'pending' | 'conflict' | 'failed';
  source_schema?: Record<string, unknown>;
  translated_schema?: Record<string, unknown>;
  payload_hash?: string;
}

export interface Conflict {
  id: string;
  application_id?: string;
  ubid: string;
  // backend canonical
  department_name?: string;
  detected_at?: string;
  resolution?: string; // unresolved | sws_wins | dept_wins | manual | merged
  // legacy aliases (used by some pages)
  department?: string;
  status?: 'unresolved' | 'resolved';
  created_at?: string;
  field_name: string;
  sws_value: string;
  dept_value: string;
  severity: 'critical' | 'warning' | 'info';
  resolved_value?: string;
  resolver_notes?: string;
  resolution_notes?: string;
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

// "Sync All" — runs both directions for every UBID in one shot.
// The /sync/all endpoint accepts no body and returns a summary.
export interface SyncAllResult {
  sws_to_dept: { applications_processed: number; departments_synced: number; conflicts_detected: number };
  dept_to_sws: { departments_processed: number; records_synced: number; conflicts_detected: number };
}

export function syncAll(): Promise<SyncAllResult> {
  return request<SyncAllResult>('/sync/all', { method: 'POST' });
}

// Legacy aliases — both call /sync/all so old buttons keep working
export function syncSwsToDept(): Promise<SyncAllResult> {
  return syncAll();
}

export function syncDeptToSws(): Promise<SyncAllResult> {
  return syncAll();
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
  data: { resolution?: string; resolved_value: string; resolution_notes?: string; notes?: string },
): Promise<Conflict> {
  // Backend ResolveConflictRequest expects: { resolution, resolved_value, notes }
  // - resolution defaults to "manual" when caller doesn't provide one (legacy UI passes resolved_value only)
  const body = {
    resolution: data.resolution ?? 'manual',
    resolved_value: data.resolved_value,
    notes: data.notes ?? data.resolution_notes ?? '',
  };
  return request<Conflict>(`/conflicts/${id}/resolve`, {
    method: 'PUT',
    body: JSON.stringify(body),
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
