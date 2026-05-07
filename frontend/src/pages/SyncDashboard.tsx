import { useEffect, useState, useCallback } from 'react'
import {
  RefreshCw,
  ArrowRight,
  ArrowLeft,
  CheckCircle2,
  Clock,
  AlertTriangle,
  XCircle,
  Loader2,
  Database,
  Building2,
  ArrowLeftRight,
  Sparkles,
  Repeat,
} from 'lucide-react'
import type { Application, SyncEvent, ConflictStats, DashboardOverview } from '../api'
import {
  listApplications,
  listSyncEvents,
  getConflictStats,
  syncSwsToDept,
  syncDeptToSws,
  getDashboardOverview,
  retryFailedSyncs,
} from '../api'

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
      <span className="inline-flex items-center gap-1 text-amber-700 text-xs font-medium">
        SWS <ArrowRight className="h-3 w-3" /> Dept
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 text-blue-700 text-xs font-medium">
      Dept <ArrowLeft className="h-3 w-3" /> SWS
    </span>
  )
}

export default function SyncDashboard({
  showApplicationsOnly = false,
}: {
  showApplicationsOnly?: boolean
}) {
  const [apps, setApps] = useState<Application[]>([])
  const [events, setEvents] = useState<SyncEvent[]>([])
  const [stats, setStats] = useState<ConflictStats | null>(null)
  const [overview, setOverview] = useState<DashboardOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [retrying, setRetrying] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [a, e, s] = await Promise.all([
        listApplications(),
        listSyncEvents(),
        getConflictStats(),
      ])
      setApps(a)
      setEvents(e)
      setStats(s)
      // Fetch AI briefing in parallel; ignore failures so the rest of the page still loads
      getDashboardOverview().then(setOverview).catch(() => setOverview(null))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data')
    } finally {
      setLoading(false)
    }
  }, [])

  async function handleRetry() {
    setRetrying(true)
    try {
      await retryFailedSyncs()
      await load()
    } finally {
      setRetrying(false)
    }
  }

  useEffect(() => {
    void load()
  }, [load])

  async function handleSyncAll() {
    setSyncing(true)
    try {
      await Promise.all([syncSwsToDept(), syncDeptToSws()])
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sync failed')
    } finally {
      setSyncing(false)
    }
  }

  const totalApps = apps.length
  const syncedDepts = new Set(events.filter((e) => e.status === 'completed').map((e) => e.department)).size
  const pendingSyncs = events.filter((e) => e.status === 'pending').length
  const unresolvedConflicts = stats?.unresolved ?? 0

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
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            {showApplicationsOnly ? 'Applications' : 'Sync Dashboard'}
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            {showApplicationsOnly
              ? 'All SWS applications and their department sync status'
              : 'Monitor SWS-Department synchronization at a glance'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleRetry}
            disabled={retrying}
            className="inline-flex items-center gap-2 px-3 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-50 disabled:opacity-50 transition-colors shadow-sm"
            title="Retry all FAILED syncs with exponential backoff"
          >
            {retrying ? <Loader2 className="h-4 w-4 animate-spin" /> : <Repeat className="h-4 w-4" />}
            Retry Failed
          </button>
          <button
            onClick={handleSyncAll}
            disabled={syncing}
            className="inline-flex items-center gap-2 px-4 py-2 bg-amber-600 text-white rounded-lg text-sm font-medium hover:bg-amber-700 disabled:opacity-50 transition-colors shadow-sm"
          >
            {syncing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            Sync All
          </button>
        </div>
      </div>

      {/* AI Morning Briefing */}
      {!showApplicationsOnly && overview ? (
        <div className="rounded-xl bg-gradient-to-br from-indigo-50 to-white border-l-4 border-indigo-500 border-y border-r border-indigo-100 p-5">
          <div className="flex items-center gap-2 mb-2">
            <Sparkles className="h-4 w-4 text-indigo-600" />
            <span className="text-sm font-semibold text-indigo-700">AI Morning Briefing</span>
            <span className="text-[10px] uppercase tracking-wider rounded-full bg-indigo-600 text-white px-2 py-0.5 font-bold">
              Azure GPT-4.1
            </span>
            <span className="ml-auto text-xs text-gray-500">
              {overview.success_rate_pct}% success · {overview.unresolved_conflicts} unresolved
            </span>
          </div>
          <p className="text-sm leading-relaxed text-gray-700">{overview.briefing}</p>
        </div>
      ) : null}

      {/* Stats cards */}
      {!showApplicationsOnly && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="Total Applications"
            value={totalApps}
            icon={Database}
            color="amber"
          />
          <StatCard
            label="Synced Departments"
            value={syncedDepts}
            icon={Building2}
            color="green"
          />
          <StatCard
            label="Pending Syncs"
            value={pendingSyncs}
            icon={Clock}
            color="yellow"
          />
          <StatCard
            label="Unresolved Conflicts"
            value={unresolvedConflicts}
            icon={AlertTriangle}
            color="red"
          />
        </div>
      )}

      {/* Recent sync events */}
      {!showApplicationsOnly && (
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
          <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-2">
            <ArrowLeftRight className="h-4 w-4 text-amber-600" />
            <h2 className="text-lg font-semibold text-gray-900">Recent Sync Events</h2>
          </div>
          {events.length === 0 ? (
            <p className="px-5 py-8 text-gray-400 text-center text-sm">No sync events yet.</p>
          ) : (
            <ul className="divide-y divide-gray-100">
              {events.slice(0, 10).map((ev) => (
                <li key={ev.id} className="px-5 py-3 flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <DirectionArrow direction={ev.direction} />
                    <span className="text-sm font-medium text-gray-700">{ev.department}</span>
                    <span className="text-xs text-gray-400 font-mono">{ev.ubid}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <StatusBadge status={ev.status} />
                    <span className="text-xs text-gray-400">
                      {new Date(ev.timestamp).toLocaleString()}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Applications table */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-2">
          <Database className="h-4 w-4 text-amber-600" />
          <h2 className="text-lg font-semibold text-gray-900">Applications</h2>
          <span className="ml-auto text-xs text-gray-400">{apps.length} total</span>
        </div>
        {apps.length === 0 ? (
          <p className="px-5 py-8 text-gray-400 text-center text-sm">No applications found.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="bg-gray-50 text-gray-500 uppercase text-xs tracking-wider">
                <tr>
                  <th className="px-5 py-3 font-medium">UBID</th>
                  <th className="px-5 py-3 font-medium">Entity Name</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Departments</th>
                  <th className="px-5 py-3 font-medium">Last Sync</th>
                  <th className="px-5 py-3 font-medium">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {apps.map((app) => {
                  const deptRecords = app.department_records ?? []
                  const lastSync = deptRecords
                    .map((d) => d.last_synced)
                    .filter(Boolean)
                    .sort()
                    .pop()
                  return (
                    <tr key={app.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-5 py-3 font-mono text-xs text-gray-600">{app.ubid}</td>
                      <td className="px-5 py-3 font-medium text-gray-900">{app.entity_name}</td>
                      <td className="px-5 py-3">
                        <StatusBadge status={app.status} />
                      </td>
                      <td className="px-5 py-3">
                        {deptRecords.length > 0 ? (
                          <div className="flex flex-wrap gap-1">
                            {deptRecords.map((d) => (
                              <span
                                key={d.id}
                                className="inline-flex items-center gap-1 px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs"
                              >
                                {d.department}
                                <StatusBadge status={d.status} />
                              </span>
                            ))}
                          </div>
                        ) : (
                          <span className="text-gray-400 text-xs">None</span>
                        )}
                      </td>
                      <td className="px-5 py-3 text-xs text-gray-500">
                        {lastSync ? new Date(lastSync).toLocaleString() : '---'}
                      </td>
                      <td className="px-5 py-3 text-xs text-gray-500">
                        {new Date(app.created_at).toLocaleDateString()}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

/* ---------- Stat Card ---------- */

const colorMap: Record<string, string> = {
  amber: 'bg-amber-50 text-amber-700 border-amber-200',
  green: 'bg-green-50 text-green-700 border-green-200',
  yellow: 'bg-yellow-50 text-yellow-700 border-yellow-200',
  red: 'bg-red-50 text-red-700 border-red-200',
}

const iconBg: Record<string, string> = {
  amber: 'bg-amber-100',
  green: 'bg-green-100',
  yellow: 'bg-yellow-100',
  red: 'bg-red-100',
}

function StatCard({
  label,
  value,
  icon: Icon,
  color,
}: {
  label: string
  value: number
  icon: typeof Database
  color: string
}) {
  return (
    <div className={`rounded-lg border p-5 ${colorMap[color]}`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-medium opacity-75 uppercase tracking-wide">{label}</p>
          <p className="text-3xl font-bold mt-1">{value}</p>
        </div>
        <div className={`p-2.5 rounded-lg ${iconBg[color]}`}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </div>
  )
}
