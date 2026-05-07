import { useEffect, useState, useCallback, useMemo } from 'react'
import {
  ArrowRight,
  ArrowLeft,
  CheckCircle2,
  Clock,
  AlertTriangle,
  XCircle,
  Loader2,
  ChevronDown,
  ChevronUp,
  Filter,
  Shield,
  Activity,
} from 'lucide-react'
import type { SyncEvent } from '../api'
import { listSyncEvents } from '../api'

const statusBadge: Record<string, { cls: string; icon: typeof CheckCircle2 }> = {
  completed: { cls: 'bg-green-100 text-green-700', icon: CheckCircle2 },
  pending: { cls: 'bg-yellow-100 text-yellow-700', icon: Clock },
  conflict: { cls: 'bg-red-100 text-red-700', icon: AlertTriangle },
  failed: { cls: 'bg-gray-100 text-gray-500', icon: XCircle },
}

function StatusBadge({ status }: { status: string }) {
  const cfg = statusBadge[status] ?? statusBadge.pending
  const Icon = cfg.icon
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${cfg.cls}`}
    >
      <Icon className="h-3 w-3" />
      {status}
    </span>
  )
}

function DirectionArrow({ direction }: { direction: string }) {
  if (direction === 'sws_to_dept') {
    return (
      <span className="inline-flex items-center gap-1 text-amber-700 bg-amber-50 px-2 py-0.5 rounded text-xs font-medium">
        SWS <ArrowRight className="h-3 w-3" /> Dept
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 text-blue-700 bg-blue-50 px-2 py-0.5 rounded text-xs font-medium">
      Dept <ArrowLeft className="h-3 w-3" /> SWS
    </span>
  )
}

export default function AuditTrail() {
  const [events, setEvents] = useState<SyncEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  // Filters
  const [dirFilter, setDirFilter] = useState<string>('all')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [deptFilter, setDeptFilter] = useState<string>('all')

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await listSyncEvents()
      setEvents(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load events')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const departments = useMemo(
    () => [...new Set(events.map((e) => e.department))].sort(),
    [events],
  )

  const filtered = useMemo(() => {
    return events.filter((ev) => {
      if (dirFilter !== 'all' && ev.direction !== dirFilter) return false
      if (statusFilter !== 'all' && ev.status !== statusFilter) return false
      if (deptFilter !== 'all' && (ev.department_name ?? ev.department) !== deptFilter) return false
      return true
    })
  }, [events, dirFilter, statusFilter, deptFilter])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-amber-600" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
        <XCircle className="h-8 w-8 text-red-400 mx-auto mb-2" />
        <p className="text-red-700 font-medium">{error}</p>
        <button
          onClick={load}
          className="mt-3 px-4 py-2 bg-red-100 text-red-700 rounded-md text-sm hover:bg-red-200 transition-colors"
        >
          Retry
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Audit Trail</h1>
        <p className="text-sm text-gray-500 mt-1">
          Chronological record of all synchronization events for compliance and verification
        </p>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm px-5 py-4">
        <div className="flex items-center gap-2 mb-3">
          <Filter className="h-4 w-4 text-gray-400" />
          <span className="text-sm font-medium text-gray-700">Filters</span>
        </div>
        <div className="flex flex-wrap gap-3">
          <select
            value={dirFilter}
            onChange={(e) => setDirFilter(e.target.value)}
            className="text-sm border border-gray-200 rounded-md px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent"
          >
            <option value="all">All Directions</option>
            <option value="sws_to_dept">SWS to Department</option>
            <option value="dept_to_sws">Department to SWS</option>
          </select>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-sm border border-gray-200 rounded-md px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent"
          >
            <option value="all">All Statuses</option>
            <option value="completed">Completed</option>
            <option value="pending">Pending</option>
            <option value="conflict">Conflict</option>
            <option value="failed">Failed</option>
          </select>
          <select
            value={deptFilter}
            onChange={(e) => setDeptFilter(e.target.value)}
            className="text-sm border border-gray-200 rounded-md px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent"
          >
            <option value="all">All Departments</option>
            {departments.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
          <span className="text-xs text-gray-400 self-center ml-auto">
            {filtered.length} of {events.length} events
          </span>
        </div>
      </div>

      {/* Events list */}
      {filtered.length === 0 ? (
        <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
          <Activity className="h-10 w-10 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500 font-medium">No events match the current filters</p>
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((ev) => {
            const isExpanded = expandedId === ev.id
            return (
              <div
                key={ev.id}
                className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden"
              >
                {/* Event row */}
                <button
                  onClick={() => setExpandedId(isExpanded ? null : ev.id)}
                  className="w-full px-5 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors text-left"
                >
                  <div className="flex items-center gap-3 flex-wrap">
                    <DirectionArrow direction={ev.direction} />
                    <span className="text-sm font-medium text-gray-700">{ev.department_name ?? ev.department ?? '—'}</span>
                    <span className="text-xs text-gray-400 font-mono">{ev.ubid}</span>
                    <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
                      {ev.event_type}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <StatusBadge status={ev.status} />
                    <span className="text-xs text-gray-400 whitespace-nowrap">
                      {(() => {
                        const ts = ev.initiated_at ?? ev.timestamp
                        return ts ? new Date(ts).toLocaleString() : '—'
                      })()}
                    </span>
                    {isExpanded ? (
                      <ChevronUp className="h-4 w-4 text-gray-400" />
                    ) : (
                      <ChevronDown className="h-4 w-4 text-gray-400" />
                    )}
                  </div>
                </button>

                {/* Expanded details */}
                {isExpanded && (
                  <div className="border-t border-gray-100 px-5 py-4 bg-gray-50 space-y-4">
                    {/* Schema mapping */}
                    {(ev.source_schema || ev.translated_schema) && (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {ev.source_schema && (
                          <div>
                            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
                              Source Schema
                            </p>
                            <pre className="text-xs bg-white border border-gray-200 rounded-md p-3 overflow-x-auto text-gray-700">
                              {JSON.stringify(ev.source_schema, null, 2)}
                            </pre>
                          </div>
                        )}
                        {ev.translated_schema && (
                          <div>
                            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
                              Translated Schema
                            </p>
                            <pre className="text-xs bg-white border border-gray-200 rounded-md p-3 overflow-x-auto text-gray-700">
                              {JSON.stringify(ev.translated_schema, null, 2)}
                            </pre>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Payload hash */}
                    {ev.payload_hash && (
                      <div className="flex items-center gap-2">
                        <Shield className="h-3.5 w-3.5 text-gray-400" />
                        <span className="text-xs text-gray-500">Payload Hash:</span>
                        <code className="text-xs font-mono text-gray-600 bg-white border border-gray-200 px-2 py-0.5 rounded">
                          {ev.payload_hash}
                        </code>
                      </div>
                    )}

                    {/* Metadata */}
                    <div className="flex flex-wrap gap-4 text-xs text-gray-500">
                      <span>
                        <strong>Event ID:</strong>{' '}
                        <span className="font-mono">{ev.id}</span>
                      </span>
                      <span>
                        <strong>UBID:</strong>{' '}
                        <span className="font-mono">{ev.ubid}</span>
                      </span>
                      <span>
                        <strong>Direction:</strong> {ev.direction}
                      </span>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
